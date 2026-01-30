import time
from typing import Optional, List
import argparse
import os, shutil

import traceback

from madagents.cli_bridge.bridge_handle import start_bridge, stop_bridge, InstanceHandle
from madagents.backend.server import backend_main
from madagents.frontend.main import frontend_main

import subprocess
from pathlib import Path

def run_npm_install():
    """Install required frontend dependencies and log output to disk."""
    project_dir = Path("/AgentFitter/src/madagents/frontend/ui")
    log_path = Path("/runs/logs/npm_install.log")
    log_path.parent.mkdir(exist_ok=True, parents=True)

    with open(log_path, "w") as log_file:
        result = subprocess.run(
            ["npm", "install", "remark-math", "rehype-katex", "katex"],
            cwd=project_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
    return result.returncode

def write_interface_links(frontend_port: int, backend_port: int) -> None:
    """Persist local interface URLs so users can discover running services."""
    link_path = Path("/runs/logs/madagents_links.txt")
    link_path.parent.mkdir(exist_ok=True, parents=True)
    link_path.write_text(
        "\n".join(
            [
                f"Backend: http://127.0.0.1:{backend_port}",
                f"Frontend: http://127.0.0.1:{frontend_port}",
            ]
        )
        + "\n"
    )

def main_madagent(
    frontend_port: int,
    backend_port: int,
    user_handle: InstanceHandle
) -> None:
    """Start backend and frontend services, then block to keep them alive."""
    backend_main(
        user_handle=user_handle,
        origin_port=frontend_port,
        port=backend_port,
        log_file="/runs/logs/backend.log"
    )
    write_interface_links(frontend_port, backend_port)
    print(f"Backend is running on http://127.0.0.1:{backend_port}")
    print(f"Frontend is starting on http://127.0.0.1:{frontend_port}")
    frontend_main(
        origin_port=backend_port,
        port=frontend_port,
        log_file="/runs/logs/frontend.log"
    )
    # Keep the process alive once both services are running.
    while True:
        time.sleep(5)

def main(
    frontend_port: int,
    backend_port: int
) -> None:
    """Provision dependencies, start the user bridge, and run the stack."""
    run_npm_install()

    user_handle = None
    try:
        if os.path.exists("/runs/user_bridge"):
            shutil.rmtree("/runs/user_bridge")

        # Bridge provides a CLI shell for user-directed commands.
        user_handle = start_bridge(
            name="user_cli",
            dir="/runs/user_bridge",
            cli_cmd="bash"
        )

        main_madagent(
            frontend_port,
            backend_port,
            user_handle
        )
    except Exception as ex:
        traceback.print_exc()
    finally:
        if user_handle is not None:
            # Best-effort cleanup for the CLI bridge.
            stop_bridge(user_handle)

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for frontend/backend port selection."""
    parser = argparse.ArgumentParser(description="MadAgents launcher")
    parser.add_argument(
        "--frontend_port",
        type=int,
        default=5173,
        help="Frontend port (default: %(default)s).",
    )
    parser.add_argument(
        "--backend_port",
        type=int,
        default=8000,
        help="Backend port (default: %(default)s).",
    )
    return parser.parse_args(argv)

if __name__ == "__main__":
    args = _parse_args()
    main(
        frontend_port=args.frontend_port,
        backend_port=args.backend_port
    )

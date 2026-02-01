import argparse
import os
from multiprocessing import Process
from subprocess import Popen, CalledProcessError

def frontend_main(
    origin_port,
    port,
    log_file
):
    p = Process(
        target=_frontend_main,
        args=(origin_port, port, log_file),
        daemon=True,
    )
    p.start()

def _frontend_main(
    origin_port,
    port,
    log_file
):
    with open(log_file, "w", buffering=1) as f:
        env = os.environ.copy()
        env["VITE_BACKEND_URL"] = f"http://127.0.0.1:{origin_port}"

        try:
            proc = Popen(
                ["npm", "run", "dev", "--", "--port", str(port), "--host", "127.0.0.1"],
                cwd="/AgentFitter/src/madagents/frontend/ui",
                stdout=f,
                stderr=f,
                env=env,
            )
            proc.wait() 
        except CalledProcessError as e:
            f.write(f"\nFrontend failed with error: {e}\n")
        except Exception as e:
            f.write(f"\nUnexpected error starting frontend: {e}\n")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--model")
    parser.add_argument("--log_file")
    parser.add_argument("--origin_port", type=int)
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    _frontend_main(
        args.origin_port,
        args.port,
        args.log_file
    )

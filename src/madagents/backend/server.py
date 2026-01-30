import argparse
import asyncio
import traceback
from contextlib import redirect_stderr, redirect_stdout

import uvicorn
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from madagents.backend.app import create_app
from madagents.backend.compat import ensure_aiosqlite_is_alive

#########################################################################
## Backend server #######################################################
#########################################################################

def backend_main(
    user_handle,
    origin_port,
    port,
    log_file,
):
    """Start the backend server in a separate process."""
    from multiprocessing import Process

    p = Process(target=_backend_main, args=(user_handle, origin_port, port, log_file), daemon=True)
    p.start()


def _backend_main(
    user_handle,
    origin_port,
    port,
    log_file,
):
    asyncio.run(
        _backend_main_async(
            user_handle=user_handle,
            origin_port=origin_port,
            port=port,
            log_file=log_file,
        )
    )


async def _backend_main_async(
    user_handle,
    origin_port,
    port,
    log_file,
):
    app = None
    ensure_aiosqlite_is_alive()
    with open(log_file, "w", buffering=1) as f, redirect_stdout(f), redirect_stderr(f):
        try:
            async with AsyncSqliteSaver.from_conn_string("/runs/runs.sqlite") as checkpointer:
                app = create_app(
                    user_handle=user_handle,
                    origin_port=origin_port,
                    checkpointer=checkpointer,
                )
                config = uvicorn.Config(app, host="127.0.0.1", port=port)
                server = uvicorn.Server(config)
                await server.serve()
        except Exception as ex:
            traceback.print_exc()
            print("Please crashed, please close the application.")
        finally:
            if app is not None and app.state.madgraph_handle is not None:
                from madagents.cli_bridge.bridge_handle import stop_bridge

                stop_bridge(app.state.madgraph_handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--log_file")
    parser.add_argument("--origin_port", type=int)
    return parser.parse_args()

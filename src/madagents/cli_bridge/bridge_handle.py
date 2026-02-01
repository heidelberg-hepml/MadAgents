from dataclasses import dataclass, field
from typing import Optional
import subprocess, time, os, sys
from pathlib import Path
import shutil

import signal, ctypes

@dataclass
class InstanceHandle:
    """Handle for a running CLI bridge instance."""
    name: str
    dir: str
    bridge_proc: Optional[subprocess.Popen] = field(default=None, repr=False)

    def __post_init__(self):
        """Populate commonly used host-side paths."""
        self.transcript_host = os.path.join(self.dir, "pure_transcript.log")
        self.fifo_in_host = os.path.join(self.dir, "in.fifo")

def _set_pdeathsig(sig=signal.SIGTERM):
    """
    On Linux, ask the kernel to send `sig` to this process when its parent dies.
    This runs in the child right before exec().
    """
    PR_SET_PDEATHSIG = 1
    libc = ctypes.CDLL("libc.so.6")
    libc.prctl(PR_SET_PDEATHSIG, sig)

def start_bridge(
    name: str,
    dir: str,
    cli_cmd: str
) -> InstanceHandle:
    """Start a bridge subprocess and return its handle."""
    if os.path.exists(dir):
        shutil.rmtree(dir, ignore_errors=True)
    Path(dir).mkdir(parents=True, exist_ok=True)
    bridge_script = "/AgentFitter/src/madagents/cli_bridge/bridge.py"

    cmd = [sys.executable, "-u", bridge_script, "--workdir", dir, "--cmd", cli_cmd, "--stamp-lines", "--use-shell"]
    log_path = os.path.join(dir, "bridge.out")
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o660)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            preexec_fn=_set_pdeathsig,
        )
    finally:
        os.close(log_fd)

    handle = InstanceHandle(
        name=name,
        dir=dir
    )
    handle.bridge_proc = proc

    # for _ in range(40):
    #     if os.path.exists(handle.fifo_in_host):
    #         break
    #     time.sleep(0.25)
    # else:
    #     proc.terminate()
    #     raise RuntimeError("Bridge FIFO not created; check bridge.out")

    return handle

def stop_bridge(handle: InstanceHandle):
    """Terminate the bridge subprocess if it is running."""
    proc = getattr(handle, "bridge_proc", None)
    if not proc:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

def cli_send(handle: InstanceHandle, text: str):
    """Send a line of text to the bridge FIFO."""
    os.makedirs(os.path.dirname(handle.fifo_in_host), exist_ok=True)
    with open(handle.fifo_in_host, "ab", buffering=0) as f:
        if not text.endswith("\n"):
            text = text + "\n"
        f.write(text.encode("utf-8"))

def cli_read_until(
        handle: InstanceHandle,
        start_offset: int,
        wait_s: Optional[float],
        timeout_s: float,
        idle_grace_s: float,
        max_bytes: int = 200_000,
):
    """Read transcript bytes until idle or timeout, returning new offset and data."""
    time.sleep(wait_s)
    timeout_s = max(timeout_s, 0.0)
    deadline = time.time() + timeout_s
    idle_grace_s = max(idle_grace_s, 0.0)

    while not os.path.exists(handle.transcript_host) and (time.time() < deadline):
        time.sleep(0.1)
    if not os.path.exists(handle.transcript_host):
        raise TimeoutError(f"Transcript not found at {handle.transcript_host}.")

    with open(handle.transcript_host, "rb") as tf:
        tf.seek(0, os.SEEK_END)
        file_end = tf.tell()
        pos = min(start_offset, file_end)
        buf = bytearray()

        while time.time() < deadline:
            # Sleep first to allow new output to accumulate.
            time.sleep(idle_grace_s)
            
            tf.seek(pos, os.SEEK_SET)
            chunk = tf.read()
            if chunk:
                pos += len(chunk)
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    break
            else:
                break

        tf.seek(pos, os.SEEK_SET)
        chunk = tf.read()
        if chunk:
            pos += len(chunk)
            buf.extend(chunk)

        return pos, bytes(buf)

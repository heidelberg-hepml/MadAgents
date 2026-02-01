import os
import signal
import subprocess
import threading
import time

from collections import deque

from pathlib import Path

from dataclasses import dataclass, field
from typing import Tuple, Union, Optional, Dict, List, Literal, Any

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from madagents.cli_bridge.bridge_interface import CLISession, strip_control_codes

from madagents.utils import pdf_to_content_block, image_to_content_block

#########################################################################
## web_search ###########################################################
#########################################################################

web_search_tool = {"type": "web_search"}

WEB_SEARCH_DESC = """web_search
- Built-in OpenAI tool.
- Search the web for information.
- You may use this tool to gather up-to-date information.
- Returns search results."""

#########################################################################
## bash helper functions ################################################
#########################################################################

class SwitchableSink:
    """Buffer output in memory until it exceeds a threshold, then spill to disk."""
    def __init__(self, base: str, kind: str, max_bytes: int = 2_000_000):
        """Initialize the sink with an in-memory buffer and spill settings."""
        self.base = base
        self.kind = kind  # "stdout" or "stderr"
        self.max_bytes = max_bytes

        self._buf = deque()
        self._buf_bytes = 0
        self._lock = threading.Lock()

        self._f = None
        self.path = None
        self.spilled = False

    def _spill_locked(self):
        """Move buffered output to a file (caller must hold lock)."""
        # Caller holds lock
        if self._f is not None:
            return

        self.path = _reserve_nonexistent_path(self.base, self.kind)
        f = open(self.path, "ab", buffering=0)

        # YES: flush buffered output into the file
        while self._buf:
            f.write(self._buf.popleft())
        self._buf_bytes = 0

        self._f = f
        self.spilled = True

    def attach_file(self):
        """Force output to be spilled to a file."""
        with self._lock:
            self._spill_locked()

    def write(self, chunk: bytes):
        """Append bytes to the buffer or spill file if the buffer is too large."""
        if not chunk:
            return
        with self._lock:
            if self._f is not None:
                self._f.write(chunk)
                return

            if self._buf_bytes + len(chunk) > self.max_bytes:
                self._spill_locked()
                self._f.write(chunk)
                return

            self._buf.append(chunk)
            self._buf_bytes += len(chunk)

    def get_buffered(self) -> bytes:
        """Return the buffered output when still in-memory."""
        with self._lock:
            if self._f is not None:
                return b""
            return b"".join(self._buf)

    def close(self):
        """Close any underlying file handle, ignoring errors."""
        with self._lock:
            if self._f is not None:
                try:
                    self._f.close()
                except Exception:
                    pass
                self._f = None

@dataclass
class RunningProcess:
    pid: int
    proc: subprocess.Popen
    t_out: threading.Thread
    t_err: threading.Thread
    out_sink: SwitchableSink
    err_sink: SwitchableSink
    stop_event: threading.Event

_RUNNING_PROCESSES: Dict[str, Dict[int, RunningProcess]] = {}
_RUNNING_PROCESSES_LOCK = threading.Lock()

def _get_log_root() -> str:
    """Return the root directory used for log discovery."""
    return os.path.realpath("/logs")

def _register_running_process(log_root: str, record: RunningProcess) -> None:
    """Track a running process by log root and PID."""
    with _RUNNING_PROCESSES_LOCK:
        by_pid = _RUNNING_PROCESSES.setdefault(log_root, {})
        by_pid[record.pid] = record

def _pop_running_processes(log_root: str) -> List[RunningProcess]:
    """Remove and return all tracked processes for a log root."""
    with _RUNNING_PROCESSES_LOCK:
        by_pid = _RUNNING_PROCESSES.pop(log_root, {})
        return list(by_pid.values())

def _pump_stream_to_sink(stream, sink: SwitchableSink, stop_event: Optional[threading.Event] = None, chunk_size: int = 8192):
    """Continuously read a stream into a sink until EOF or stop."""
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            if stop_event is not None and stop_event.is_set():
                break
            sink.write(chunk)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass
        sink.close()

def _reserve_nonexistent_path(base: str, kind: str, max_tries: int = 1_000) -> str:
    """Reserve a unique log path for a given base/kind."""
    log_dir = "/logs/tool_output"
    os.makedirs(log_dir, exist_ok=True)

    for i in range(max_tries):
        suffix = "" if i == 0 else f".{i}"
        path = os.path.join(log_dir, f"{base}{suffix}.{kind}.log")
        try:
            # reserve+create the file atomically
            with open(path, "xb"):
                pass
            return path
        except FileExistsError:
            continue

    raise RuntimeError(f"Could not reserve free log filename in {log_dir} after {max_tries} tries.")

def _tail_last_lines_from_bytes_info(data: bytes, n_lines: int = 20) -> tuple[str, int, bool]:
    """Return a UTF-8 tail string, line count, and truncation flag."""
    if not data:
        return "", 0, False
    lines = data.splitlines()
    total = len(lines)
    tail_lines = lines[-n_lines:] if total > n_lines else lines
    tail = b"\n".join(tail_lines).decode("utf-8", errors="replace")
    truncated = total > n_lines
    return tail, len(tail_lines), truncated

def _tail_last_lines_from_file_info(path: str, n_lines: int = 20, max_read_bytes: int = 512_000) -> tuple[str, int, bool]:
    """Tail the last lines from a file with bounded I/O."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            if end == 0:
                return "", 0, False
            to_read = min(end, max_read_bytes)
            f.seek(end - to_read, os.SEEK_SET)
            data = f.read(to_read)

        # IMPORTANT: with limited reads we may not know total lines in the whole file.
        # But we *can* know if truncation is very likely by checking whether we had
        # to read a partial file chunk.
        lines = data.splitlines()
        tail_lines = lines[-n_lines:] if len(lines) > n_lines else lines
        tail = b"\n".join(tail_lines).decode("utf-8", errors="replace")

        # If we didn't read the whole file, we can't be certain, but it's safe to say "last 20 lines"
        # when we return exactly n_lines AND we didn't read the entire file.
        read_was_partial = to_read < end
        truncated = (len(lines) > n_lines) or (read_was_partial and len(tail_lines) == n_lines)

        return tail, len(tail_lines), truncated
    except FileNotFoundError:
        return "", 0, False
    except Exception as e:
        return f"[tail error] {type(e).__name__}: {e}", 0, False

def _get_last_lines_info(sink: SwitchableSink, n_lines: int = 20) -> tuple[str, int, bool]:
    """Return tail information from a sink, reading file or buffer."""
    if sink.spilled and sink.path:
        return _tail_last_lines_from_file_info(sink.path, n_lines=n_lines)
    return _tail_last_lines_from_bytes_info(sink.get_buffered(), n_lines=n_lines)

def terminate_processes_for_log_root(log_root: str, term_timeout_s: float = 5.0, kill_timeout_s: float = 2.0) -> int:
    """Terminate all tracked processes for a given log root."""
    records = _pop_running_processes(log_root)
    for record in records:
        proc = record.proc
        record.stop_event.set()
        try:
            pgid = os.getpgid(record.pid)
        except ProcessLookupError:
            pgid = None

        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        if proc.poll() is None:
            try:
                proc.wait(timeout=term_timeout_s)
            except subprocess.TimeoutExpired:
                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    proc.wait(timeout=kill_timeout_s)
                except subprocess.TimeoutExpired:
                    proc.wait()

        for stream in (proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

        record.t_out.join()
        record.t_err.join()
        record.out_sink.close()
        record.err_sink.close()

    return len(records)

def terminate_processes_for_current_logs(term_timeout_s: float = 5.0, kill_timeout_s: float = 2.0) -> int:
    """Terminate all tracked processes under the default log root."""
    return terminate_processes_for_log_root(
        _get_log_root(),
        term_timeout_s=term_timeout_s,
        kill_timeout_s=kill_timeout_s,
    )

#########################################################################
## bash #################################################################
#########################################################################

def bash(commands: str) -> Tuple[str, dict]:
    """Run a bash command string and capture stdout/stderr with tailing."""
    timeout_s = 600
    virtual_venv = os.environ.get("VIRTUAL_ENV", None)
    env = os.environ.copy()
    if virtual_venv is not None:
        env["PATH"] = f"{virtual_venv}/bin:" + env.get("PATH", "")
    else:
        env["PATH"] = env.get("PATH", "")

    # Start a new process group so we can terminate descendants as needed.
    proc = subprocess.Popen(
        commands,
        env=env,
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        executable="/bin/bash",
        start_new_session=True,
        text=False,
        bufsize=0
    )

    base = str(proc.pid)
    out_sink = SwitchableSink(base=base, kind="stdout", max_bytes=40_000)
    err_sink = SwitchableSink(base=base, kind="stderr", max_bytes=40_000)

    stop_event = threading.Event()
    t_out = threading.Thread(target=_pump_stream_to_sink, args=(proc.stdout, out_sink, stop_event), daemon=True)
    t_err = threading.Thread(target=_pump_stream_to_sink, args=(proc.stderr, err_sink, stop_event), daemon=True)
    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True

    artefact = {
        "commands": commands,
        "pid": proc.pid,
        "timeout": timed_out,
        "exit_code": None if timed_out else proc.returncode,
    }

    stdout_text = ""
    stderr_text = ""

    # If timed out, force spill to file so we keep capturing output after returning.
    if timed_out:
        out_sink.attach_file()
        err_sink.attach_file()

        artefact["stdout_path"] = out_sink.path
        artefact["stderr_path"] = err_sink.path

        msg_lines = [
            f"Process still running after {timeout_s}s (pid={proc.pid}).",
            "Output is being written to files:",
            f"stdout: {out_sink.path}",
            f"stderr: {err_sink.path}",
        ]

        tail, n, truncated = _get_last_lines_info(out_sink, n_lines=20)
        if truncated:
            artefact["stdout_last_n"] = n # we set this only if truncated
        stdout_text = tail or ""
        if tail:
            label = f"stdout (last {f'{n} lines' if n > 1 else 'line'}) so far" if truncated else "stdout so far"
            msg_lines.append(f"--- {label} ---")
            msg_lines.append(tail)

        tail, n, truncated = _get_last_lines_info(err_sink, n_lines=20)
        if truncated:
            artefact["stderr_last_n"] = n # we set this only if truncated
        stderr_text = tail or ""
        if tail:
            label = f"stderr (last {f'{n} lines' if n > 1 else 'line'}) so far" if truncated else "stderr so far"
            msg_lines.append(f"--- {label} ---")
            msg_lines.append(tail)

        artefact["stdout"] = stdout_text
        artefact["stderr"] = stderr_text

        _register_running_process(
            _get_log_root(),
            RunningProcess(
                pid=proc.pid,
                proc=proc,
                t_out=t_out,
                t_err=t_err,
                out_sink=out_sink,
                err_sink=err_sink,
                stop_event=stop_event,
            ),
        )

        return "\n".join(msg_lines), artefact

    # Completed within timeout: wait for pumps to drain remaining data
    # t_out.join(timeout=60)
    # t_err.join(timeout=60)
    t_out.join()
    t_err.join()

    out_lines = [f"[exit code] {proc.returncode}"]

    # stdout reporting
    if out_sink.spilled and out_sink.path:
        artefact["stdout_path"] = out_sink.path
        tail, n, truncated = _get_last_lines_info(out_sink, n_lines=20)
        if truncated:
            artefact["stdout_last_n"] = n # we set this only if truncated
        stdout_text = tail or ""
        out_lines.append(f"stdout was large; full stdout is in: {out_sink.path}")
        if tail:
            truncated_str = f" (last {f'{n} lines' if n > 1 else 'line'})" if truncated else ""
            out_lines.append(f"--- stdout{truncated_str} ---")
            out_lines.append(tail)
    else:
        stdout = out_sink.get_buffered().decode("utf-8", errors="replace")
        stdout_text = stdout
        if stdout:
            out_lines.append("--- stdout ---")
            out_lines.append(stdout)

    # stderr reporting
    if err_sink.spilled and err_sink.path:
        artefact["stderr_path"] = err_sink.path
        tail, n, truncated = _get_last_lines_info(err_sink, n_lines=20)
        if truncated:
            artefact["stderr_last_n"] = n # we set this only if truncated
        stderr_text = tail or ""
        out_lines.append(f"stderr was large; full stderr is in: {err_sink.path}")
        if tail:
            truncated_str = f" (last {f'{n} lines' if n > 1 else 'line'})" if truncated else ""
            out_lines.append(f"--- stderr{truncated_str} ---")
            out_lines.append(tail)
    else:
        stderr = err_sink.get_buffered().decode("utf-8", errors="replace")
        stderr_text = stderr
        if stderr:
            out_lines.append("--- stderr ---")
            out_lines.append(stderr)

    artefact["stdout"] = stdout_text
    artefact["stderr"] = stderr_text

    return "\n".join(out_lines), artefact

class BashArgs(BaseModel):
    commands: str = Field(
        ...,
        description=(
            "Commands to be executed in bash."
        ),
    )

bash_tool = StructuredTool.from_function(
    name="bash",
    description=(
        "Execute commands in bash."
    ),
    func=bash,
    args_schema=BashArgs,
    return_direct=False,
    response_format="content_and_artifact"
)

BASH_DESC = """bash(commands: str)
- Execute a command string using /bin/bash (non-interactive).
- Runs with a configured Python virtual environment: `$VIRTUAL_ENV/bin` is prepended to `PATH` if it exists.
- Provide commands exactly as in a terminal: no leading "$", no backticks, and no markdown code fences.
- Multi-line scripts are allowed (e.g., "&&", ";" and newlines, or heredocs).
- Stdin is disabled: commands cannot read interactive input (stdin reads return EOF; use filenames or `< file` redirection).
- Avoid interactive programs (editors/pagers/prompts). Prefer non-interactive flags (e.g., `--yes`, `--no-pager`).
- Commands have a fixed 600s response window. If exceeded, you can execute new tool calls while the process remains running in the background; output continues to append to log files and you get the PID.
  This is not a timeout error! This is a feature allowing you to run long-lasting commands in the background and abort them if they appear to be stuck or in an endless loop.
- Captures stdout/stderr. If a stream exceeds ~40 KB, output is spilled to a log file and up to the last 20 lines are returned inline.
- Empty inline stdout/stderr sections are omitted.
- Stdout/stderr are decoded as UTF-8 with replacement for invalid bytes.
- Return message shape:

  - On completion:

    [exit code] <exit-code>
    stdout was large; full stdout is in: <stdout-file-path> (if spilled to file)
    --- stdout --- (omitted if empty)
    <stdout>
    stderr was large; full stderr is in: <stderr-file-path> (if spilled to file)
    --- stderr --- (omitted if empty)
    <stderr>

  - If the response window is exceeded:

    Process still running after 600s (pid=<pid>).
    Output is being written to files:
    stdout: <stdout-file-path>
    stderr: <stderr-file-path>
    --- stdout so far --- (omitted if empty)
    <stdout>
    --- stderr so far --- (omitted if empty)
    <stderr>
    
    If stderr or stdout is too large, only a truncated stderr/stdout is returned inline. This case is indicated with "(last <n> lines)"."""

#########################################################################
## wait ###############################################################
#########################################################################

def wait(minutes: float) -> str:
    """Sleep for the requested number of minutes."""
    time.sleep(minutes * 60.0)
    return f"Waited {minutes} minutes"

class WaitArgs(BaseModel):
    minutes: float = Field(
        ...,
        description=("Minutes to wait before returning."),
    )

wait_tool = StructuredTool.from_function(
    name="wait",
    description=(
        "Wait for a given number of minutes."
    ),
    func=wait,
    args_schema=WaitArgs,
    return_direct=False,
    response_format="content"
)

WAIT_DESC = """wait(minutes: float)
- Wait for the specified number of minutes.
- Return message shape:

Waited <minutes> minutes."""

#########################################################################
## apply_patch ##########################################################
#########################################################################

class ApplyPatchOp(BaseModel):
    type: Literal["create_file", "update_file", "delete_file"] = Field(..., description="Patch operation type.")
    path: str = Field(..., description="File path")
    diff: Optional[str] = Field(None, description="The hunk of the V4A diff string for create_file/update_file. Omit for delete_file.")

class ApplyPatchArgs(BaseModel):
    operations: List[ApplyPatchOp] = Field(..., description="List of patch operations to apply.")

def apply_patch(operations: List[ApplyPatchOp]) -> Tuple[str, Dict[str, Any]]:
    """Apply a batch of patch operations under the allowed roots."""
    root_dir = Path("/workspace")

    results: List[Dict[str, Any]] = []
    all_ok = True

    for op in operations:
        ok, log = apply_patch_operation_to_fs(
            root_dir=root_dir,
            operation=op.model_dump(),  # dict with type/path/diff
        )
        results.append(
            {
                "type": op.type,
                "path": op.path,
                "status": "completed" if ok else "failed",
                "output": log,
            }
        )
        all_ok = all_ok and ok

    status = "completed" if all_ok else "failed"
    message = f"apply_patch {status}: {len(results)} operation(s)"
    details_lines = []
    for item in results:
        op_type = item.get("type") or ""
        path = item.get("path") or ""
        op_status = item.get("status") or ""
        output = item.get("output") or ""
        details_lines.append(f"- {op_type} {path}: {op_status} - {output}")
    if details_lines:
        message = message + "\nResults:\n" + "\n".join(details_lines)
    return message, {
        "status": status,
        "results": results,
    }

apply_patch_tool = StructuredTool.from_function(
    name="apply_patch",
    description="Apply patch operations to files under the allowed roots (`/workspace`, `/output`, `/opt`).",
    func=apply_patch,
    args_schema=ApplyPatchArgs,
    return_direct=False,
    response_format="content_and_artifact"
)

APPLY_PATCH_DESC = """apply_patch(operations: list)
- Apply one or more patch operations to files under the allowed roots (`/workspace`, `/output`, `/opt`).
- Use this to create, update, or delete files by emitting patch operations.
- Do not use this tool for binary files!
- Operations are a list of objects with:
  - `type`: `create_file` | `update_file` | `delete_file`
  - `path`: relative to `/workspace` or absolute (must be under `/workspace`, `/output` or `/opt`)
  - `diff`: The hunk of the V4A diff string (required for create/update; omit for delete)
- Notes:
  - File writes use UTF-8 encoding.
  - Control characters are rejected in `diff`, except for newline (`\\n`), tab (`\\t`), and carriage return (`\\r`). Do not use this tool if other control characters are needed.
  - For `create_file`, the diff should represent the full file contents. Each line of the content must start with "+", even the empty lines.
  - For `update_file`, the diff should be a V4A update diff with enough surrounding context to apply cleanly.
  - In an update section, the context is the contiguous "keep" lines (prefixed with space) plus any `-` delete lines; this block must appear in the original file.
  - You may use `@@ <anchor line>` to move the search start to after a matching line (bare `@@` just separates sections); a literal `*** End of File` line after a section tries to match that section near EOF first, then falls back to normal search.
  - Matching tries exact lines first, then `rstrip`, then `strip` (fuzzier).
- After calling, the system will apply the patch and return a status + logs for each operation.
- Examples:
    - {type: "create_file", path: "/workspace/demo.txt", diff: "+Hello\n+World\n"}
      This creates the file `/workspace/demo.txt` with content "Hello\nWorld\n".
    - {type: "update_file", path: "/workspace/demo.txt", diff: "@@\n Hello\n-World\n+Universe\n"}
      This modifies the content of the above file to "Hello\nUniverse\n".
    - {type: "update_file", path: "/workspace/demo.txt", diff: "@@ Header\n Title\n-Old\n+New\n"}
      This uses an anchor line to move the search start before applying the update.
    - {type: "update_file", path: "/workspace/demo.txt", diff: "@@\n A\n-1\n+2\n@@\n Z\n-x\n+y\n"}
      This applies two separate update sections in one diff.
    - {type: "update_file", path: "/workspace/demo.txt", diff: "@@\n Tail\n-Old\n+New\n*** End of File"}
      This prefers matching the update near the end of the file.
    - {type: "delete_file", path: "/workspace/demo.txt"}
      This deletes the above file.
- Return message shape:

  apply_patch <completed|failed>: <n> operation(s)
  Results:
  - <type> <path>: <completed|failed> - <output>
  - ..."""

# Patch application

class V4ADiffError(ValueError):
    """Any problem detected while parsing or applying a V4A diff."""

@dataclass
class _Chunk:
    orig_index: int = -1
    del_lines: List[str] = field(default_factory=list)
    ins_lines: List[str] = field(default_factory=list)

def _find_context_core(lines: List[str], context: List[str], start: int) -> Tuple[int, int]:
    """Find an exact/trimmed context match and return (index, fuzz_score)."""
    if not context:
        return start, 0

    # Exact match
    for i in range(start, len(lines) - len(context) + 1):
        if lines[i : i + len(context)] == context:
            return i, 0

    # rstrip match
    ctx_r = [s.rstrip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
        if [s.rstrip() for s in lines[i : i + len(context)]] == ctx_r:
            return i, 1

    # strip match (very fuzzy)
    ctx_s = [s.strip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
        if [s.strip() for s in lines[i : i + len(context)]] == ctx_s:
            return i, 100

    return -1, 0

def _find_context(lines: List[str], context: List[str], start: int, eof: bool) -> Tuple[int, int]:
    """
    If eof=True, prefer matching the context near the end of file.
    """
    if eof:
        near_end = max(0, len(lines) - len(context))
        idx, fuzz = _find_context_core(lines, context, near_end)
        if idx != -1:
            return idx, fuzz
        idx, fuzz = _find_context_core(lines, context, start)
        return idx, fuzz + 10_000
    return _find_context_core(lines, context, start)

def _peek_next_section(diff_lines: List[str], index: int) -> Tuple[List[str], List[_Chunk], int, bool]:
    """
    Reads one "section" of V4A diff until the next @@ or EOF.
    Returns:
      - old_context_lines: the contiguous context lines that must match somewhere in the original
      - chunks: delete/insert chunks anchored relative to the context
      - new_index: where we stopped in diff_lines
      - eof: whether this section is marked as end-of-file (*** End of File)
    """
    old: List[str] = []
    del_lines: List[str] = []
    ins_lines: List[str] = []
    chunks: List[_Chunk] = []

    mode: Literal["keep", "add", "delete"] = "keep"
    orig_index = index

    while index < len(diff_lines):
        s = diff_lines[index]

        # Section boundaries:
        if s.startswith("@@") or s.startswith("***"):
            break

        index += 1

        # The reference implementation treats empty as " " keep-line.
        if s == "":
            s = " "

        if not s:
            raise V4ADiffError("Invalid empty line in diff section")

        prefix = s[0]
        body = s[1:]

        last_mode = mode
        if prefix == "+":
            mode = "add"
        elif prefix == "-":
            mode = "delete"
        elif prefix == " ":
            mode = "keep"
        else:
            raise V4ADiffError(f"Invalid diff line prefix {prefix!r}: {s!r}")

        # When returning to keep-mode after edits, close a chunk
        if mode == "keep" and last_mode != mode:
            if ins_lines or del_lines:
                chunks.append(
                    _Chunk(
                        orig_index=len(old) - len(del_lines),
                        del_lines=del_lines,
                        ins_lines=ins_lines,
                    )
                )
            del_lines, ins_lines = [], []

        if mode == "delete":
            del_lines.append(body)
            old.append(body)
        elif mode == "add":
            ins_lines.append(body)
        else:  # keep
            old.append(body)

    # Final pending chunk
    if ins_lines or del_lines:
        chunks.append(
            _Chunk(
                orig_index=len(old) - len(del_lines),
                del_lines=del_lines,
                ins_lines=ins_lines,
            )
        )

    # Optional EOF sentinel sometimes appears in older harnesses
    eof = False
    if index < len(diff_lines) and diff_lines[index] == "*** End of File":
        eof = True
        index += 1

    if index == orig_index:
        raise V4ADiffError("Nothing in this diff section")

    return old, chunks, index, eof

def apply_v4a_update_diff(original: str, diff: str) -> Tuple[str, int]:
    """
    Apply a V4A "update_file" diff to original file content.
    Returns (new_content, fuzz_score).
    """
    orig_lines = original.split("\n")
    diff_lines = diff.splitlines()
    i = 0
    search_start = 0
    fuzz_total = 0

    applied_chunks: List[_Chunk] = []

    while i < len(diff_lines):
        line = diff_lines[i]

        # V4A supports "jump" markers:
        #   @@ <anchor line>
        # or a bare "@@" line.
        if line.startswith("@@ "):
            anchor = line[3:]
            i += 1

            # Move search_start forward if we can find the anchor
            found = False
            if anchor and anchor not in orig_lines[:search_start]:
                for j in range(search_start, len(orig_lines)):
                    if orig_lines[j] == anchor:
                        search_start = j + 1
                        found = True
                        break

            # Try stripped anchor as fuzzier match if exact not found
            if anchor and not found and anchor.strip() not in [s.strip() for s in orig_lines[:search_start]]:
                for j in range(search_start, len(orig_lines)):
                    if orig_lines[j].strip() == anchor.strip():
                        search_start = j + 1
                        fuzz_total += 1
                        break

            continue

        if line.strip() == "@@":
            # bare section marker; just advance
            i += 1
            continue

        # Otherwise parse the next section (keep/add/delete lines)
        ctx, chunks, new_i, eof = _peek_next_section(diff_lines, i)

        new_index, fuzz = _find_context(orig_lines, ctx, search_start, eof=eof)
        if new_index == -1:
            ctx_txt = "\n".join(ctx)
            raise V4ADiffError(f"Context not found (start={search_start}, eof={eof}). Context:\n{ctx_txt}")
        fuzz_total += fuzz

        # Anchor chunk indices to the matched context start
        for ch in chunks:
            applied_chunks.append(
                _Chunk(
                    orig_index=new_index + ch.orig_index,
                    del_lines=ch.del_lines,
                    ins_lines=ch.ins_lines,
                )
            )

        search_start = new_index + len(ctx)
        i = new_i

    # Apply chunks in order
    applied_chunks.sort(key=lambda c: c.orig_index)
    dest_lines: List[str] = []
    cursor = 0

    for ch in applied_chunks:
        if ch.orig_index > len(orig_lines):
            raise V4ADiffError(f"Chunk index {ch.orig_index} exceeds file length {len(orig_lines)}")
        if cursor > ch.orig_index:
            raise V4ADiffError(f"Overlapping chunks: cursor {cursor} > {ch.orig_index}")

        dest_lines.extend(orig_lines[cursor : ch.orig_index])
        cursor = ch.orig_index

        # Validate deletions match (best-effort)
        if ch.del_lines:
            existing = orig_lines[cursor : cursor + len(ch.del_lines)]
            if existing != ch.del_lines:
                # Allow a little fuzz: rstrip match
                if [s.rstrip() for s in existing] != [s.rstrip() for s in ch.del_lines]:
                    raise V4ADiffError(
                        "Deletion block does not match original.\n"
                        f"Expected:\n{chr(10).join(ch.del_lines)}\n\n"
                        f"Found:\n{chr(10).join(existing)}"
                    )

        dest_lines.extend(ch.ins_lines)
        cursor += len(ch.del_lines)

    dest_lines.extend(orig_lines[cursor:])
    return "\n".join(dest_lines), fuzz_total

def v4a_create_file_content(diff: str) -> str:
    """
    For create_file: docs say diff is a V4A diff representing full contents.
    In practice this is usually every line prefixed with '+'.
    We support:
      - all non-empty lines start with '+': strip '+' prefixes
      - otherwise: treat diff as raw content
    """
    lines = diff.splitlines()
    non_empty = [ln for ln in lines if ln != ""]
    if non_empty and all(ln.startswith("+") for ln in non_empty):
        return "\n".join([ln[1:] if ln.startswith("+") else ln for ln in lines])
    return diff

def validate_v4a_create_diff(diff: str) -> Optional[str]:
    """Validate that create_file diffs use '+' prefixes for each line."""
    lines = diff.splitlines()
    for idx, line in enumerate(lines, 1):
        if not line.startswith("+"):
            return (
                "Invalid create_file diff: line "
                f"{idx} does not start with '+'. "
                "For empty lines, use '+' on its own line."
            )
    return None

def validate_diff_control_chars(diff: str) -> Optional[str]:
    """Reject control characters that are not allowed in diffs."""
    for idx, ch in enumerate(diff):
        code = ord(ch)
        if code < 32 or code == 127:
            if ch in ("\n", "\t", "\r"):
                continue
            return (
                "Invalid diff: control character "
                f"U+{code:04X} at index {idx}. "
                "Only \\n, \\t, and \\r are allowed."
            )
    return None

def _safe_join(root_dir: Path, relative_path: str) -> Path:
    """Resolve a path safely under the allowed roots."""
    rel = Path(relative_path)
    allowed_roots = (Path("/workspace").resolve(), Path("/output").resolve(), Path("/opt").resolve())

    def _is_under(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    if rel.is_absolute():
        full = rel.resolve()
        if not any(_is_under(full, root) for root in allowed_roots):
            raise ValueError(f"Absolute path is outside allowed roots: {relative_path}")
        return full

    # Resolve and ensure it stays under root_dir
    full = (root_dir / rel).resolve()
    root = root_dir.resolve()
    if not any(_is_under(root, allowed) for allowed in allowed_roots):
        raise ValueError(f"Root dir is outside allowed roots: {root_dir}")
    if root not in full.parents and full != root:
        raise ValueError(f"Path escapes root_dir: {relative_path}")
    return full

def apply_patch_operation_to_fs(
    *,
    root_dir: Path,
    operation: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Apply a single apply_patch operation (create_file/update_file/delete_file) to disk.
    Returns (success, log_output).
    """
    op_type = operation.get("type")
    path = operation.get("path")
    diff = operation.get("diff")

    if not isinstance(path, str) or not path:
        return False, "Invalid operation.path"

    try:
        full_path = _safe_join(root_dir, path)
    except Exception as e:
        return False, f"Invalid path: {e}"

    try:
        if op_type == "delete_file":
            if full_path.exists():
                full_path.unlink()
            return True, f"Deleted {path}"

        if op_type == "create_file":
            if not isinstance(diff, str):
                return False, "create_file requires operation.diff (string)"
            error = validate_diff_control_chars(diff)
            if error:
                return False, error
            error = validate_v4a_create_diff(diff)
            if error:
                return False, error
            full_path.parent.mkdir(parents=True, exist_ok=True)
            content = v4a_create_file_content(diff)
            full_path.write_text(content, encoding="utf-8")
            return True, f"Created {path} ({len(content)} chars)"

        if op_type == "update_file":
            if not isinstance(diff, str):
                return False, "update_file requires operation.diff (string)"
            error = validate_diff_control_chars(diff)
            if error:
                return False, error
            if not full_path.exists():
                return False, f"File not found: {path}"
            original = full_path.read_text(encoding="utf-8")
            updated, fuzz = apply_v4a_update_diff(original, diff)
            full_path.write_text(updated, encoding="utf-8")
            return True, f"Updated {path} (fuzz={fuzz})"

        return False, f"Unknown operation.type: {op_type!r}"

    except V4ADiffError as e:
        return False, f"Patch failed for {path}: {e}"
    except Exception as e:
        return False, f"Unhandled error applying {op_type} to {path}: {e}"

#########################################################################
## read_pdf #############################################################
#########################################################################

def read_pdf(pdf_file_path: str) -> Tuple[Union[list[dict], str], str]:
    """Validate and load a PDF file as a content block."""
    if not pdf_file_path.endswith(".pdf"):
        error_msg = f"Error: The file {pdf_file_path} does not end with .pdf"
        return error_msg, error_msg
    if not os.path.exists(pdf_file_path):
        error_msg = f"Error: The file {pdf_file_path} was not found."
        return error_msg, error_msg
    msg = f"File {pdf_file_path} opened."
    return [pdf_to_content_block(pdf_file_path)], msg

class ReadPDFArgs(BaseModel):
    pdf_file_path: str = Field(..., description="Absolute path of the PDF file.")

read_pdf_tool = StructuredTool.from_function(
    name="read_pdf",
    description="Read a PDF file.",
    func=read_pdf,
    args_schema=ReadPDFArgs,
    return_direct=False,
    response_format="content_and_artifact"
)

READ_PDF_DESC = """read_pdf(pdf_file_path: str)
- Make the PDF at pdf_file_path available to you.
- pdf_file_path must be an absolute path, must exist, and must end with ".pdf".
- After a successful call, the PDF content is included in the conversation; on failure, you will receive an error message."""

#########################################################################
## read_image ###########################################################
#########################################################################

def read_image(image_file_path: str) -> Tuple[Union[list[dict], str], str]:
    """Validate and load an image file as a content block."""
    valid_exts = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
    if not image_file_path.lower().endswith(valid_exts):
        error_msg = f"Error: The file {image_file_path} does not end with one of {', '.join(valid_exts)}"
        return error_msg, error_msg
    if not os.path.exists(image_file_path):
        error_msg = f"Error: The file {image_file_path} was not found."
        return error_msg, error_msg
    msg = f"File {image_file_path} opened."
    return [image_to_content_block(image_file_path)], msg

class ReadImageArgs(BaseModel):
    image_file_path: str = Field(..., description="Absolute path of the image file.")

read_image_tool = StructuredTool.from_function(
    name="read_image",
    description="Read an image file.",
    func=read_image,
    args_schema=ReadImageArgs,
    return_direct=False,
    response_format="content_and_artifact"
)

READ_IMAGE_DESC = """read_image(image_file_path: str)
- Make the image at image_file_path available to you.
- image_file_path must be an absolute path to an existing file.
- Supported extensions (case-insensitive): .png, .jpg, .jpeg, .webp, .gif, .bmp, .tif, .tiff.
- After a successful call, the image is included in the conversation; on failure, you will receive an error message."""

#########################################################################
## int_cli time settings ################################################
#########################################################################

WAIT_S_DEFAULT = 2.0
TIMEOUT_SECONDS = 10. * 60.
IDLE_TIMEOUT_DEFAULT = 2.0

#########################################################################
## get_int_cli_status ###################################################
#########################################################################

def _count_lines(data: bytes) -> int:
    """Count lines in a byte string, accounting for missing trailing newline."""
    if not data:
        return 0
    count = data.count(b"\n")
    if not data.endswith(b"\n"):
        count += 1
    return count

def get_int_cli_status(session: CLISession):
    """Return a tool function that reports interactive CLI session status."""
    def int_cli_status() -> Tuple[str, dict]:
        """Summarize transcript position, context, and new output."""
        first_seen = not getattr(session, "_int_cli_status_seen", False)
        session._int_cli_status_seen = True
        status = "Potentially unseen CLI session" if first_seen else "Ongoing CLI session"

        transcript_path = None
        if session.handle is not None:
            transcript_path = session.handle.transcript_host
        elif session.dir:
            transcript_path = os.path.join(session.dir, "pure_transcript.log")

        data = b""
        if transcript_path and os.path.exists(transcript_path):
            with open(transcript_path, "rb") as f:
                data = f.read()

        file_len = len(data)
        previous_offset = min(max(session.read_offset, 0), file_len)
        new_bytes = data[previous_offset:file_len] if file_len > previous_offset else b""
        session.read_offset = file_len
        prefix = data[:session.read_offset]
        new_output = strip_control_codes(new_bytes.decode("utf-8", errors="replace"))

        total_lines = _count_lines(data)
        lines_before = _count_lines(prefix)
        lines_after = max(total_lines - lines_before, 0)
        read_position_line = lines_before

        context_lines = prefix.splitlines()[-10:] if prefix else []
        context_text = ""
        context_start = None
        if context_lines:
            context_start = max(1, read_position_line - len(context_lines) + 1)
            rendered = []
            for line in context_lines:
                text = strip_control_codes(line.decode("utf-8", errors="replace")).rstrip("\r")
                rendered.append(text)
            context_text = "\n".join(rendered)

        msg_lines = [
            f"{status} ({lines_before} lines before read position, {lines_after} lines after read position)"
        ]
        if context_text:
            msg_lines.append(f"--- context lines {context_start}-{read_position_line} ---")
            msg_lines.append(context_text)
        msg_lines.append("--- new cli output ---")
        if new_output:
            msg_lines.append(new_output)

        return "\n".join(msg_lines), {
            "status": status,
            "lines_before": lines_before,
            "lines_after": lines_after,
            "context_start": context_start,
            "context": context_text,
            "new_output": new_output
        }
    return int_cli_status

class IntCLIStatusArgs(BaseModel):
    pass

def get_int_cli_status_tool(session: CLISession):
    """Create a StructuredTool for interactive CLI status."""
    int_cli_status_tool = StructuredTool.from_function(
        name="int_cli_status",
        description=(
            "Summarize the interactive CLI session state and read any new output. "
            "Reports how many lines exist before/after the current read position, shows the last 10 lines before it and the new output after it."
        ),
        func=get_int_cli_status(session),
        args_schema=IntCLIStatusArgs,
        return_direct=False,
        response_format="content_and_artifact"
    )
    return int_cli_status_tool

INT_CLI_STATUS_DESC = """int_cli_status()
- Summarize the interactive CLI session state and read any new output.
- Uses the current read position and advances it to the latest output.
- Reports how many lines exist before/after the current read position.
- Shows up to the last 10 lines before the read position as context lines.
- Shows the new output and updates the read position to the end of the new output.
- Return message shape:

  <status line>
  --- context lines <start>-<end> --- (omitted if no context)
  <context lines>
  --- new cli output ---
  <new output>"""

#########################################################################
## read_int_cli_transcript ##############################################
#########################################################################

def get_read_int_cli_transcript(session: CLISession):
    """Return a tool function to read transcript lines from the CLI session."""
    def read_int_cli_transcript(start_line: int, end_line: int) -> Tuple[str, dict]:
        """Read and format transcript lines, advancing the read offset."""
        text, start_line, end_line = session.read_transcript_lines(
            start_line=start_line,
            end_line=end_line,
            advance_read_offset=True,
        )
        if start_line == 0 and end_line == 0:
            error_msg = "Error: CLI transcript not found."
            return error_msg, {
                "text": "",
                "start_line": 0,
                "end_line": 0,
                "error": error_msg,
            }

        llm_message = f"--- cli transcript {start_line}-{end_line} ---\n{text}"
        return llm_message, {
            "text": text,
            "start_line": start_line,
            "end_line": end_line,
        }
    return read_int_cli_transcript

class ReadIntCLITranscriptArgs(BaseModel):
    start_line: int = Field(..., description="First line number to return (1-based).")
    end_line: int = Field(..., description="Last line number to return (inclusive). Use -1 for last line.")

def get_read_int_cli_transcript_tool(session: CLISession):
    """Create a StructuredTool for reading CLI transcript lines."""
    read_int_cli_transcript_tool = StructuredTool.from_function(
        name="read_int_cli_transcript",
        description=(
            "Read lines from the interactive CLI transcript. "
            "end_line is processed first: -1 means last line; otherwise it is clamped. "
            "start_line is then clamped to [1, end_line]. "
            "If end_line is beyond the current read position, the read_offset is advanced."
        ),
        func=get_read_int_cli_transcript(session),
        args_schema=ReadIntCLITranscriptArgs,
        return_direct=False,
        response_format="content_and_artifact"
    )
    return read_int_cli_transcript_tool

READ_INT_CLI_TRANSCRIPT_DESC = """read_int_cli_transcript(start_line: int, end_line: int)
- Read a line range from the interactive CLI transcript.
- end_line is processed first: -1 means last line; otherwise it is clamped to [1, last line].
- start_line is then clamped to [1, end_line].
- If end_line is beyond the current read position, the read_offset is advanced to end_line.
- Return message shape:

  --- cli transcript <start>-<end> ---
  <transcript lines>"""

#########################################################################
## read_int_cli_output ##################################################
#########################################################################

def get_read_int_cli_output(session: CLISession):
    """Return a tool function to read new CLI output."""
    def read_int_cli_output(wait_s: float = WAIT_S_DEFAULT) -> Tuple[str, str]:
        """Read new CLI output and return formatted text plus raw output."""
        cli_output = session.read_output(
            wait_s=wait_s,
            timeout_s=TIMEOUT_SECONDS,
            idle_grace_s=IDLE_TIMEOUT_DEFAULT,
        ) # .strip()
        llm_message = "--- cli output ---\n" + cli_output
        return llm_message, cli_output
    return read_int_cli_output

class ReadIntCLIOutputArgs(BaseModel):
    wait_s: float = Field(
        WAIT_S_DEFAULT,
        description=(
            "Seconds to wait before reading any CLI output. Output is read only after this delay. "
            f"Default {WAIT_S_DEFAULT:g} s. "
            "Negative values are clipped to 0.\n"
            "During installations and generations/simulations, prefer using 60-600 s."
        ),
    )

def get_read_int_cli_output_tool(session: CLISession):
    """Create a StructuredTool for reading CLI output."""
    read_int_cli_output_tool = StructuredTool.from_function(
        name="read_int_cli_output",
        description=(
            "Collect new output from the already-running interactive CLI session. "
            "Use this when you have received a new message from the user or you expect a previous command to still be printing output "
            "(e.g. when a previous 'run_cli_command' call indicated that more output may follow)."
        ),
        func=get_read_int_cli_output(session),
        args_schema=ReadIntCLIOutputArgs,
        return_direct=False,
        response_format="content_and_artifact"
    )
    return read_int_cli_output_tool

READ_INT_CLI_OUTPUT_DESC = f"""read_int_cli_output(wait_s: float = {WAIT_S_DEFAULT})
- Read new output from the already-running interactive CLI session.
- Updates the read position to the end of the new output.
- Use this for a long-running interactive command (e.g. started via "run_int_cli_command") to poll the output.
- wait_s is how many seconds to wait before reading output:
  - Prefer using the default value or 0-2 s for quick commands.
  - Prefer using 10-30 s for medium jobs.
  - Prefer using 60-600 s for long-running installs/simulations/generations.
  - If you repeatedly get empty output and you believe a command is still running, increase wait_s and try again.
- If there is no new output yet, the returned output may be empty.
- Return message shape:

  --- cli output ---
  <new_cli_output>"""

#########################################################################
## run_int_cli_command ##################################################
#########################################################################

def get_run_int_cli_command(session: CLISession):
    """Return a tool function to execute a CLI command."""
    def run_int_cli_command(command: str, wait_s: float = WAIT_S_DEFAULT) -> Tuple[str, str]:
        """Run a command in the CLI session and return formatted output."""
        cli_output = session.run_command(
            command,
            wait_s=wait_s,
            timeout_s=TIMEOUT_SECONDS,
            idle_grace_s=IDLE_TIMEOUT_DEFAULT,
        )

        # _, sep, after = cli_output.partition(command)
        # cli_output = after if sep else ""
        # cli_output = cli_output # .strip()

        llm_message = "--- cli output ---\n" + cli_output
        return llm_message, cli_output
    return run_int_cli_command

class RunIntCLICommandArgs(BaseModel):
    command: str = Field(..., description="A command to execute in the interactive CLI session.")
    wait_s: float = Field(
        WAIT_S_DEFAULT,
        description=(
            "Seconds to wait before reading any CLI output. Output is read only after this delay. "
            f"Default {WAIT_S_DEFAULT:g} s. "
            "Negative values are clipped to 0.\n"
            "During installations and generations/simulations, prefer using 60-600 s."
        ),
    )

def get_run_int_cli_command_tool(session: CLISession):
    """Create a StructuredTool for running CLI commands."""
    run_int_cli_command_tool = StructuredTool.from_function(
        name="run_int_cli_command",
        description="Execute a single, deterministic CLI command in the already-running interactive CLI session and return its output.",
        func=get_run_int_cli_command(session),
        args_schema=RunIntCLICommandArgs,
        return_direct=False,
        response_format="content_and_artifact"
    )
    return run_int_cli_command_tool

RUN_INT_CLI_COMMAND_DESC = f"""run_int_cli_command(command: str, wait_s: float = {WAIT_S_DEFAULT})
- Execute a command in the already-running interactive CLI session and return its output.
- Updates the read position to the end of the new output.
- A newline will be automatically appended if the command does not end with one.
- wait_s is how many seconds to wait before reading output:
  - Prefer using the default value or 0-2 s for quick commands.
  - Prefer using 10-30 s for medium jobs.
  - Prefer using 60-600 s for long-running installs/simulations/generations.
  - If you repeatedly get empty output and you believe a command is still running, increase wait_s and try again.
- Output may be empty if nothing was printed yet, and may include an echoed copy of the command and trailing newlines.
- Return message shape:

  --- cli output ---
  <new_cli_output>"""

#########################################################################
## save_answer ##########################################################
#########################################################################

def save_answer(file_path: str, content: str) -> str:
    """Write text content to an absolute path, overwriting if needed."""
    if not os.path.isabs(file_path):
        return f"Error: The file path {file_path} is not absolute."
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.isdir(dir_path):
        return f"Error: The directory {dir_path} does not exist."
    try:
        with open(file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
    except OSError as exc:
        return f"Error: Could not write to {file_path}: {exc}"
    return f"Saved answer to {file_path}."

class SaveAnswerArgs(BaseModel):
    file_path: str = Field(..., description="Absolute path of the file to write.")
    content: str = Field(..., description="Text content to save to the file.")

save_answer_tool = StructuredTool.from_function(
    name="save_answer",
    description="Save a text answer to a file, overwriting the file if it already exists.",
    func=save_answer,
    args_schema=SaveAnswerArgs,
    return_direct=False,
)

SAVE_ANSWER_DESC = """save_answer(file_path: str, content: str)
- Save text content to file_path.
- The file will be created if it does not exist yet. Otherwise, it will be overwritten.
- file_path must be an absolute path to a file.
- On failure, you will receive an error message.
- Return message shape (on success):

Saved answer to <file_path>"""

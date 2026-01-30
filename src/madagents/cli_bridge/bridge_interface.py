from dataclasses import dataclass
import os
from typing import Optional
import re

from pathlib import Path

import traceback

from madagents.cli_bridge.bridge_handle import (
    InstanceHandle,
    cli_read_until,
    cli_send,
    start_bridge,
    stop_bridge,
)

@dataclass
class CLISession:
    """Session wrapper around a CLI bridge and its transcript."""
    name: str = ""
    handle: Optional[InstanceHandle] = None
    read_offset: int = 0
    dir: Optional[str] = None
    finished: bool = False
    cmd_script: Optional[str] = None

    def __post_init__(self):
        """Resolve handle/dir defaults and ensure a bridge is available."""
        if self.handle is not None:
            self.dir = self.handle.dir
            self.name = self.handle.name
        else:
            if self.dir is None:
                raise ValueError("The directory of the bridge must be set!")
            if self.cmd_script is None:
                self.cmd_script = "bash"
        self._ensure_handle()

    def read_output(
        self,
        wait_s: float,
        timeout_s: float,
        idle_grace_s: float,
        max_bytes: int = 200_000,
    ) -> str:
        """Read new output from the CLI transcript, applying control stripping."""
        handle = self._ensure_handle()

        try:
            new_offset, chunk = cli_read_until(
                handle,
                start_offset=self.read_offset,
                wait_s=wait_s,
                timeout_s=timeout_s,
                idle_grace_s=idle_grace_s,
                max_bytes=max_bytes,
            )
            self.read_offset = new_offset
            cli_chunk = chunk.decode("utf-8", errors="ignore") if chunk else ""
            cli_chunk = strip_control_codes(cli_chunk)
            # cli_chunk = smart_strip_control_codes(cli_chunk)
            return cli_chunk

        except TimeoutError as exc:
            traceback.print_exc()
            return f"[Timeout error] {exc}"
        except Exception as exc:
            traceback.print_exc()
            return f"[Error] {exc}"

    def run_command(
        self,
        command: str,
        wait_s: float,
        timeout_s: float,
        idle_grace_s: float,
    ) -> str:
        """Send a single CLI command and return the resulting output."""
        handle = self._ensure_handle()
        cli_send(handle, command)
        return self.read_output(
            wait_s=wait_s,
            timeout_s=timeout_s,
            idle_grace_s=idle_grace_s,
        )

    def finish(self):
        """Terminate the bridge and mark the session finished."""
        if self.handle:
            try:
                stop_bridge(self.handle)
            finally:
                self.handle = None
        self.finished = True

    def _ensure_handle(self) -> InstanceHandle:
        """Start the bridge on-demand and return the handle."""
        if self.finished:
            raise RuntimeError("Session already finished; create a new session.")
        if self.handle:
            return self.handle
        Path(self.dir).mkdir(exist_ok=True, parents=True)
        self.handle = start_bridge(
            self.name,
            self.dir,
            self.cmd_script,
        )
        self.read_offset = 0
        return self.handle

    def _get_transcript_path(self) -> Optional[str]:
        """Return the path to the transcript file, if available."""
        handle = self._ensure_handle()
        return handle.transcript_host if handle is not None else None

    def _read_transcript_bytes(self) -> bytes:
        """Read the full transcript as bytes."""
        path = self._get_transcript_path()
        if not path or not os.path.exists(path):
            return b""
        with open(path, "rb") as f:
            return f.read()

    def read_transcript_lines(
        self,
        start_line: int,
        end_line: int,
        advance_read_offset: bool = True,
    ) -> tuple[str, int, int]:
        """
        Returns (text, start_line, end_line), using 1-based inclusive lines.
        end_line is processed first:
          -1 => last line, otherwise clamped to [1, last line].
        start_line is then clamped to [1, end_line].
        If advance_read_offset is True and end_line is beyond the current read position,
        read_offset is advanced to the end of end_line.
        """
        data = self._read_transcript_bytes()
        lines = data.splitlines(keepends=True)
        total_lines = len(lines)

        if total_lines == 0:
            return "", 0, 0

        if end_line == -1:
            end_line = total_lines
        else:
            end_line = max(1, min(int(end_line), total_lines))

        start_line = max(1, min(int(start_line), end_line))

        end_offsets = []
        pos = 0
        for line in lines:
            pos += len(line)
            end_offsets.append(pos)

        if advance_read_offset:
            current_offset = min(max(self.read_offset, 0), len(data))
            current_line = data[:current_offset].count(b"\n")
            if current_offset > 0 and not data[:current_offset].endswith(b"\n"):
                current_line += 1
            if end_line > current_line:
                # Move read_offset forward to reflect newly read lines.
                self.read_offset = end_offsets[end_line - 1]

        selected = b"".join(lines[start_line - 1:end_line])
        text = strip_control_codes(selected.decode("utf-8", errors="replace"))
        return text, start_line, end_line

ANSI_ESCAPE_RE = re.compile(
    r'''
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or CSI sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
    ''',
    re.VERBOSE
)

def strip_control_codes(s: str, keep_newlines: bool = True) -> str:
    """Remove ANSI escape sequences and control characters."""
    s = ANSI_ESCAPE_RE.sub('', s)

    if keep_newlines:
        # Remove control chars except tab (\x09), LF (\x0A) and CR (\x0D)
        s = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', s)
    else:
        # Remove all C0 control chars (including \r and \n) and DEL
        s = re.sub(r'[\x00-\x1F\x7F]', '', s)

    return s

# TODO: I don't think this is right, for instance \r\n would be handled wrong!
def smart_strip_control_codes(text: str) -> str:
    """Attempt to normalize output with carriage returns and blank lines."""
    current = ""
    last_was_blank = True
    
    text = strip_control_codes(text, keep_newlines=True)

    out_lines: list[str] = []

    for ch in text:
        if ch == "\r":
            current = ""
        elif ch == "\n":
            # finalize a line
            line = current.rstrip()
            is_blank = (line == "")
            if not is_blank or not last_was_blank:
                out_lines.append(line + "\n")
            last_was_blank = is_blank
            current = ""
        else:
            current += ch
    if current:
        out_lines.append(current)

    if not out_lines:
        return b""
    return "".join(out_lines)

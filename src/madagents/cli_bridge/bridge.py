import argparse, os, pty, select, sys, time, threading, signal, shlex, shutil, errno, stat, fcntl, struct, termios, socket

def now():
    """Return a UTC timestamp string for transcript stamping."""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

def set_winsize(fd, rows, cols):
    """Set PTY window size if rows/cols are provided or available via env."""
    if rows is None and cols is None:
        return
    # Fallback to env if one of them is missing
    if rows is None:
        rows = int(os.environ.get("LINES", "40"))
    if cols is None:
        cols = int(os.environ.get("COLUMNS", "120"))
    winsz = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsz)
    except Exception:
        # non-fatal
        pass

class ClientManager:
    def __init__(self, sock_path, stop_event, replay=True, max_client_buffer=16 * 1024 * 1024):
        """Manage attach clients and buffered output replay."""
        self.sock_path = sock_path
        self.stop_event = stop_event
        self.replay = replay
        self.max_client_buffer = max_client_buffer
        self.server = None
        self.clients = {}
        self.lock = threading.Lock()  # protects self.clients
        self.drop_warned = set()

        workdir = os.path.dirname(self.sock_path)
        self.replay_file = os.path.join(workdir, "pure_transcript.log")

    def start_server(self):
        """Start the UNIX socket server and background accept/write loops."""
        # Remove stale socket, if any
        try:
            if os.path.exists(self.sock_path):
                os.unlink(self.sock_path)
        except OSError:
            pass

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.sock_path)
        os.chmod(self.sock_path, 0o660)
        self.server.listen(5)
        self.server.setblocking(False)

        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        t_w = threading.Thread(target=self._write_loop, daemon=True)
        t_w.start()

    def _replay_to(self, conn):
        """Replay existing transcript to a newly attached client."""
        if not self.replay:
            return
        if not os.path.exists(self.replay_file):
            return
        try:
            with open(self.replay_file, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    conn.sendall(chunk)
        except OSError:
            # non-fatal: just skip replay
            pass

    def _accept_loop(self):
        """Accept new clients and register them for broadcast."""
        while not self.stop_event.is_set():
            try:
                r, _, _ = select.select([self.server], [], [], 0.25)
            except (OSError, ValueError):
                break
            if self.server in r:
                try:
                    conn, _ = self.server.accept()

                    # Replay BEFORE making it part of the broadcast set
                    conn.setblocking(True)
                    self._replay_to(conn)
                    conn.setblocking(False)

                    with self.lock:
                        self.clients[conn] = bytearray()
                except OSError:
                    continue

    def _append_with_cap(self, buf: bytearray, data: bytes) -> bool:
        """
        Append data to buf while keeping only the newest max_client_buffer bytes.
        Returns True if any data was dropped.
        """
        if not data:
            return False
        max_buf = self.max_client_buffer
        if max_buf is None:
            buf.extend(data)
            return False
        if len(data) >= max_buf:
            buf[:] = data[-max_buf:]
            return True
        total = len(buf) + len(data)
        if total <= max_buf:
            buf.extend(data)
            return False
        overflow = total - max_buf
        del buf[:overflow]
        buf.extend(data)
        return True

    def broadcast(self, data: bytes):
        """Queue data for all connected clients."""
        if not data:
            return
        with self.lock:
            for c, buf in list(self.clients.items()):
                dropped = self._append_with_cap(buf, data)
                if dropped and c not in self.drop_warned:
                    sys.stderr.write(
                        f"[bridge] client backpressure; dropping output beyond {self.max_client_buffer} bytes (fd={c.fileno()})\n"
                    )
                    self.drop_warned.add(c)

    def _drop_client_locked(self, c):
        """Remove a client and close its socket (caller holds lock)."""
        try:
            self.clients.pop(c, None)
        finally:
            self.drop_warned.discard(c)
            try:
                c.close()
            except OSError:
                pass

    def _write_loop(self):
        """Flush queued output to clients, handling backpressure."""
        while not self.stop_event.is_set():
            with self.lock:
                writable = [c for c, buf in self.clients.items() if buf]
            if not writable:
                time.sleep(0.05)
                continue
            try:
                _, w, _ = select.select([], writable, [], 0.25)
            except (OSError, ValueError):
                time.sleep(0.1)
                continue
            if not w:
                continue
            with self.lock:
                for c in w:
                    buf = self.clients.get(c)
                    if not buf:
                        continue
                    try:
                        sent = c.send(buf)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        self._drop_client_locked(c)
                        continue
                    if sent > 0:
                        del buf[:sent]

    def close(self):
        """Close all clients and remove the socket."""
        with self.lock:
            for c in list(self.clients.keys()):
                try:
                    c.close()
                except OSError:
                    pass
            self.clients.clear()
            self.drop_warned.clear()
        if self.server is not None:
            try:
                self.server.close()
            except OSError:
                pass
        try:
            if os.path.exists(self.sock_path):
                os.unlink(self.sock_path)
        except OSError:
            pass

def reader(master_fd, transcript_path, transcript_pure_path, stop_event, client_mgr, stamp_lines=False):
    """
    Read from PTY, write to transcripts, and broadcast to attached clients.
    """
    last_was_nl = True
    with open(transcript_path, "ab", buffering=0) as tf:
        with open(transcript_pure_path, "ab", buffering=0) as tf_pure:
            while not stop_event.is_set():
                try:
                    r, _, _ = select.select([master_fd], [], [], 0.25)
                except (OSError, ValueError):
                    break
                if master_fd not in r:
                    continue
                try:
                    data = os.read(master_fd, 4096)
                except OSError as e:
                    # EIO is expected when the slave side is closed
                    if e.errno in (errno.EIO, errno.ENXIO):
                        break
                    break
                if not data:
                    break

                if stamp_lines:
                    out = bytearray()
                    out_pure = bytearray()
                    for b in data.splitlines(keepends=True):
                        if last_was_nl:
                            out += f"[[{now()}]] ".encode("utf-8")
                        out += b
                        out_pure += b
                        last_was_nl = b.endswith(b"\n")
                    tf.write(out)
                    tf_pure.write(out_pure)
                    # Send raw bytes (no timestamps) to clients
                    client_mgr.broadcast(out_pure)
                else:
                    prefix = f"[[{now()}]] ".encode("utf-8")
                    tf.write(prefix)
                    tf.write(data + b"\n")
                    tf_pure.write(data)
                    client_mgr.broadcast(data)

def writer(master_fd, fifo_path, transcript_path, stop_event, write_lock, echo_commands=False):
    """
    Read commands from FIFO and send to PTY stdin.
    """
    # Create FIFO with sane perms if missing
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path, 0o660)
    else:
        # ensure it's a FIFO (in case of stale file)
        st = os.stat(fifo_path)
        if not stat.S_ISFIFO(st.st_mode):
            raise RuntimeError(f"{fifo_path} exists and is not a FIFO")

    # Open read end non-blocking
    fifo_r = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
    # Keep a dummy writer so readers don't see EOF cycles
    fifo_w = os.open(fifo_path, os.O_WRONLY | os.O_NONBLOCK)

    read_buf = bytearray()
    try:
        with open(transcript_path, "ab", buffering=0) as tf:
            while not stop_event.is_set():
                try:
                    r, _, _ = select.select([fifo_r], [], [], 0.25)
                except (OSError, ValueError):
                    break
                if fifo_r not in r:
                    continue
                try:
                    chunk = os.read(fifo_r, 4096)
                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    break
                if not chunk:
                    # No writers; just wait for the next one
                    time.sleep(0.05)
                    continue

                read_buf.extend(chunk)
                while True:
                    nl = read_buf.find(b"\n")
                    if nl == -1:
                        break
                    line = read_buf[:nl + 1]
                    del read_buf[:nl + 1]

                    # Send to PTY
                    try:
                        with write_lock:
                            os.write(master_fd, line)
                    except OSError:
                        # child likely gone
                        return

                    if echo_commands:
                        tf.write(
                            b"\n[[%s]] [BRIDGE] >> %s\n"
                            % (now().encode("utf-8"), line.rstrip(b"\n"))
                        )
    finally:
        for fd in (fifo_r, fifo_w):
            try:
                os.close(fd)
            except Exception:
                pass

def client_io_loop(master_fd, client_mgr, stop_event, write_lock):
    """
    Read keystrokes from attached clients and forward to PTY.
    """
    while not stop_event.is_set():
        with client_mgr.lock:
            clients = list(client_mgr.clients.keys())
        if not clients:
            time.sleep(0.1)
            continue
        try:
            r, _, _ = select.select(clients, [], [], 0.25)
        except (OSError, ValueError):
            time.sleep(0.1)
            continue
        for c in r:
            try:
                data = c.recv(4096)
            except OSError:
                data = b""
            if not data:
                # disconnect
                with client_mgr.lock:
                    try:
                        client_mgr.clients.pop(c, None)
                    except Exception:
                        pass
                    client_mgr.drop_warned.discard(c)
                try:
                    c.close()
                except OSError:
                    pass
                continue
            try:
                with write_lock:
                    os.write(master_fd, data)
            except OSError:
                return

def spawn(args):
    """
    Spawn the CLI inside a PTY. Returns (child_pid, master_fd).
    """
    master_fd, slave_fd = pty.openpty()

    # Set PTY window size if requested
    set_winsize(slave_fd, args.rows, args.cols)

    pid = os.fork()
    if pid == 0:
        # --- child ---
        try:
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(master_fd)
            os.close(slave_fd)

            # Build a "clean" env that preserves the container's env but ignores host dotfiles shenanigans
            env = dict(os.environ)
            # after: env = dict(os.environ)

            env["PATH"] = "/opt/envs/MAD/bin:" + env.get("PATH", "")
            lhapdf = "/opt/MG5_aMC/HEPTools/lhapdf6_py3"
            env["PYTHONPATH"] = f"/opt/envs/MAD/lib/python3.11/site-packages:{lhapdf}/lib/python3.11/site-packages:" + env.get("PYTHONPATH", "")

            env.pop("BASH_ENV", None)
            for var in list(env):
                if var.startswith(("CONDA_", "PYENV", "VIRTUAL_ENV", "PIP_")):
                    env.pop(var, None)
            env["PAGER"] = "cat"
            env["EDITOR"] = "cat"
            env["VISUAL"] = "cat"

            if args.use_shell:
                # Shell, but without reading rc files
                os.execve("/bin/bash", ["bash", "--noprofile", "--norc", "-c", args.cmd], env)
            else:
                argv = shlex.split(args.cmd)
                prog = argv[0]
                # If bare name, rely on container PATH
                if "/" not in prog and shutil.which(prog) is None:
                    sys.stderr.write(f"exec failed: '{prog}' not found in PATH={env.get('PATH','')}\n")
                    os._exit(127)
                os.execvpe(prog, argv, env)
        except Exception as e:
            sys.stderr.write(f"exec failed: {e}\n")
            os._exit(1)

    # --- parent ---
    # Close the slave in the parent so EOF works correctly
    try:
        os.close(slave_fd)
    except Exception:
        pass
    return pid, master_fd

def main():
    """Run the bridge: spawn PTY child, relay IO, and manage clients."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="/workspace/bridge", help="Shared dir (bind mounted)")
    ap.add_argument("--cmd", required=True, help="CLI command to launch (e.g., 'bash' or '/usr/local/bin/mycli')")
    ap.add_argument("--use-shell", action="store_true",
                    help="Run command via /bin/bash --noprofile --norc -c (avoid if not needed)")
    ap.add_argument("--echo-commands", action="store_true",
                    help="Echo anything received from FIFO into the transcript")
    ap.add_argument("--stamp-lines", action="store_true",
                    help="Timestamp once per output line instead of per read chunk")
    ap.add_argument("--rows", type=int, default=40, help="PTY rows (e.g., 40)")
    ap.add_argument("--cols", type=int, default=120, help="PTY cols (e.g., 120)")
    ap.add_argument("--socket-name", default="attach.sock", help="Filename for attach socket (in workdir)")
    ap.add_argument("--replay", action=argparse.BooleanOptionalAction, default=True,help="Replay pure_transcript.log to newly attached clients")

    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    transcript = os.path.join(args.workdir, "transcript.log")
    transcript_pure = os.path.join(args.workdir, "pure_transcript.log")
    fifo_in = os.path.join(args.workdir, "in.fifo")
    pidfile = os.path.join(args.workdir, "bridge.pid")
    sock_path = os.path.join(args.workdir, args.socket_name)

    # Ensure transcripts exist with sane perms
    open(transcript, "ab").close()
    os.chmod(transcript, 0o660)
    open(transcript_pure, "ab").close()
    os.chmod(transcript_pure, 0o660)

    child_pid, master_fd = spawn(args)

    # Write pidfile
    with open(pidfile, "w") as pf:
        pf.write(str(child_pid))

    stop_event = threading.Event()
    write_lock = threading.Lock()

    # Start client socket server
    client_mgr = ClientManager(sock_path, stop_event, replay=args.replay)
    client_mgr.start_server()

    # Threads: PTY->log+clients, FIFO->PTY, clients->PTY
    t_r = threading.Thread(
        target=reader,
        args=(master_fd, transcript, transcript_pure, stop_event, client_mgr, args.stamp_lines),
        daemon=True,
    )
    t_w = threading.Thread(
        target=writer,
        args=(master_fd, fifo_in, transcript, stop_event, write_lock, args.echo_commands),
        daemon=True,
    )
    t_c = threading.Thread(
        target=client_io_loop,
        args=(master_fd, client_mgr, stop_event, write_lock),
        daemon=True,
    )
    t_r.start(); t_w.start(); t_c.start()

    def shutdown():
        stop_event.set()
        # Give threads a moment to notice stop_event
        time.sleep(0.1)
        # Kill the child if still around
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                # Negative PID → send to the whole process group started by the child
                os.killpg(child_pid, sig)
            except ProcessLookupError:
                break
            except Exception:
                # Fallback: try just the child if killpg fails for some reason
                try:
                    os.kill(child_pid, sig)
                except ProcessLookupError:
                    break
            time.sleep(0.2)

        # Close PTY master
        try:
            os.close(master_fd)
        except Exception:
            pass
        # Cleanup files
        try:
            os.unlink(pidfile)
        except Exception:
            pass
        client_mgr.close()

    def handle_sigterm(signum, frame):
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Wait for child to exit, then shut down
    try:
        _, _ = os.waitpid(child_pid, 0)
    finally:
        shutdown()

if __name__ == "__main__":
    main()

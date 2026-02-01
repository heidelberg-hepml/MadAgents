import argparse
import os
import socket
import sys
import termios
import tty
import select
import signal

def main():
    """Attach to a bridge socket and proxy stdin/stdout in raw mode."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True, help="Bridge workdir (same as passed to bridge.py)")
    ap.add_argument("--socket-name", default="attach.sock", help="Socket filename in workdir")
    args = ap.parse_args()

    sock_path = os.path.join(args.workdir, args.socket_name)

    if not os.path.exists(sock_path):
        print(f"ERROR: attach socket {sock_path} does not exist", file=sys.stderr)
        sys.exit(1)

    # Connect to the Unix domain socket.
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(sock_path)
    except OSError as e:
        print(f"ERROR: failed to connect to {sock_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Put local terminal into raw mode.
    stdin_fd = sys.stdin.fileno()
    stdout_fd = sys.stdout.fileno()
    old_tio = termios.tcgetattr(stdin_fd)
    tty.setraw(stdin_fd)

    # Make socket non-blocking-ish via select.
    s.setblocking(False)

    # Handle Ctrl-C locally: just exit, bridge keeps running.
    def handle_sigint(signum, frame):
        # Restore terminal and close socket
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_tio)
        try:
            s.close()
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while True:
            # Forward stdin -> socket and socket -> stdout.
            r, _, _ = select.select([stdin_fd, s], [], [])
            if stdin_fd in r:
                data = os.read(stdin_fd, 4096)
                if not data:
                    break
                try:
                    s.sendall(data)
                except OSError:
                    break

            if s in r:
                try:
                    data = s.recv(4096)
                except OSError:
                    break
                if not data:
                    # PTY side closed
                    break
                os.write(stdout_fd, data)
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_tio)
        try:
            s.close()
        except OSError:
            pass

if __name__ == "__main__":
    main()

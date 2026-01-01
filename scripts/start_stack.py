#!/usr/bin/env python
"""
Helper script to boot both the FastAPI server and Celery worker/beat together.

Usage:
    python scripts/start_stack.py
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import List

DEFAULT_APP = "app:app"
DEFAULT_CELERY_APP = "runtime.tasks.celery_app.celery_app"
DEFAULT_RPC_APP = "rpc_app.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start FastAPI and Celery together.")
    parser.add_argument("--app", default=DEFAULT_APP, help="Uvicorn app path (default: %(default)s)")
    parser.add_argument("--host", default="0.0.0.0", help="Uvicorn host (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn port (default: %(default)s)")
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of Uvicorn worker processes")
    parser.add_argument("--celery-app", default=DEFAULT_CELERY_APP, help="Celery app path")
    parser.add_argument("--celery-loglevel", default="info", help="Celery log level (default: %(default)s)")
    parser.add_argument("--no-beat", action="store_true", help="Disable Celery beat (worker only)")

    return parser.parse_args()


def build_uvicorn_cmd(args: argparse.Namespace) -> List[str]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        args.app,
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    else:
        cmd.extend(["--workers", str(args.workers)])
    return cmd


def build_celery_cmd(args: argparse.Namespace) -> List[str]:
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        args.celery_app,
        "worker",
        "-l",
        args.celery_loglevel,
    ]
    if not args.no_beat and sys.platform != "win32":
        cmd.append("-B")
    return cmd


def build_rpc_cmd(args: argparse.Namespace) -> List[str]:
    return [sys.executable, "-m", "rpc_app"]


def terminate_process(proc: subprocess.Popen, name: str):
    if proc.poll() is None:
        print(f"[stack] Terminating {name}...")
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"[stack] Force killing {name}")
            proc.kill()


def main():
    args = parse_args()
    env = os.environ.copy()

    uvicorn_cmd = build_uvicorn_cmd(args)
    celery_cmd = build_celery_cmd(args)

    print(f"[stack] Starting Uvicorn: {' '.join(uvicorn_cmd)}")
    uvicorn_proc = subprocess.Popen(uvicorn_cmd, env=env)

    print(f"[stack] Starting Celery worker{' + beat' if not args.no_beat else ''}: {' '.join(celery_cmd)}")
    celery_proc = subprocess.Popen(celery_cmd, env=env)

    processes = [("uvicorn", uvicorn_proc), ("celery", celery_proc)]

    rpc_cmd = build_rpc_cmd(args)
    print(f"[stack] Starting RPC app")
    rpc_proc = subprocess.Popen(rpc_cmd, env=env)
    processes.append(("rpc", rpc_proc))

    interrupted = False
    try:
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    raise RuntimeError(f"{name} exited with code {ret}")
            time.sleep(1)
    except KeyboardInterrupt:
        interrupted = True
        print("[stack] Keyboard interrupt received, shutting down...")
    except RuntimeError as exc:
        print(f"[stack] {exc}")
    finally:
        for name, proc in processes:
            terminate_process(proc, name)
        if interrupted:
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()

"""CLI for ``teleop`` / ``python -m teleop`` (console script and module entry)."""

from __future__ import annotations

import argparse
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="teleop",
        description="RealSense robot: FastAPI + WebRTC + cloud signaling client.",
    )
    p.add_argument(
        "--cloud",
        metavar="URL",
        help="Cloud signaling URL (sets CLOUD_SIGNALING_URL), e.g. http://localhost:3001",
    )
    p.add_argument(
        "--robot-id",
        metavar="ID",
        help="Robot id registered with the cloud (sets ROBOT_ID)",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("TELEOP_HOST", "0.0.0.0"),
        help="Bind address for the local API (default 0.0.0.0)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Port for the local API (default 8000)",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Verbose uvicorn log level",
    )
    return p


def cli(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.cloud:
        os.environ["CLOUD_SIGNALING_URL"] = args.cloud
    if args.robot_id:
        os.environ["ROBOT_ID"] = args.robot_id

    os.environ["TELEOP_HOST"] = args.host
    os.environ["PORT"] = str(args.port)

    log_level = "debug" if args.debug else "info"

    from teleop.runtime import run_sync

    run_sync(host=args.host, port=args.port, log_level=log_level)


def main() -> None:
    cli(sys.argv[1:])


if __name__ == "__main__":
    main()

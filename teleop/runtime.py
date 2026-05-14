"""Shared entry: FastAPI + Socket.IO + cloud robot client (same as legacy ``python main.py``)."""

from __future__ import annotations

import asyncio
import os

import uvicorn

from robot_websocket_client import start_robot_websocket_client, stop_robot_websocket_client


async def _run_stack(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info",
) -> None:
    robot_task = asyncio.create_task(start_robot_websocket_client())

    config = uvicorn.Config(
        "main:combined_app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
    )
    server = uvicorn.Server(config)
    await server.serve()

    await stop_robot_websocket_client()
    try:
        robot_task.cancel()
        await robot_task
    except asyncio.CancelledError:
        pass


def run_sync(
    host: str | None = None,
    port: int | None = None,
    log_level: str = "info",
) -> None:
    """Run the robot + API stack until interrupted (blocking)."""
    h = host or os.environ.get("TELEOP_HOST", "0.0.0.0")
    p = port if port is not None else int(os.environ.get("PORT", "8000"))
    try:
        asyncio.run(_run_stack(host=h, port=p, log_level=log_level))
    except KeyboardInterrupt:
        print("Shutting down...")
        asyncio.run(stop_robot_websocket_client())

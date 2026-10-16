"""A Client that subscribes to values published by the Rust Service."""

from __future__ import annotations

import contextlib

from msl.network import Client


def handle_publications(value: int) -> None:
    """Handle a published value."""
    print(f"Heartbeat published {value}")


with Client() as client:
    print("Services:", client.services())

    heartbeat = client.link("Heartbeat")
    heartbeat.subscribe(handle_publications)
    with contextlib.suppress(KeyboardInterrupt):
        _ = input()

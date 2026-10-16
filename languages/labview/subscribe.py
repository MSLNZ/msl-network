"""Python code to subscribe to messages published by the LabVIEW Service."""

from __future__ import annotations

from contextlib import suppress

from msl.network import Client


def handle_published(value: int) -> None:
    """Handle a published value."""
    print(f"LabVIEW published {value}")


with Client() as c:
    labview = c.link("LabVIEW")
    labview.subscribe(handle_published)
    with suppress(KeyboardInterrupt):
        _ = input()

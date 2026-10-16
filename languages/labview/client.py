"""Example of a client module that LabVIEW code can use to send requests and subscribe to publications."""

from __future__ import annotations

from contextlib import suppress
from queue import Empty, Queue
from typing import Any

from msl.network import Client, Link

client: Client | None = None
link: Link | None = None

publication: Queue[Any] = Queue()


def get_published_value(timeout: float | None = None) -> Any:
    """The LabVIEW code gets a published value."""
    try:
        value = publication.get(timeout=timeout)
    except Empty:
        return -1
    else:
        publication.task_done()
        return value


def send_request(function: str, *args: Any) -> Any:
    """The LabVIEW code sends a request to the linked Service.

    Args:
        function: The name of the function on the Service to call.
        args: The arguments that the `function` on the Service requires.
    """
    if link is not None:
        return getattr(link, function)(*args)
    return None


def services(timeout: float | None = None) -> list[str]:
    """The LabVIEW code requests the list of Services that are available."""
    if client is not None:
        return client.services(timeout)
    return []


def start(service: str) -> None:
    """Start the Client (connect to the Broker) and create a Link with a Service."""
    global client, link
    client = Client()
    link = client.link(service)


def stop() -> None:
    """Stop the Client (disconnect from the Broker)."""
    global client, link
    if client is not None:
        with suppress(Exception):
            client.disconnect()
        client = None
        link = None


def subscribe() -> None:
    """The LabVIEW code wants to subscribe to publications from the Service."""
    if link is not None:
        link.subscribe(publication.put_nowait)


def unsubscribe() -> None:
    """The LabVIEW code wants to unsubscribe to publications from the Service."""
    if link is not None:
        link.unsubscribe()

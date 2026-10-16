"""Example of a service module that LabVIEW code can use to handle requests and publish values."""

from __future__ import annotations

from contextlib import suppress
from queue import Empty, Queue
from threading import Thread
from typing import Any

from msl.network import Service

# The following queues and functions are generic and may be used
# with any LabVIEW Service that you implement

service: LabVIEW | None = None

arguments: Queue[tuple[Any, ...]] = Queue()
result: Queue[tuple[bool, Any]] = Queue()
task: Queue[str] = Queue()


def get_arguments() -> Any:
    """The LabVIEW code gets the values of the arguments that were sent in the request."""
    args = arguments.get()
    arguments.task_done()
    if not args:
        return None
    if len(args) == 1:
        return args[0]
    return args


def get_task(timeout: float) -> str:
    """Get the name of the next task that the LabVIEW code should process.

    If a Client has not sent a request within `timeout` seconds an empty string
    is returned. This allows for the LabVIEW code to implement a graceful
    shut down procedure, rather than clicking on the Abort button in the toolbar.
    """
    try:
        name = task.get(timeout=timeout)
        task.task_done()
    except Empty:
        return ""
    else:
        return name


def publish(value: Any) -> None:
    """Publish a value to all subscribed Client's."""
    if service is not None:
        service.publish(value)


def set_error(reason: str) -> None:
    """The LabVIEW code sets the reply to be an error message.

    The Client's request could not be handled successfully.
    """
    result.put_nowait((False, reason))


def set_value(value: Any) -> None:
    """The LabVIEW code sets the reply to be a value.

    The Client's request was handled successfully.
    """
    result.put_nowait((True, value))


def start() -> None:
    """Start the Service (connect to the Broker)."""
    global service
    service = LabVIEW()
    Thread(target=service.connect, daemon=True).start()


def stop() -> None:
    """Stop the Service (disconnect from the Broker)."""
    global service
    if service is not None:
        with suppress(Exception):
            service.disconnect()
        service = None


def wait_for_result() -> Any:
    """Waits for the LabVIEW code to set a result (an error or a value)."""
    ok, value = result.get()
    result.task_done()
    if ok:
        return value
    raise RuntimeError(value)


class LabVIEW(Service):
    """The methods in this Service must be rewritten for your specific application."""

    def add(self, x: float, y: float) -> float:
        """Every method that your Service implements does the same three things.

        1. Specifies the name of the task that the LabVIEW code must handle.
        2. Specifies the arguments that the LabVIEW code can get.
        3. Waits for the LabVIEW code to set a result (an error or a value).
        """
        task.put_nowait("add")
        arguments.put_nowait((x, y))  # must put a tuple of the arguments
        result: float = wait_for_result()
        return result

    def reverse_string(self, s: str) -> str:
        """Reverse a string."""
        task.put_nowait("reverse_string")
        arguments.put_nowait((s,))  # must put a tuple of the arguments
        result: str = wait_for_result()
        return result

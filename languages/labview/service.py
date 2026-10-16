"""Example of a service module that LabVIEW code can use to handle requests and publish values."""

from __future__ import annotations

from contextlib import suppress
from queue import Empty, Queue
from threading import Thread
from typing import Any

from msl.network import Service


class LabVIEW(Service):
    """The methods in this Service must be rewritten for your specific application.

    Every method that your Service implements does the same three things:

    1. Put the name of the task into the queue for the LabVIEW code to `get_task`.
    2. Put the arguments into the queue for the LabVIEW code to `get_arguments`.
    3. Wait for the LabVIEW code to set a result (an error or a value).
    """

    def add(self, x: float, y: float) -> float:
        """Add two numbers."""
        put_task("add")
        put_arguments(x, y)
        result: float = wait_for_result()
        return result

    def reverse_string(self, s: str) -> str:
        """Reverse a string."""
        put_task("reverse_string")
        put_arguments(s)
        result: str = wait_for_result()
        return result


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
    """The LabVIEW code gets the name of the next task to process.

    If a Client has not sent a request within `timeout` seconds an empty string
    is returned. This allows for the LabVIEW code to implement a graceful
    shut down procedure, rather than clicking on the Abort button in the toolbar.
    """
    try:
        name = task.get(timeout=timeout)
    except Empty:
        return ""
    else:
        task.task_done()
        return name


def publish(value: Any) -> None:
    """The LabVIEW code publishes a value to all subscribed Client's."""
    if service is not None:
        service.publish(value)


def put_arguments(*args: Any) -> None:
    """Put the arguments into the queue for the LabVIEW code."""
    arguments.put_nowait(args)


def put_task(name: str) -> None:
    """Put the name of the task into the queue for the LabVIEW code."""
    task.put_nowait(name)


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
    """The LabVIEW code starts the Service (connect to the Broker)."""
    global service
    service = LabVIEW()
    Thread(target=service.connect, daemon=True).start()


def stop() -> None:
    """The LabVIEW code stops the Service (disconnect from the Broker)."""
    global service
    if service is not None:
        with suppress(Exception):
            service.disconnect()
        service = None


def wait_for_result() -> Any:
    """Wait for the LabVIEW code to set a result (an error or a value)."""
    ok, value = result.get()
    result.task_done()
    if ok:
        return value

    # The Client receives the error message.
    # The Service continues to run to handle another request.
    raise RuntimeError(value)

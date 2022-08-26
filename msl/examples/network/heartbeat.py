"""
Example Service that emits notifications to all linked Clients. This example
also shows how to add a task to the event loop of the Service.

Before running this module ensure that the Network Manager is running on the
same computer, i.e., run the following command in a terminal

msl-network start

then run this module to connect to the Manager as a Service.

After the Heartbeat Service starts you can connect to the Manager as a Client,
link with the Heartbeat Service, handle notifications from the Service and also
send requests, e.g.,

import types
from msl.network import connect

def print_notification(self, *args, **kwargs):
    print(f'The {self.service_name} Service emitted', args, kwargs)

cxn = connect()
heartbeat = cxn.link('Heartbeat')
heartbeat.notification_handler = types.MethodType(print_notification, heartbeat)

# some time later

heartbeat.reset()
"""
import asyncio

from msl.network import Service


class Heartbeat(Service):

    def __init__(self):
        """A Service that emits a counter value."""
        super(Heartbeat, self).__init__()
        self._sleep = 1.0
        self._counter = 0
        self._alive = True

    def kill(self) -> None:
        """Stop emitting the heartbeat."""
        self._alive = False

    def reset(self) -> None:
        """Reset the heartbeat counter."""
        self._counter = 0

    def set_heart_rate(self, beats_per_second: int) -> None:
        """Change the rate that the value of the counter is emitted."""
        self._sleep = 1.0 / float(beats_per_second)

    def shutdown_handler(self) -> None:
        """Called when the connection to the Manager is closed."""
        self._alive = False

    async def emit(self) -> None:
        """This coroutine is also run in the event loop."""
        while self._alive:
            self.emit_notification(self._counter)
            self._counter += 1
            await asyncio.sleep(self._sleep)


if __name__ == '__main__':
    # Initialize the Service
    service = Heartbeat()

    # Add a task to the event loop of the Service
    service.add_tasks(service.emit())

    # Start the Service
    service.start()

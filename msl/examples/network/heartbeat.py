"""
Example heartbeat :class:`~msl.network.service.Service` that emits notifications.

Before running this module ensure that the Network :class:`~msl.network.manager.Manager`
is running on the same computer (i.e., run ``msl-network start`` in a terminal
to start the Network :class:`~msl.network.manager.Manager`).

After the ``Heartbeat`` :class:`~msl.network.service.Service` starts you can
:meth:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`,
:meth:`~msl.network.client.Client.link` with the ``Heartbeat`` :class:`~msl.network.service.Service`
and re-assign the :meth:`~msl.network.client.Link.notification_handler` method to handle
the notifications.
"""
import asyncio
from threading import Thread

from msl.network import Service


class Heartbeat(Service):

    def __init__(self):
        """A Service that emits a counter value."""
        super(Heartbeat, self).__init__()
        self._sleep = 1.0
        self._counter = 0
        self._alive = True
        self._thread = Thread(target=self._run_iterate_loop, daemon=True)
        self._thread.start()

    def kill(self) -> None:
        """Stop emitting the heartbeat."""
        self._alive = False

    def reset(self) -> None:
        """Reset the heartbeat counter."""
        self._counter = 0

    def set_heart_rate(self, beats_per_second: int) -> None:
        """Change the rate that the value of the counter is emitted."""
        self._sleep = 1.0 / float(beats_per_second)

    async def _iterate(self):
        """Private method that emits the heartbeat."""
        while self._alive:
            self.emit_notification(self._counter)
            self._counter += 1
            await asyncio.sleep(self._sleep)

    def _run_iterate_loop(self):
        """Private method that start the heartbeat loop."""
        loop = asyncio.new_event_loop()
        task = loop.create_task(self._iterate())
        loop.run_until_complete(task)

    def shutdown_handler(self, exc):
        self._alive = False


if __name__ == '__main__':
    service = Heartbeat()
    service.start()

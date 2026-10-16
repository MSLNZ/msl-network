"""Python version of a Service that LabVIEW code can subscribe to."""

from __future__ import annotations

import asyncio

from msl.network import Service


class Python(Service):
    """Python version of a Service that LabVIEW code can subscribe to."""

    _counter: int = 0

    async def emit(self) -> None:
        """Publish the counter value every second."""
        _ = await self.connected.wait()
        while True:
            self.publish(self._counter)
            print(f"Python published {self._counter}")
            self._counter += 1
            await asyncio.sleep(1)


if __name__ == "__main__":
    python = Python()
    python.add_tasks(python.emit())
    python.connect()

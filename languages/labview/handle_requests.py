"""Python version of a Service that LabVIEW code can send requests to."""

from __future__ import annotations

from msl.network import Service


class Python(Service):
    """Python version of a Service that LabVIEW code can send requests to."""

    def add(self, x: float, y: float) -> float:
        """Add two numbers."""
        return x + y

    def reverse_string(self, s: str) -> str:
        """Reverse a string."""
        return s[::-1]


if __name__ == "__main__":
    python = Python()
    python.connect()

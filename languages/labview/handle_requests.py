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

    def scale_array(self, f: float, array: list[float]) -> list[float]:
        """Scale an array."""
        if f > 0:
            return [f * value for value in array]

        msg = "The scaling factor must be > 0"
        raise ValueError(msg)


if __name__ == "__main__":
    python = Python()
    python.connect()

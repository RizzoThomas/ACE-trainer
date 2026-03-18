"""Shared memory reader for Assetto Corsa, ACC, and AC Evo telemetry.

This package provides a thread-safe, pure-Python interface to the shared memory
segments exposed by the Assetto Corsa family of racing simulations.

Supported games:
- Assetto Corsa (AC)
- Assetto Corsa Competizione (ACC)
- Assetto Corsa Evo (experimental)

Example usage:
    >>> from telemetry.reader import SharedMemoryReader
    >>> reader = SharedMemoryReader()
    >>> try:
    ...     data = reader.read()
    ...     print(f"RPM: {data.physics.rpm}, Speed: {data.graphics.speed}")
    ... except GameNotRunningError:
    ...     print("Game not running")
"""

__version__ = "0.1.0"

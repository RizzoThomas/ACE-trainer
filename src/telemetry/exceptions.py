"""Custom exception hierarchy for telemetry module.

All exceptions derive from TelemetryError for easy catch-all handling.
"""


class TelemetryError(Exception):
    """Base exception for all telemetry-related errors."""

    pass


class SharedMemoryError(TelemetryError):
    """Raised when shared memory access fails or is unavailable."""

    pass


class GameNotRunningError(SharedMemoryError):
    """Raised when the target game process is not running or memory not mapped."""

    pass


class SharedMemoryDisconnectedError(SharedMemoryError):
    """Raised when shared memory was available but disconnected during operation.

    This occurs during hot-plugging scenarios when the game closes while
    the reader is active.
    """

    pass


class DataParseError(TelemetryError):
    """Raised when binary data cannot be parsed or validation fails.

    Includes context about which field failed and why.
    """

    def __init__(self, message: str, field: str | None = None, value: object = None) -> None:
        """Initialize with optional field and value context.

        Args:
            message: Human-readable error description
            field: Name of the field that failed validation (if applicable)
            value: The problematic value (if available)
        """
        super().__init__(message)
        self.field = field
        self.value = value

    def __str__(self) -> str:
        """Return detailed string representation."""
        base = super().__str__()
        if self.field is not None:
            return f"{base} (field: {self.field}, value: {self.value})"
        return base


class GameVariantError(TelemetryError):
    """Raised when game variant detection or initialization fails."""

    pass


class MockModeError(TelemetryError):
    """Raised when mock mode encounters an inconsistent state."""

    pass

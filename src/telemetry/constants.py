"""Shared memory layout constants and configuration.

This module defines the memory map locations, data sizes, and validation
ranges for each supported Assetto Corsa game variant.

The actual struct layouts will be defined in reader.py based on PDF spec.
"""

from enum import StrEnum


class GameVariant(StrEnum):
    """Supported Assetto Corsa game variants."""

    ASSETTO_CORSA = "AC"
    ASSETTO_CORSA_COMPETIZIONE = "ACC"
    ASSETTO_CORSA_EVO = "AC_EVO"


# Windows shared memory mapping names (named sections)
# These are the tag names used with CreateFileMapping/MapViewOfFile
# The exact names should be verified from the PDF documentation
SHARED_MEMORY_NAMES = {
    GameVariant.ASSETTO_CORSA: {
        "physics": "Local\\AssettoCorsa\\Physics",
        "graphics": "Local\\AssettoCorsa\\Graphics",
        "static": "Local\\AssettoCorsa\\Static",
    },
    GameVariant.ASSETTO_CORSA_COMPETIZIONE: {
        "physics": "Local\\ACCV\\Physics",
        "graphics": "Local\\ACCV\\Graphics",
        "static": "Local\\ACCV\\Static",
    },
    GameVariant.ASSETTO_CORSA_EVO: {
        "physics": "Local\\ACEvo\\Physics",
        "graphics": "Local\\ACEvo\\Graphics",
        "static": "Local\\ACEvo\\Static",
    },
}

# Default polling interval for hot-plugging detection (seconds)
DEFAULT_POLL_INTERVAL = 0.016  # ~60 Hz

# Connection timeout (seconds)
DEFAULT_CONNECTION_TIMEOUT = 5.0

# Data validation ranges (based on realistic car physics)
MAX_RPM = 20000  # Most racing engines redline below 15000
MAX_SPEED_KMH = 400  # Top speed for most race cars
MAX_GEAR = 10  # Sequential + reverse

# Tire pressure range (psi) - typical street/track pressures
MIN_TIRE_PRESSURE_PSI = 10.0
MAX_TIRE_PRESSURE_PSI = 50.0

# Physics update rate (Hz) - used for time deltas
PHYSICS_HZ = 60  # Most games update physics at 60Hz or 120Hz

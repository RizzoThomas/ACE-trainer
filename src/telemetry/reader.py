"""Shared memory reader interface and base implementation.

This module provides the core reader classes for accessing Assetto Corsa
telemetry through Windows shared memory.

Architecture:
- SharedMemoryReader: Abstract base class defining the interface
- WindowsSharedMemoryReader: Concrete implementation using mmap/struct
- MockSharedMemoryReader: Test/dev mode with synthetic data

All readers are thread-safe and support hot-plugging (game start/stop detection).
"""

from __future__ import annotations

import abc
import ctypes
import threading
import time
from pathlib import Path
from typing import ClassVar

from .constants import DEFAULT_POLL_INTERVAL, GameVariant, SHARED_MEMORY_NAMES
from .exceptions import (
    DataParseError,
    GameNotRunningError,
    GameVariantError,
    SharedMemoryDisconnectedError,
    SharedMemoryError,
    TelemetryError,
)
from .models import (
    GraphicsData,
    PhysicsData,
    StaticData,
    SPageFileGraphics,
    SPageFilePhysics,
    SPageFileStatic,
    graphics_from_ctypes,
    physics_from_ctypes,
    static_from_ctypes,
)


# ============================================================================
# Abstract Base Class
# ============================================================================


class SharedMemoryReader(abc.ABC):
    """Abstract interface for shared memory readers.

    All shared memory readers must implement these methods. The reader is
    designed to be used in a background thread polling at ~60Hz.

    Attributes:
        game_variant: The detected or configured game variant (AC/ACC/AC_Evo).
        is_connected: True if shared memory is currently accessible.
    """

    def __init__(self, *, variant: GameVariant | None = None, poll_interval: float = DEFAULT_POLL_INTERVAL) -> None:
        """Initialize reader.

        Args:
            variant: Force a specific game variant. If None, auto-detect.
            poll_interval: How often to check for game presence (seconds).
                          Only relevant for hot-plugging detection.
        """
        self._game_variant = variant
        self._poll_interval = poll_interval
        self._connected = False
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._last_error: Exception | None = None

    @property
    def game_variant(self) -> GameVariant:
        """Return the current game variant.

        Raises:
            GameVariantError: If variant is not yet detected/configured.
        """
        if self._game_variant is None:
            raise GameVariantError("Game variant not detected or configured")
        return self._game_variant

    @property
    def is_connected(self) -> bool:
        """True if shared memory is currently accessible and game is running."""
        with self._lock:
            return self._connected

    @abc.abstractmethod
    def read(self) -> tuple[PhysicsData, GraphicsData, StaticData]:
        """Read latest telemetry data from shared memory.

        This method should be fast (< 1ms) and non-blocking when connected.
        It may block briefly (up to timeout) if disconnected and waiting
        for game to start.

        Returns:
            A tuple of (physics, graphics, static) data objects.

        Raises:
            GameNotRunningError: If the game is not running.
            SharedMemoryDisconnectedError: If connection was lost during read.
            DataParseError: If binary data is malformed or invalid.
            TelemetryError: For other reader-specific errors.
        """
        raise NotImplementedError

    def disconnect(self) -> None:
        """Explicitly disconnect from shared memory.

        This releases resources and marks the reader as disconnected.
        The reader can be reconnected by calling read() again.
        """
        with self._lock:
            self._connected = False
            self._last_error = None

    @abc.abstractmethod
    def _detect_game_variant(self) -> GameVariant:
        """Auto-detect which game variant is running.

        Returns:
            The detected GameVariant.

        Raises:
            GameVariantError: If detection fails.
        """
        raise NotImplementedError

    def __enter__(self) -> SharedMemoryReader:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: object, exc_val: BaseException, exc_tb: object) -> None:
        """Context manager exit — ensure cleanup."""
        self.disconnect()


# ============================================================================
# Mock Implementation for UI Development
# ============================================================================


class MockSharedMemoryReader(SharedMemoryReader):
    """Mock reader that returns synthetic, deterministic telemetry data.

    This allows UI development without the game running. Data patterns
    simulate realistic car behavior: RPM ramping, speed changes, gear shifts.
    """

    def __init__(self, *, seed: int = 42, **kwargs: object) -> None:
        """Initialize mock reader.

        Args:
            seed: Random seed for deterministic data generation.
            **kwargs: Passed to SharedMemoryReader.__init__.
        """
        super().__init__(**kwargs)
        self._seed = seed
        self._counter = 0  # Increments each read()
        self._lock = threading.RLock()
        # Auto-detect variant if not forced (mock always returns AC)
        if self._game_variant is None:
            self._game_variant = self._detect_game_variant()

    def read(self) -> tuple[PhysicsData, GraphicsData, StaticData]:
        """Generate synthetic telemetry data.

        Returns:
            Tuple of (physics, graphics, static) with realistic patterns.
        """
        with self._lock:
            self._counter += 1
            t = self._counter * DEFAULT_POLL_INTERVAL

            # Simulate varying RPM (idle ~1000, redline ~15000)
            rpm = int(1000 + 14000 * (0.5 + 0.5 * (t % 10) / 10))

            # Simulate speed (0-250 km/h)
            speed = 250.0 * (t % 20) / 20.0

            # Simulate gear (1-7, cycling)
            gear = (int(t) % 7) + 1

            physics = PhysicsData(
                rpm=rpm,
                speed=speed,
                gear=gear,
                throttle=0.8 if gear > 1 else 0.0,
                brake=0.1 if gear > 2 else 0.0,
                clutch=0.0,
                steering=5.0 * (t % 2 - 1),  # oscillate -5 to +5
                pos_x=0.0,
                pos_y=0.0,
                pos_z=0.0,
                vel_x=speed / 3.6,  # km/h to m/s
                vel_y=0.0,
                vel_z=0.0,
                acc_x=0.0,
                acc_y=0.0,
                acc_z=0.0,
                tire_pressure=[32.5, 32.5, 30.0, 30.0],  # Front/Rear psi
                tire_temperature=[[90.0, 100.0, 90.0]] * 4,  # inner/center/outer
                tire_wear=[0.05, 0.05, 0.05, 0.05],
                suspension_position=[0.0, 0.0, 0.0, 0.0],
                suspension_velocity=[0.0, 0.0, 0.0, 0.0],
                front_wing_setting=2,
                rear_wing_setting=3,
                fuel_level=120.0 - t * 0.1,  # slowly decreasing
                lap=int(t // 60) + 1,
                lap_time=90.0 + (t % 10),
                sector=1,
                is_on_track=True,
                is_rewinding=False,
            )

            graphics = GraphicsData(
                display_speed=speed,
                display_rpm=rpm,
                display_gear=gear,
                shift_light=rpm > 13000,
                rev_limiter=False,
                current_lap=physics.lap,
                total_laps=10,
                current_lap_time=physics.lap_time,
                last_lap_time=89.5,
                best_lap_time=88.2,
                delta_to_best=physics.lap_time - 88.2,
                flag=0,
                pit_limiter=False,
                yellow_danger=False,
                race_position=1,
                total_competitors=20,
            )

            static = StaticData(
                car_model="Ferrari 488 GT3",
                car_skins=10,
                tire_compound="slick",
                tire_size=[305/30, 71, 18] * 4,
                driver_name="Test Driver",
                driver_nationality="ITA",
                session_type=2,  # race
                track_name="Monza",
                track_length=5793.0,
                weather="Clear",
                max_rpm=15000,
                max_speed=330.0,
                fuel_capacity=120.0,
            )

            return physics, graphics, static

    def _detect_game_variant(self) -> GameVariant:
        """Mock always returns AC variant unless overridden."""
        return GameVariant.ASSETTO_CORSA

    def __enter__(self) -> MockSharedMemoryReader:
        """Enter context manager — mark as connected."""
        self._connected = True
        return self


# ============================================================================
# Windows Shared Memory Implementation (Phase 1 scaffold)
# ============================================================================


class WindowsSharedMemoryReader(SharedMemoryReader):
    """Windows implementation using mmap to read shared memory sections.

    This is the production reader that connects to the game's shared memory.
    It uses ctypes structures to parse the binary layout exactly as defined
    in the Assetto Corsa shared memory specification.

    Attributes:
        _mmap_physics, _mmap_graphics, _mmap_static: Memory maps for each section.
        _lock: Threading lock for safe concurrent access.
    """

    # Struct sizes computed from ctypes definitions (must match PDF spec)
    PHYSICS_STRUCT_SIZE = ctypes.sizeof(SPageFilePhysics)
    GRAPHICS_STRUCT_SIZE = ctypes.sizeof(SPageFileGraphics)
    STATIC_STRUCT_SIZE = ctypes.sizeof(SPageFileStatic)

    def __init__(self, *, variant: GameVariant | None = None, poll_interval: float = DEFAULT_POLL_INTERVAL) -> None:
        """Initialize Windows shared memory reader.

        Args:
            variant: Force a specific game variant. If None, auto-detect by checking
                    which shared memory names exist.
            poll_interval: Interval for hot-plugging detection (seconds).
        """
        super().__init__(variant=variant, poll_interval=poll_interval)
        self._mmap_physics: object = None  # mmap.mmap object (typing: avoid import at top)
        self._mmap_graphics: object = None
        self._mmap_static: object = None
        self._lock = threading.RLock()

    def _detect_game_variant(self) -> GameVariant:
        """Auto-detect game variant by checking which shared memory names exist."""
        # Import here to avoid platform issues on non-Windows
        import mmap
        import os

        # If variant was forced in constructor, use it
        if self._game_variant is not None:
            return self._game_variant

        # Check each variant's shared memory names
        for variant in GameVariant:
            names = SHARED_MEMORY_NAMES.get(variant, {})
            # Try to open any one of the sections to detect
            physics_name = names.get("physics", "")
            if physics_name:
                try:
                    # Attempt to open shared memory
                    access = mmap.ACCESS_READ
                    with mmap.mmap(-1, 0, tagname=physics_name, access=access) as test_map:
                        # If we got here, the mapping exists
                        return variant
                except OSError:
                    # This variant not running
                    continue

        raise GameNotRunningError(
            "Could not detect running game. Ensure Assetto Corsa is running, "
            "or pass variant explicitly."
        )

    def _open_memory_maps(self) -> None:
        """Open mmap handles for all shared memory sections.

        This is called after successful variant detection.

        Raises:
            GameNotRunningError: If any required section cannot be opened.
        """
        import mmap

        if self._game_variant is None:
            raise GameVariantError("Variant not set before opening memory maps")

        names = SHARED_MEMORY_NAMES[self._game_variant]

        # Helper to open one section
        def open_section(key: str, size_attr: str) -> object:
            name = names[key]
            size = getattr(self, size_attr)
            try:
                access = mmap.ACCESS_READ
                mm = mmap.mmap(-1, size, tagname=name, access=access)
                setattr(self, key, mm)
                return mm
            except OSError as e:
                raise GameNotRunningError(f"Failed to open {key} shared memory: {name}") from e

        # Open all three sections (we'll change 'key' to store in correct attributes)
        try:
            self._mmap_physics = open_section("physics", "PHYSICS_STRUCT_SIZE")
            self._mmap_graphics = open_section("graphics", "GRAPHICS_STRUCT_SIZE")
            self._mmap_static = open_section("static", "STATIC_STRUCT_SIZE")
        except GameNotRunningError:
            # Clean up any partially opened maps
            self._cleanup_mmaps()
            raise

    def _cleanup_mmaps(self) -> None:
        """Close all memory maps."""
        for attr in ("_mmap_physics", "_mmap_graphics", "_mmap_static"):
            mm = getattr(self, attr, None)
            if mm is not None:
                try:
                    mm.close()
                except Exception:
                    pass  # Best effort
                setattr(self, attr, None)

    def _validate_physics(self, physics: PhysicsData) -> None:
        """Validate physics data ranges to catch corrupted memory reads.

        Raises:
            DataParseError: If any value is outside plausible bounds.
        """
        # Hard bounds based on typical car physics
        if not (0 <= physics.rpm <= 20000):
            raise DataParseError(f"RPM out of range: {physics.rpm}", field="rpm", value=physics.rpm)

        if not (0.0 <= physics.speed <= 400.0):
            raise DataParseError(f"Speed out of range: {physics.speed}", field="speed", value=physics.speed)

        if not (-5 <= physics.gear <= 10):
            raise DataParseError(f"Gear out of range: {physics.gear}", field="gear", value=physics.gear)

        if not (0.0 <= physics.throttle <= 1.0):
            raise DataParseError(f"Throttle out of range: {physics.throttle}", field="throttle", value=physics.throttle)

        if not (0.0 <= physics.brake <= 1.0):
            raise DataParseError(f"Brake out of range: {physics.brake}", field="brake", value=physics.brake)

        if not (0.0 <= physics.clutch <= 1.0):
            raise DataParseError(f"Clutch out of range: {physics.clutch}", field="clutch", value=physics.clutch)

        if not (-900.0 <= physics.steering <= 900.0):
            raise DataParseError(f"Steering angle out of range: {physics.steering}", field="steering", value=physics.steering)

        # Tire pressures (10-50 PSI typical)
        for i, pressure in enumerate(physics.tire_pressure):
            if not (10.0 <= pressure <= 50.0):
                raise DataParseError(
                    f"Tire pressure {i} out of range: {pressure}",
                    field=f"tire_pressure[{i}]",
                    value=pressure
                )

        # Fuel level (0 to capacity+margin)
        if physics.fuel_level < 0:
            raise DataParseError(f"Fuel level negative: {physics.fuel_level}", field="fuel_level", value=physics.fuel_level)

        # Lap time (0 to 24 hours theoretically)
        if not (0.0 <= physics.lap_time <= 86400.0):
            raise DataParseError(f"Lap time out of range: {physics.lap_time}", field="lap_time", value=physics.lap_time)

    def read(self) -> tuple[PhysicsData, GraphicsData, StaticData]:
        """Read latest telemetry from shared memory.

        For Phase 1 scaffold, this returns placeholder zero-filled data.
        Full parsing implementation will be in Phase 2.

        Returns:
            Tuple of (physics, graphics, static) data objects.

        Raises:
            GameNotRunningError: If game is not running or memory inaccessible.
            SharedMemoryDisconnectedError: If connection lost during read.
            DataParseError: If data is invalid.
        """
        with self._lock:
            # Ensure variant is detected and memory maps are open
            if not self._connected:
                try:
                    if self._game_variant is None:
                        self._game_variant = self._detect_game_variant()
                    self._open_memory_maps()
                    self._connected = True
                except GameNotRunningError as e:
                    self._connected = False
                    self._last_error = e
                    raise

            try:
                # Read raw bytes from each section
                physics_raw = self._mmap_physics.read(self.PHYSICS_STRUCT_SIZE)
                graphics_raw = self._mmap_graphics.read(self.GRAPHICS_STRUCT_SIZE)
                static_raw = self._mmap_static.read(self.STATIC_STRUCT_SIZE)

                # Reset position for next read
                self._mmap_physics.seek(0)
                self._mmap_graphics.seek(0)
                self._mmap_static.seek(0)

                # Parse binary data using ctypes structures
                try:
                    physics_ctypes = SPageFilePhysics.from_buffer_copy(physics_raw)
                    graphics_ctypes = SPageFileGraphics.from_buffer_copy(graphics_raw)
                    static_ctypes = SPageFileStatic.from_buffer_copy(static_raw)
                except Exception as e:
                    raise DataParseError(
                        f"Failed to parse shared memory structures: {e}"
                    ) from e

                # Convert to dataclasses
                physics = physics_from_ctypes(physics_ctypes)
                graphics = graphics_from_ctypes(graphics_ctypes)
                static = static_from_ctypes(static_ctypes)

                # Validate ranges
                self._validate_physics(physics)

                return physics, graphics, static

            except OSError as e:
                # Memory map became invalid (game closed)
                self._connected = False
                self._last_error = e
                self._cleanup_mmaps()
                raise SharedMemoryDisconnectedError(
                    f"Lost connection to shared memory: {e}"
                ) from e

    def disconnect(self) -> None:
        """Explicitly close memory maps and disconnect."""
        with self._lock:
            self._cleanup_mmaps()
            self._connected = False
            self._last_error = None

    def __del__(self) -> None:
        """Ensure cleanup on garbage collection."""
        self.disconnect()

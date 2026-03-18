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
        # Session state for realistic simulation
        self._lap_start_counter = 0  # Counter value at start of current lap
        self._last_lap_counter = 0   # Counter value at completion of last lap
        self._lap_times: list[float] = []  # Historical lap times
        # Auto-detect variant if not forced (mock always returns AC)
        if self._game_variant is None:
            self._game_variant = self._detect_game_variant()

    def read(self) -> tuple[PhysicsData, GraphicsData, StaticData]:
        """Generate realistic synthetic telemetry data.

        Simulates a proper race session:
        - First 3 laps: tires cold (60-80°C), lap times decreasing
        - After lap 3: tires reach operating temp (90-110°C)
        - Fuel decreases linearly
        - Lap times vary with slight random noise around a baseline
        - Throttle/brake patterns simulate actual driving (coasting, braking zones)
        """
        with self._lock:
            self._counter += 1
            t = self._counter * DEFAULT_POLL_INTERVAL

            # Time-based sine wave for smooth variations (simulates lap progression)
            time_wave = (t % 60) / 60.0 * 2 * 3.14159

            # === RPM and Speed with more realistic envelope ===
            # RPM oscillates between idle and redline based on track position
            rpm_base = 2000 + 13000 * (0.3 + 0.7 * abs((t % 20) / 20.0 - 0.5) * 2)
            rpm_noise = 200 * (0.5 - 0.5 * (t % 1))  # vibration effect
            rpm = int(rpm_base + rpm_noise)

            # Speed correlates with gear and RPM, but also varies by track position
            speed_base = 180.0 * (rpm / 15000)  # 0-180 km/h proportional to RPM
            speed = max(0.0, speed_base + 30.0 * (t % 5) / 5.0 - 15.0)  # ±30 variation

            # Gear calculation based on speed (more realistic)
            if speed < 40:
                gear = 1
            elif speed < 80:
                gear = 2
            elif speed < 120:
                gear = 3
            elif speed < 160:
                gear = 4
            elif speed < 200:
                gear = 5
            else:
                gear = 6

            # Throttle and brake are anti-correlated with some randomness
            # Simulate: accelerating on straights, braking at corners
            throttle_phase = (t % 15) / 15.0
            if throttle_phase < 0.6:
                throttle = 0.7 + 0.3 * (throttle_phase / 0.6)
                brake = 0.0
            else:
                throttle = 0.0
                brake = 0.6 + 0.4 * ((throttle_phase - 0.6) / 0.4)

            # Lap counting: a lap takes about 90 seconds at 60Hz = ~5400 counter steps
            LAP_COUNTER_STEPS = int(90 / DEFAULT_POLL_INTERVAL)  # ~5400
            lap = self._counter // LAP_COUNTER_STEPS
            lap_elapsed = (self._counter % LAP_COUNTER_STEPS) * DEFAULT_POLL_INTERVAL

            # Lap time: base 88 seconds (good lap) + noise + first 3 laps slower
            base_lap_time = 88.0 if lap >= 3 else 92.0 - lap * 1.5  # improvement over first laps
            lap_time = base_lap_time + 0.5 * (t % 10)  # small variations

            # Track last lap time when lap completes
            if self._counter > 0 and self._counter % LAP_COUNTER_STEPS == 0:
                self._last_lap_counter = self._counter
                self._lap_times.append(lap_time)
                if len(self._lap_times) > 5:
                    self._lap_times = self._lap_times[-5:]

            # Best lap time is the minimum of historical laps
            best_lap_time = min(self._lap_times) if self._lap_times else base_lap_time
            delta_to_best = lap_time - best_lap_time

            # Tire temperatures: after 3 laps, they heat up to 90-110°C range
            warmup_factor = min(1.0, max(0.0, (lap - 2) / 2.0))  # 0 for laps 0-2, ramp to 1 by lap 4
            base_temp = 65.0 + 45.0 * warmup_factor  # 65°C cold, 110°C hot
            # Add variation per tire and per section (inner/center/outer)
            tire_temps = []
            for i in range(4):
                # Front tires hotter due to braking
                base_offset = 5.0 if i < 2 else -5.0
                inner = base_temp + base_offset + 3.0
                center = base_temp + base_offset
                outer = base_temp + base_offset - 3.0
                tire_temps.append([inner, center, outer])

            # Flatten to 12-element array
            tire_temperature_flat = [temp for tire in tire_temps for temp in tire]

            # Tire pressures: slightly dropping as tires wear/heated
            pressures = [32.0 - 0.1 * lap, 32.0 - 0.1 * lap, 30.5 - 0.05 * lap, 30.5 - 0.05 * lap]

            # Fuel level: linear consumption ~2.5L per lap
            fuel_level = 120.0 - lap * 2.5 - (lap_elapsed / 90.0) * 2.5
            fuel_level = max(0.0, fuel_level)

            physics = PhysicsData(
                rpm=rpm,
                speed=speed,
                gear=gear,
                throttle=throttle,
                brake=brake,
                clutch=0.0,
                steering=10.0 * (t % 3 - 1.5),  # ±15° steering
                pos_x=0.0,
                pos_y=0.0,
                pos_z=0.0,
                vel_x=speed / 3.6,
                vel_y=0.0,
                vel_z=0.0,
                acc_x=0.0,
                acc_y=0.0,
                acc_z=0.0,
                tire_pressure=pressures,
                tire_temperature=tire_temperature_flat,
                tire_wear=[0.02 * lap, 0.02 * lap, 0.015 * lap, 0.015 * lap],
                suspension_position=[0.0, 0.0, 0.0, 0.0],
                suspension_velocity=[0.0, 0.0, 0.0, 0.0],
                front_wing_setting=2,
                rear_wing_setting=3,
                fuel_level=fuel_level,
                lap=lap + 1,
                lap_time=lap_time,
                sector=1,
                is_on_track=True,
                is_rewinding=False,
            )

            graphics = GraphicsData(
                display_speed=speed,
                display_rpm=rpm,
                display_gear=gear,
                shift_light=rpm > 13000,
                rev_limiter=rpm > 14500,
                current_lap=lap + 1,
                total_laps=10,
                current_lap_time=lap_time,
                last_lap_time=self._last_lap_counter / LAP_COUNTER_STEPS if self._last_lap_counter else 0.0,
                best_lap_time=best_lap_time,
                delta_to_best=delta_to_best,
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
                tire_size=[305.0, 30.0, 18.0] * 4,
                driver_name="Test Driver",
                driver_nationality="ITA",
                session_type=2,
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

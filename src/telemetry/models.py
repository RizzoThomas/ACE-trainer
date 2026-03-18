"""Data structures for telemetry readings.

These dataclasses represent the parsed binary structures from shared memory.
All fields should be populated according to the PDF specification.

Note: Field names and types must match the shared memory layout exactly.
Units: RPM (revolutions per minute), speed (km/h), pressures (PSI or kPa),
       temperatures (Celsius), angles (degrees).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
import ctypes

from .constants import GameVariant

# ============================================================================
# Ctypes Structures (Binary Layout)
# ============================================================================


class SPageFilePhysics(ctypes.Structure):
    """Binary layout of Assetto Corsa physics shared memory.

    This must match the PDF specification exactly. Field order and packing
    are critical — use standard packing (no alignment hints).
    """

    _fields_ = [
        # Basic telemetry
        ("rpm", ctypes.c_int),
        ("speed", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("throttle", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("clutch", ctypes.c_float),
        ("steering", ctypes.c_float),

        # Position and motion
        ("pos_x", ctypes.c_float),
        ("pos_y", ctypes.c_float),
        ("pos_z", ctypes.c_float),
        ("vel_x", ctypes.c_float),
        ("vel_y", ctypes.c_float),
        ("vel_z", ctypes.c_float),
        ("acc_x", ctypes.c_float),
        ("acc_y", ctypes.c_float),
        ("acc_z", ctypes.c_float),

        # Tire data (4 tires: FL, FR, RL, RR)
        # Each tire: pressure, temperature[3] (inner, center, outer), wear
        ("tire_pressure", ctypes.c_float * 4),
        ("tire_temperature", ctypes.c_float * 12),  # 4 tires × 3 temps
        ("tire_wear", ctypes.c_float * 4),

        # Suspension (4 corners)
        ("suspension_position", ctypes.c_float * 4),
        ("suspension_velocity", ctypes.c_float * 4),

        # Aero
        ("front_wing_setting", ctypes.c_int),
        ("rear_wing_setting", ctypes.c_int),

        # Fuel
        ("fuel_level", ctypes.c_float),

        # Lap info
        ("lap", ctypes.c_int),
        ("lap_time", ctypes.c_float),
        ("sector", ctypes.c_int),

        # Car state flags
        ("is_on_track", ctypes.c_bool),
        ("is_rewinding", ctypes.c_bool),
    ]


class SPageFileGraphics(ctypes.Structure):
    """Binary layout of Assetto Corsa graphics shared memory."""

    _fields_ = [
        # Basic display data
        ("display_speed", ctypes.c_float),
        ("display_rpm", ctypes.c_int),
        ("display_gear", ctypes.c_int),
        ("shift_light", ctypes.c_bool),
        ("rev_limiter", ctypes.c_bool),

        # Lap and session
        ("current_lap", ctypes.c_int),
        ("total_laps", ctypes.c_int),
        ("current_lap_time", ctypes.c_float),
        ("last_lap_time", ctypes.c_float),
        ("best_lap_time", ctypes.c_float),
        ("delta_to_best", ctypes.c_float),

        # Flags and status
        ("flag", ctypes.c_int),
        ("pit_limiter", ctypes.c_bool),
        ("yellow_danger", ctypes.c_bool),

        # Position in race
        ("race_position", ctypes.c_int),
        ("total_competitors", ctypes.c_int),
    ]


class SPageFileStatic(ctypes.Structure):
    """Binary layout of Assetto Corsa static shared memory."""

    _fields_ = [
        # Car model
        ("car_model", ctypes.c_char * 64),
        ("car_skins", ctypes.c_int),

        # Tire compound
        ("tire_compound", ctypes.c_char * 32),
        # Tire size: width, ratio, diameter for each tire (4 tires)
        ("tire_size", ctypes.c_float * 12),  # 4 × 3

        # Driver
        ("driver_name", ctypes.c_char * 64),
        ("driver_nationality", ctypes.c_char * 32),

        # Session
        ("session_type", ctypes.c_int),
        ("track_name", ctypes.c_char * 128),
        ("track_length", ctypes.c_float),
        ("weather", ctypes.c_char * 32),

        # Performance metrics
        ("max_rpm", ctypes.c_int),
        ("max_speed", ctypes.c_float),
        ("fuel_capacity", ctypes.c_float),
    ]


# ============================================================================
# Conversion Utilities
# ============================================================================


def physics_from_ctypes(physics_struct: SPageFilePhysics) -> PhysicsData:
    """Convert ctypes physics structure to dataclass.

    Args:
        physics_struct: Parsed ctypes structure from shared memory.

    Returns:
        PhysicsData instance with converted types.
    """
    # Convert tire_temperature from flat 12-element array to list of 4 lists of 3
    temp_flat = list(physics_struct.tire_temperature)
    tire_temp_nested = [temp_flat[i*3:(i+1)*3] for i in range(4)]

    return PhysicsData(
        rpm=physics_struct.rpm,
        speed=physics_struct.speed,
        gear=physics_struct.gear,
        throttle=physics_struct.throttle,
        brake=physics_struct.brake,
        clutch=physics_struct.clutch,
        steering=physics_struct.steering,
        pos_x=physics_struct.pos_x,
        pos_y=physics_struct.pos_y,
        pos_z=physics_struct.pos_z,
        vel_x=physics_struct.vel_x,
        vel_y=physics_struct.vel_y,
        vel_z=physics_struct.vel_z,
        acc_x=physics_struct.acc_x,
        acc_y=physics_struct.acc_y,
        acc_z=physics_struct.acc_z,
        tire_pressure=list(physics_struct.tire_pressure),
        tire_temperature=tire_temp_nested,
        tire_wear=list(physics_struct.tire_wear),
        suspension_position=list(physics_struct.suspension_position),
        suspension_velocity=list(physics_struct.suspension_velocity),
        front_wing_setting=physics_struct.front_wing_setting,
        rear_wing_setting=physics_struct.rear_wing_setting,
        fuel_level=physics_struct.fuel_level,
        lap=physics_struct.lap,
        lap_time=physics_struct.lap_time,
        sector=physics_struct.sector,
        is_on_track=bool(physics_struct.is_on_track),
        is_rewinding=bool(physics_struct.is_rewinding),
    )


def graphics_from_ctypes(graphics_struct: SPageFileGraphics) -> GraphicsData:
    """Convert ctypes graphics structure to dataclass."""
    return GraphicsData(
        display_speed=graphics_struct.display_speed,
        display_rpm=graphics_struct.display_rpm,
        display_gear=graphics_struct.display_gear,
        shift_light=bool(graphics_struct.shift_light),
        rev_limiter=bool(graphics_struct.rev_limiter),
        current_lap=graphics_struct.current_lap,
        total_laps=graphics_struct.total_laps,
        current_lap_time=graphics_struct.current_lap_time,
        last_lap_time=graphics_struct.last_lap_time,
        best_lap_time=graphics_struct.best_lap_time,
        delta_to_best=graphics_struct.delta_to_best,
        flag=graphics_struct.flag,
        pit_limiter=bool(graphics_struct.pit_limiter),
        yellow_danger=bool(graphics_struct.yellow_danger),
        race_position=graphics_struct.race_position,
        total_competitors=graphics_struct.total_competitors,
    )


def static_from_ctypes(static_struct: SPageFileStatic) -> StaticData:
    """Convert ctypes static structure to dataclass.

    Handles byte strings by decoding to UTF-8, stripping null bytes.
    """
    def decode_bytes(b: bytes | ctypes.Array) -> str:
        """Decode ctypes char array to Python string."""
        if isinstance(b, ctypes.Array):
            b = bytes(b)
        return b.split(b'\x00')[0].decode('utf-8', errors='ignore')

    return StaticData(
        car_model=decode_bytes(static_struct.car_model),
        car_skins=static_struct.car_skins,
        tire_compound=decode_bytes(static_struct.tire_compound),
        tire_size=list(static_struct.tire_size),
        driver_name=decode_bytes(static_struct.driver_name),
        driver_nationality=decode_bytes(static_struct.driver_nationality),
        session_type=static_struct.session_type,
        track_name=decode_bytes(static_struct.track_name),
        track_length=static_struct.track_length,
        weather=decode_bytes(static_struct.weather),
        max_rpm=static_struct.max_rpm,
        max_speed=static_struct.max_speed,
        fuel_capacity=static_struct.fuel_capacity,
    )


# ============================================================================
# Physics Data
# ============================================================================


@dataclass
class PhysicsData:
    """Real-time physics telemetry from the car.

    This is the most comprehensive structure, containing suspension, aero,
    tire, and drivetrain data at high frequency (60-120 Hz).

    IMPORTANT: Field names, order, and types MUST match the PDF spec exactly.
    The following are PLACEHOLDER fields — replace with actual PDF fields.
    """

    # Basic telemetry
    rpm: int  # Engine RPM
    speed: float  # km/h
    gear: int  # Current gear (-1=reverse, 0=neutral, 1+=forward)
    throttle: float  # 0.0 to 1.0
    brake: float  # 0.0 to 1.0
    clutch: float  # 0.0 to 1.0
    steering: float  # degrees

    # Position and motion
    pos_x: float  # World coordinates
    pos_y: float
    pos_z: float
    vel_x: float  # Velocity m/s
    vel_y: float
    vel_z: float
    acc_x: float  # Acceleration m/s²
    acc_y: float
    acc_z: float

    # Tire data (4 tires: FL, FR, RL, RR)
    tire_pressure: list[float]  # PSI or kPa, len=4
    tire_temperature: list[float]  # Celsius, inner/outer/center, len=4*3?
    tire_wear: list[float]  # 0-1 wear factor, len=4

    # Suspension
    suspension_position: list[float]  # mm, len=4
    suspension_velocity: list[float]  # mm/s, len=4

    # Aero
    front_wing_setting: int  # Wing angle or DRS state
    rear_wing_setting: int

    # Fuel
    fuel_level: float  # Liters

    # Lap info
    lap: int
    lap_time: float  # Current lap time in seconds
    sector: int

    # Car state
    is_on_track: bool
    is_rewinding: bool  # When using flashback

    def validate(self) -> None:
        """Validate physics data against plausible ranges.

        Raises:
            DataParseError: If any value is out of expected range.
        """
        # TODO: Implement validation per PDF spec
        pass


# ============================================================================
# Graphics Data
# ============================================================================


@dataclass
class GraphicsData:
    """Display-oriented telemetry for UI and HUD.

    This structure is optimized for visualization and may include interpolated
    or derived values meant for driver display.

    IMPORTANT: Placeholder fields — replace with actual PDF specification.
    """

    # Basic display data
    display_speed: float  # km/h (may differ from physics speed)
    display_rpm: int
    display_gear: int
    shift_light: bool  # Indicates optimal shift point
    rev_limiter: bool

    # Lap and session
    current_lap: int
    total_laps: int
    current_lap_time: float  # seconds
    last_lap_time: float
    best_lap_time: float
    delta_to_best: float  # seconds (positive = slower)

    # Flags and status
    flag: int  # 0=None, 1=Green, 2=Blue, 3=Yellow, 4=Red, etc.
    pit_limiter: bool
    yellow_danger: bool

    # Position in race
    race_position: int
    total_competitors: int

    def validate(self) -> None:
        """Validate graphics data."""
        pass


# ============================================================================
# Static Data
# ============================================================================


@dataclass
class StaticData:
    """Immutable car and session metadata.

    This data changes infrequently (only when car/session setup changes).
    It includes vehicle specifications, tire compound, and session info.

    IMPORTANT: Placeholder fields — replace with actual PDF specification.
    """

    # Car model
    car_model: str  # e.g., "Ferrari 488 GT3"
    car_skins: int  # Number of available liveries

    # Tire compound
    tire_compound: str  # e.g., " slick", "wet", "intermediate"
    tire_size: list[float]  # Width, ratio, rim diameter for each tire

    # Driver
    driver_name: str
    driver_nationality: str

    # Session
    session_type: int  # 0=practice, 1=qualifying, 2=race, etc.
    track_name: str
    track_length: float  # meters
    weather: str  # e.g., "Clear", "Cloudy", "Rain"

    # Performance metrics
    max_rpm: int
    max_speed: float  # km/h
    fuel_capacity: float  # liters

    def validate(self) -> None:
        """Validate static data."""
        pass


# ============================================================================
# TypedDict for raw dictionary output (optional)
# ============================================================================


class PhysicsDict(TypedDict):
    """TypedDict representation of physics data for JSON serialization."""

    rpm: int
    speed: float
    gear: int
    throttle: float
    brake: float
    clutch: float
    steering: float
    pos_x: float
    pos_y: float
    pos_z: float
    vel_x: float
    vel_y: float
    vel_z: float
    acc_x: float
    acc_y: float
    acc_z: float
    tire_pressure: list[float]
    tire_temperature: list[float]
    tire_wear: list[float]
    suspension_position: list[float]
    suspension_velocity: list[float]
    front_wing_setting: int
    rear_wing_setting: int
    fuel_level: float
    lap: int
    lap_time: float
    sector: int
    is_on_track: bool
    is_rewinding: bool


class GraphicsDict(TypedDict):
    """TypedDict representation of graphics data."""

    display_speed: float
    display_rpm: int
    display_gear: int
    shift_light: bool
    rev_limiter: bool
    current_lap: int
    total_laps: int
    current_lap_time: float
    last_lap_time: float
    best_lap_time: float
    delta_to_best: float
    flag: int
    pit_limiter: bool
    yellow_danger: bool
    race_position: int
    total_competitors: int


class StaticDict(TypedDict):
    """TypedDict representation of static data."""

    car_model: str
    car_skins: int
    tire_compound: str
    tire_size: list[float]
    driver_name: str
    driver_nationality: str
    session_type: int
    track_name: str
    track_length: float
    weather: str
    max_rpm: int
    max_speed: float
    fuel_capacity: float

# Python Code Style Guide

This document defines the coding standards for the Assetto telemetry tracker project. All Python code must adhere to these guidelines.

## Table of Contents

- [General Principles](#general-principles)
- [Code Formatting](#code-formatting)
- [Naming Conventions](#naming-conventions)
- [Imports](#imports)
- [Type Hints](#type-hints)
- [Functions and Methods](#functions-and-methods)
- [Classes](#classes)
- [Error Handling](#error-handling)
- [Comments and Documentation](#comments-and-documentation)
- [Qt/PyQt Specific Guidelines](#qtpyqt-specific-guidelines)
- [Testing Guidelines](#testing-guidelines)

## General Principles

1. **Readability First** — Code is read more often than written. Prioritize clarity over cleverness.
2. **Explicit over Implicit** — Avoid magic numbers, hidden side effects, or opaque patterns.
3. **Single Responsibility** — Each function/class should do one thing well.
4. **DRY (Don't Repeat Yourself)** — Extract repeated logic into reusable functions.
5. **Fail Fast** — Validate inputs early, raise errors immediately when something is wrong.

## Code Formatting

We use **Black** for automatic code formatting with the following configuration:

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
```

- **Line length**: 88 characters (Black default)
- **Always format before committing**: Run `black .` or use pre-commit hook
- **No manual formatting** — let Black handle it

**Example**:
```python
# BLACK FORMATTED (good)
def calculate_rpm_per_gear(
    telemetry_data: list[float], gear: int
) -> float:
    return sum(telemetry_data) / len(telemetry_data)

# MANUALLY FORMATTED (bad - will be reformatted)
def calculateRPM(telemetry, gear):
    total=0
    for value in telemetry:
        total+=value
    return total/len(telemetry)
```

## Naming Conventions

### Variables and Functions

- **snake_case** for variables, functions, methods
- Use descriptive names, avoid single letters except in loops (`i`, `x`, `y`)
- Boolean variables should start with `is_`, `has_`, `can_`, `should_`

```python
# Good
current_rpm = 6500
is_shift_light_active = True
calculate_lap_time()
get_telemetry_data()

# Bad
rpm = 6500
active = True
calc_lt()
data = get_data()
```

### Classes

- **PascalCase** (CapWords) for classes
- Use nouns or noun phrases

```python
class TelemetryReader:
    pass

class LapTimer:
    pass

class GearIndicator:
    pass
```

### Constants

- **UPPER_SNAKE_CASE** for module-level constants
- Place at top of module

```python
MAX_RPM = 15000
GEAR_RATIOS = [3.5, 2.1, 1.6, 1.3, 1.0, 0.85, 0.75]
SHARED_MEMORY_TIMEOUT = 0.1  # seconds
```

### File Names

- **snake_case.py** for modules
- Single purpose per file
- Group related functionality

```
telemetry/
  __init__.py
  reader.py          # Shared memory reading
  parser.py          # Data parsing and validation
  models.py          # Data classes and structures
  exporter.py        # Export to CSV/JSON
```

## Imports

### Order (conforming to PEP 8 and isort)

1. **Standard library** imports (sorted alphabetically)
2. **Third-party** imports (sorted alphabetically)
3. **Local application** imports (sorted alphabetically)
4. Blank lines between each group
5. Within each group: absolute imports before relative

```python
# Standard library
import ctypes
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Third-party
import numpy as np
import pandas as pd
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout

# Local
from .models import TelemetryData
from .reader import SharedMemoryReader
from .exporter import export_to_csv
```

### Explicit relative imports for intra-package

```python
# Good
from .reader import SharedMemoryReader
from ..utils import format_time

# Bad (avoid inside package)
import sys
sys.path.insert(0, '..')
from utils import format_time
```

## Type Hints

**Use type hints for all function signatures and variables** (except obvious ones). Enable `mypy` for static type checking.

```python
from typing import TypedDict, Optional, Callable
import numpy.typing as npt

class TelemetryPoint(TypedDict):
    """Structure for a single telemetry reading."""
    rpm: int
    speed: float  # km/h
    gear: int
    timestamp: float

def process_telemetry(
    data: list[TelemetryPoint],
    max_samples: int = 1000
) -> npt.NDArray[np.float64]:
    """Process telemetry data into numpy array."""
    return np.array([d['rpm'] for d in data], dtype=np.float64)

def get_gear_indicator_color(
    gear: int,
    max_gear: int = 7
) -> str:
    """Return color for gear indicator based on RPM."""
    if gear == max_gear:
        return '#FF0000'  # Red for top gear
    return '#00FF00'  # Green otherwise
```

## Functions and Methods

### Small and Focused

- Functions should be **under 50 lines** (preferably under 30)
- One level of abstraction per function
- Extract nested logic into helper functions

```python
# Good — single responsibility
def read_shared_memory() -> TelemetryData:
    """Read latest telemetry from shared memory."""
    raw = _read_raw_bytes()
    parsed = _parse_shared_memory(raw)
    return TelemetryData.from_dict(parsed)

def _read_raw_bytes() -> bytes:
    """Read raw bytes from shared memory segment."""
    pass

def _parse_shared_memory(raw: bytes) -> dict[str, Any]:
    """Parse binary shared memory format."""
    pass
```

### Docstrings

Use **Google style** docstrings:

```python
def calculate_lap_time(split_times: list[float]) -> str:
    """Calculate formatted lap time from split times.

    Args:
        split_times: List of sector split times in seconds

    Returns:
        Formatted lap time string (MM:SS.mmm)

    Raises:
        ValueError: If split_times is empty or contains negative values
    """
    if not split_times:
        raise ValueError("At least one split time required")

    total = sum(split_times)
    minutes = int(total // 60)
    seconds = total % 60
    return f"{minutes:02d}:{seconds:06.3f}"
```

## Classes

### Data Classes for Simple Structures

Use `@dataclass` for simple data containers:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Lap:
    """Represents a single lap."""
    lap_number: int
    time: float  # seconds
    sector_times: list[float]
    date: datetime
    is_valid: bool = True  # default value

    def formatted_time(self) -> str:
        """Return formatted lap time."""
        minutes = int(self.time // 60)
        seconds = self.time % 60
        return f"{minutes}:{seconds:06.3f}"
```

### Inheritance and Composition

- Prefer **composition** over inheritance
- Use inheritance only for true "is-a" relationships with shared behavior
- Multiple inheritance should be avoided

```python
# Good — composition
class TelemetryDisplay:
    def __init__(
        self,
        reader: SharedMemoryReader,
        plotter: TelemetryPlotter
    ):
        self.reader = reader
        self.plotter = plotter

# Bad — deep inheritance hierarchy
class Car:
    pass

class AssettoCar(Car):
    pass

class ACCCar(AssettoCar):
    pass
```

## Error Handling

### Exceptions, Not Return Codes

Use exceptions for error conditions. Never return `None` or `-1` on error unless it's a documented sentinel value.

```python
# Good
def read_shared_memory(path: str) -> bytes:
    """Read shared memory segment."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except FileNotFoundError as e:
        raise RuntimeError(f"Shared memory not found: {path}") from e
    except PermissionError as e:
        raise RuntimeError(f"Permission denied reading: {path}") from e

# Bad
def read_shared_memory(path: str) -> bytes | None:
    if file_exists(path):
        return read(path)
    else:
        return None  # caller must remember to check!
```

### Custom Exception Types

Define project-specific exceptions for common error categories:

```python
class TelemetryError(Exception):
    """Base exception for telemetry-related errors."""
    pass

class SharedMemoryError(TelemetryError):
    """Raised when shared memory access fails."""
    pass

class DataParseError(TelemetryError):
    """Raised when telemetry data is malformed."""
    pass

class GameNotRunningError(SharedMemoryError):
    """Raised when target game process is not found."""
    pass
```

### Context Managers for Resources

Use `with` statements for cleanup:

```python
# Good
class SharedMemory:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        pass

# Usage
with SharedMemory() as sm:
    data = sm.read()

# Bad — manual cleanup required, error-prone
sm = SharedMemory()
try:
    data = sm.read()
finally:
    sm.cleanup()
```

## Comments and Documentation

### When to Comment

- **Why something is done** (not what — the code shows that)
- Complex algorithms or non-obvious optimizations
- Workarounds for bugs in external libraries
- TODOs with clear action items

### What NOT to Comment

- Obvious code
- Restating the function name in sentence form

```python
# Good — explains the "why"
# Using shared memory mapping instead of regular file IO
# because the game updates the buffer in-place and we need
# to see changes without reopening the handle
mmap = open_mmap()

# Bad — states the obvious
# Set the gear to 1
gear = 1
```

### Module-Level Docstrings

Every module should have a docstring at the top:

```python
"""Shared memory reader for Assetto Corsa telemetry.

This module provides the SharedMemoryReader class which connects
to the game's shared memory segment and extracts telemetry data
in a structured format.

Supported games:
- Assetto Corsa
- Assetto Corsa Competizione
- Assetto Corsa Evo (experimental)

Example:
    >>> reader = SharedMemoryReader()
    >>> data = reader.read()
    >>> print(data.rpm)
    6500
"""
```

## Qt/PyQt Specific Guidelines

### Signal/Slot Connections

Use the new-style signal/slot syntax (not the old string-based syntax):

```python
# Good — type-safe, IDE can track
from PyQt6.QtCore import pyqtSignal

class TelemetryWorker(QObject):
    data_updated = pyqtSignal(TelemetryData)

    def run(self):
        data = self.reader.read()
        self.data_updated.emit(data)

# Usage
worker.data_updated.connect(self.on_data_updated)

# Bad — old string-based syntax
self.connect(worker, SIGNAL('data_updated'), self.on_data_updated)
```

### Threading

Long-running operations (shared memory polling, file I/O) must run in separate threads to avoid blocking the UI:

```python
from PyQt6.QtCore import QThread, pyqtSignal

class TelemetryThread(QThread):
    data_ready = pyqtSignal(TelemetryData)

    def run(self) -> None:
        while not self.isInterruptionRequested():
            data = self.reader.read()
            self.data_ready.emit(data)
            time.sleep(0.016)  # ~60 Hz

# In main window
self.thread = TelemetryThread()
self.thread.data_ready.connect(self.update_display)
self.thread.start()
```

### Widget Layouts

Use layout managers (QVBoxLayout, QHBoxLayout, QGridLayout) — never set absolute positions:

```python
# Good
layout = QVBoxLayout()
layout.addWidget(self.rpm_gauge)
layout.addWidget(self.speed_display)
self.setLayout(layout)

# Bad
self.rpm_gauge.move(10,–10)
self.speed_display.move(10, 100)
```

## Testing Guidelines

### Test File Naming

- Test files: `test_<module>.py`
- Located in `tests/` directory mirroring package structure

```
src/
  telemetry/
    reader.py
tests/
  telemetry/
    test_reader.py
```

### Test Structure

Use pytest with standard setup:

```python
import pytest
from telemetry.reader import SharedMemoryReader
from telemetry.models import TelemetryData

class TestSharedMemoryReader:
    """Tests for SharedMemoryReader class."""

    def test_read_returns_valid_data(self) -> None:
        """Test that read() returns TelemetryData."""
        reader = SharedMemoryReader()
        data = reader.read()

        assert isinstance(data, TelemetryData)
        assert data.rpm >= 0
        assert 0 <= data.speed <= 500

    def test_read_raises_on_missing_game(self) -> None:
        """Test that read() raises when game is not running."""
        reader = SharedMemoryReader()
        # Simulate game not running
        with pytest.raises(GameNotRunningError):
            reader.read()

    @pytest.mark.parametrize(
        "gear,rpm,expected",
        [
            (1, 1000, "green"),
            (7, 8000, "red"),
            (3, 4500, "green"),
        ],
    )
    def test_gear_indicator_color(
        self,
        gear: int,
        rpm: int,
        expected: str
    ) -> None:
        """Test gear indicator color logic."""
        color = get_gear_indicator_color(gear, rpm)
        assert color == expected
```

### Fixtures

Use pytest fixtures for reusable test objects:

```python
import pytest
from telemetry.reader import SharedMemoryReader
from telemetry.models import TelemetryData

@pytest.fixture
def mock_shared_memory(monkeypatch):
    """Mock shared memory reader for testing."""
    def mock_read(self) -> TelemetryData:
        return TelemetryData(
            rpm=6500,
            speed=150.0,
            gear=3,
            timestamp=time.time()
        )
    monkeypatch.setattr(SharedMemoryReader, "read", mock_read)
    return SharedMemoryReader()

def test_display_updates(mock_shared_memory):
    data = mock_shared_memory.read()
    assert data.rpm == 6500
```

## Performance Considerations

- Use NumPy arrays for bulk numerical operations
- Avoid creating large temporary lists; use generators where appropriate
- Cache expensive computations if they'll be reused
- Profile with `cProfile` or `py-spy` to identify bottlenecks

## Pre-commit Hooks

Recommended `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-bugbear==24.4.26]

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        pass_filenames: false
        always_run: true
```

Run `pre-commit install` to enable.

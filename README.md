# Assetto Telemetry Tracker

A high-performance, Python-based telemetry tracker for Assetto Corsa, Assetto Corsa Competizione (ACC), and Assetto Corsa Evo.

## Features

- **Real-time telemetry**: Read engine RPM, vehicle speed, gear, tire pressures, and more directly from game shared memory
- **Multiple game support**: Works with AC, ACC, and AC Evo (auto-detects which game is running)
- **Thread-safe design**: Run the reader in a background thread without data corruption
- **Hot-plugging**: Automatically detects when game starts or stops
- **Mock mode**: Develop UI without the game running using synthetic data
- **Zero external dependencies**: Pure Python with `mmap` and `struct` for maximum compatibility

## Project Structure

This is a **Conductor-managed** project. Track progress with:

- `conductor/` — Project management artifacts
- `conductor/tracks/` — Feature tracks (current work)
- `src/telemetry/` — Core telemetry library (this package)
- `tests/` — Unit and integration tests

## Quick Start

### Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (including dev)
uv sync --dev
```

### Basic Usage

```python
from telemetry.reader import SharedMemoryReader, MockSharedMemoryReader

# Use mock mode for UI development (no game required)
reader = MockSharedMemoryReader()
physics, graphics, static = reader.read()
print(f"RPM: {physics.rpm}, Speed: {graphics.display_speed}")

# Use real reader when game is running
# reader = SharedMemoryReader()
# try:
#     physics, graphics, static = reader.read()
#     print(f"RPM: {physics.rpm}")
# except GameNotRunningError:
#     print("Game is not running")
```

### Running Tests

```bash
pytest                    # Run all tests
pytest -v                 # Verbose
pytest --cov=telemetry    # With coverage report
```

### Code Quality

```bash
black src tests          # Format code
ruff check .             # Lint
mypy src/telemetry       # Type check
```

## Development Workflow

This project uses **Conductor** for task and workflow management.

1. **View active tracks**:
   ```bash
   /conductor:tracks
   ```

2. **Create a new feature**:
   ```bash
   /conductor:new-track "feature description"
   ```

3. **Track progress**:
   ```bash
   /conductor:status
   ```

4. **Update task completion**:
   ```bash
   /conductor:task update --id <task-id> --status done
   ```

Current active track: [shared-memory-core_20250318](./conductor/tracks/shared-memory-core_20250318/)

## Technical Details

### Shared Memory Architecture

The reader connects to Windows shared memory segments created by each game. The memory layout (binary struct definition) is different for AC, ACC, and AC Evo. We define data structures in `src/telemetry/models.py` that must match the PDF specification exactly.

- **Physics**: High-frequency car data (60-120 Hz): suspension, aero, tires, drivetrain
- **Graphics**: Display-oriented data for HUD: speed, RPM, gear, flags
- **Static**: Immutable session/car metadata: car model, track, tire compound

### Thread Safety

The reader is designed to run in a background thread polling at ~60Hz. All public methods use a reentrant lock (`threading.RLock`) to prevent race conditions. The `read()` method is non-blocking when connected (< 1ms typical).

### Hot-Plugging

The reader detects when the game starts or stops via memory map availability. If the game closes while the reader is active, `SharedMemoryDisconnectedError` is raised on the next read, allowing graceful reconnection.

### Mock Mode

`MockSharedMemoryReader` provides deterministic, realistic synthetic data for UI development. It simulates varying RPM, speed, gear changes, and tire pressures over time. This allows developers to work without the game running.

## Current Implementation Status

**Phase 1: Project Foundation** — In Progress

- [x] Package structure created
- [x] Exception hierarchy defined
- [x] Constants and game variants
- [x] Data models (placeholders pending PDF spec)
- [x] Abstract reader interface
- [x] Mock reader implementation
- [x] Windows mmap scaffold (Phase 2 will fill parsing)
- [x] Unit tests covering core interfaces
- [ ] PDF spec analysis to fill exact struct layouts

## Build for Distribution

To create a standalone Windows .exe:

```bash
uv add pyinstaller
pyinstaller --onefile --name telemetry-reader src/telemetry/__init__.py
```

(Full packaging configuration to be added later.)

## License

MIT

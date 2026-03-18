# Implementation Plan: Shared Memory Core Module

**Track ID:** shared-memory-core_20250318
**Spec:** [spec.md](./spec.md)
**Created:** 2025-03-18
**Status:** [ ] Not Started

## Overview

We will build the SharedMemoryReader module in 4 phases:
1. **Foundation** — Set up project structure, interfaces, and basic mmap scaffolding
2. **Core Parsing** — Implement binary data structures and parsing for Physics/Graphics/Static
3. **Robustness** — Add hot-plugging detection, thread-safety, game variant auto-detection
4. **Mock & Test** — Create mock mode and comprehensive test suite

Each phase is independently verifiable.

---

## Phase 1: Project Foundation

**Goal:** Establish module structure, interfaces, and basic mmap connection scaffolding.

### Tasks

- [ ] Create package structure: `src/telemetry/` with `__init__.py`, `reader.py`, `models.py`, `constants.py`
- [ ] Define base `SharedMemoryReader` abstract class with methods: `read()`, `is_connected()`, `disconnect()`
- [ ] Define data classes using `@dataclass`: `PhysicsData`, `GraphicsData`, `StaticData` with all fields from PDF (placeholders initially)
- [ ] Implement basic mmap opening: locate shared memory file path for AC/ACC/AC Evo (based on PDF), open read-only mmap
- [ ] Add connection state tracking (boolean flag, last error)
- [ ] Implement basic exception hierarchy: `TelemetryError`, `SharedMemoryError`, `GameNotRunningError`, `DataParseError`
- [ ] Write initial unit tests for `SharedMemoryReader` interface (mocking mmap)

### Verification

- [ ] Module structure matches Python style guide (from `conductor/code_styleguides/python.md`)
- [ ] All public methods have proper type hints and docstrings
- [ ] Unit tests can import and instantiate `SharedMemoryReader` (even though parsing is not yet implemented)
- [ ] Exception classes raise correctly with informative messages

---

## Phase 2: Core Binary Parsing

**Goal:** Implement complete binary parsing of Physics, Graphics, and Static structures using `struct` or `ctypes.Structure`.

### Tasks

- [ ] **Analyze PDF documentation** thoroughly to extract exact struct layouts (field names, types, offsets, sizes)
- [ ] Choose implementation approach:
  - Option A: `struct.unpack` with format strings (simpler, explicit)
  - Option B: `ctypes.Structure` subclasses (automatic offset calculation)
  - Document choice in code with rationale
- [ ] Implement parsing for **StaticData** (usually simplest — car setup, tire compound, etc.)
- [ ] Implement parsing for **GraphicsData** (telemetry for display — speed, RPM, gear, flag, etc.)
- [ ] Implement parsing for **PhysicsData** (most complex — suspension, aero, tire pressures, temperatures, etc.)
- [ ] Add unit conversion if needed (some games use different units — e.g., pressure in PSI vs kPa)
- [ ] Ensure each `read()` call returns fresh data (no caching unless explicitly designed)
- [ ] Write comprehensive unit tests with sample binary blobs (from PDF examples or crafted manually)
- [ ] Test against actual game data if available (optional, but preferred)

### Verification

- [ ] All fields from PDF spec are present in data classes with correct Python types (int, float, bool)
- [ ] Unit tests validate parsing against known binary patterns
- [ ] Parsed values match expected ranges (e.g., RPM 0-15000, speed 0-400 km/h)
- [ ] Out-of-range or malformed binary data raise `DataParseError` with descriptive message
- [ ] `reader.read()` returns `PhysicsData`, `GraphicsData`, `StaticData` instances with populated fields

---

## Phase 3: Robustness & Reliability

**Goal:** Add hot-plugging (game start/stop detection), thread-safety, and game variant auto-detection.

### Tasks

- [ ] Implement **game process detection**: check if shared memory file exists and is accessible; raise `GameNotRunningError` if missing
- [ ] Implement **polling loop** concept: `read()` should handle `FileNotFoundError` gracefully and set disconnected state
- [ ] Add **reconnection logic**: when game starts after being disconnected, automatically re-open mmap on next `read()` call
- [ ] Make reader **thread-safe**: add `threading.Lock` around mmap operations; document thread-safety guarantees
- [ ] Implement **game variant auto-detection**:
  - Distinguish AC vs ACC vs AC Evo based on memory layout differences (e.g., struct sizes, unique field values)
  - Provide `game_variant` property on reader
  - Allow user to force a variant if auto-detection fails (via constructor parameter)
- [ ] Add **configurable polling interval** (default 0.016s for ~60Hz) in case multiple readers are used
- [ ] Improve error messages: include which memory section failed, file path, and OS error details
- [ ] Add `timeout` parameter to `read()` to prevent indefinite blocking if game is stuck

### Verification

- [ ] Simulate game start: reader detects game, reads data successfully
- [ ] Simulate game stop: reader raises `GameNotRunningError` on next read, disconnects cleanly
- [ ] Simulate rapid start/stop: no crashes, no resource leaks (use `tracemalloc` or similar to check)
- [ ] Thread-safety test: spawn 4 threads all calling `read()` simultaneously for 1000 iterations; no exceptions or corrupted data
- [ ] Auto-detection: open AC memory, verify `game_variant == "AC"`; same for ACC and AC Evo (if test data available)
- [ ] Forced variant: instantiate reader with `variant="ACC"` even if AC memory present; verify it reads ACC layout

---

## Phase 4: Mock Mode & Testing

**Goal:** Create `MockSharedMemoryReader` for UI development and complete test coverage for the core module.

### Tasks

- [ ] Implement `MockSharedMemoryReader` subclass:
  - Override `read()` to return synthetic but realistic `PhysicsData`, `GraphicsData`, `StaticData`
  - Simulate varying RPM, speed, gear changes, tire pressures over time
  - Allow seed/configuration to produce deterministic data for reproducible tests
  - Should behave like real reader (raise same exceptions, same data shapes)
- [ ] Add **comprehensive unit tests** for `SharedMemoryReader`:
  - Test connection establishment and `is_connected()` state
  - Test `read()` returns correct types and non-None values
  - Test exception raising for disconnected state
  - Test hot-plugging scenarios (simulate with mocks)
  - Test thread-safety with concurrent reads
- [ ] Add **integration tests** (optional but ideal):
  - Spin up actual Assetto Corsa process (if available in CI environment) and verify real data
  - If game not available, use recorded memory dump files
- [ ] Write **module-level docstring** describing usage, supported games, performance characteristics, thread-safety guarantees
- [ ] Document **performance expectations**: typical CPU usage, memory footprint, update rate capabilities
- [ ] Add **example usage** in `__init__.py` or separate `example.py`:
  ```python
  from telemetry.reader import SharedMemoryReader

  reader = SharedMemoryReader()
  try:
      data = reader.read()
      print(f"RPM: {data.physics.rpm}, Speed: {data.graphics.speed}")
  except GameNotRunningError:
      print("Game not running")
  ```

### Verification

- [ ] Mock mode works out-of-the-box: UI developers can run without game installed
- [ ] All unit tests pass (`pytest -q` shows 100% pass)
- [ ] Code coverage report (via `pytest-cov`) shows >90% coverage of core parsing logic
- [ ] Mock data is realistic: RPM curves match expected engine behavior, speed accelerates/decelerates plausibly
- [ ] Example code in documentation runs without errors (in mock mode)
- [ ] No resource leaks in long-running mock mode (run for 1+ hour, monitor memory)

---

## Final Verification

- [ ] All acceptance criteria from `spec.md` are satisfied
- [ ] All unit and integration tests passing (`pytest` clean)
- [ ] Code style compliance: `black .`, `isort .`, `flake8` all pass
- [ ] All public APIs have type hints and Google-style docstrings
- [ ] No `print()` statements in production code (use `logging` module if needed)
- [ ] Module can be imported in isolation: `python -c "from telemetry.reader import SharedMemoryReader; print('OK')"`
- [ ] Documentation updated (module docstring, example usage)
- [ ] Ready for code review

---

_Generated by Conductor. Tasks will be marked [~] in progress and [x] complete._

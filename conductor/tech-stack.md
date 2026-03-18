# Tech Stack

## Languages

- **Python 3.11** — primary language for application logic

## Frameworks & Libraries

### GUI & Visualization
- **PyQt6** — main application framework and UI components
- **pyqtgraph** — real-time plotting for telemetry graphs (RPM, speed, pressures)
- **Matplotlib** (optional) — for static analysis charts

### Data Processing
- **NumPy** — efficient numerical operations on telemetry arrays
- **Pandas** (optional) — data analysis and CSV export functionality

### Data Storage
- **SQLite** — local database for storing laps, sessions, setups
- **SQLAlchemy** (recommended) — ORM for database operations

### Build & Distribution
- **PyInstaller** — package Python app into standalone Windows .exe
- **cx_Freeze** (alternative) — another option for .exe generation

### Shared Memory Integration
- **aclib_shared_memory.pyd** — existing compiled Python extension for reading Assetto Corsa shared memory
- **ctypes** — standard library for loading and interfacing with .pyd library

## Infrastructure & Distribution

- **Target Platform**: Windows (x64)
- **Distribution**: Standalone .exe with bundled Python interpreter
- **Installation**: Single executable file, no installer required

## Development Dependencies

- **pytest** — testing framework (optional but recommended)
- **pytest-qt** — Qt testing integration
- **black** — code formatting
- **flake8** or **pylint** — linting
- **mypy** — optional type checking

## Key Constraints

- Must work with Assetto Corsa, ACC, and AC Evo shared memory formats
- .pyd library is Windows-specific (compiled C/C++ extension)
- Application must be distributable as single .exe (PyInstaller onefile mode)
- Real-time requirements: telemetry update rate should match game physics rate (typically 60-120 Hz)

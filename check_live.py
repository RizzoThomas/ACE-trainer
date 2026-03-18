#!/usr/bin/env python3
"""Live telemetry monitor for Assetto Corsa.

Poll the shared memory every 100ms and print RPM and Gear to stdout.
Exits cleanly if the game is not running or on Ctrl+C.
"""

import sys
import time
import signal
from pathlib import Path

# Add src to path for imports when run as script
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from telemetry.reader import (
    WindowsSharedMemoryReader,
    GameNotRunningError,
    GameVariantError,
    SharedMemoryDisconnectedError,
)


def signal_handler(sig: int, frame: object) -> None:
    """Handle Ctrl+C gracefully."""
    print("\nInterrupted. Exiting...")
    sys.exit(0)


def main() -> int:
    """Main loop: connect to shared memory and print telemetry."""
    signal.signal(signal.SIGINT, signal_handler)

    print("Connecting to Assetto Corsa shared memory...")
    try:
        reader = WindowsSharedMemoryReader()
    except GameVariantError as e:
        print(f"Error: Could not detect game variant: {e}")
        return 1
    except Exception as e:
        print(f"Error: Failed to initialize reader: {e}")
        return 1

    with reader:
        # Attempt first read to verify connection
        try:
            physics, graphics, _ = reader.read()
        except GameNotRunningError:
            print("Game is not running. Start Assetto Corsa and retry.")
            return 1
        except Exception as e:
            print(f"Error during initial read: {e}")
            return 1

        print("Connected! Streaming telemetry (Ctrl+C to exit):\n")
        print(f"{'RPM':>6} | {'Gear':>4} | {'Speed km/h':>10}")
        print("-" * 30)

        while True:
            try:
                physics, graphics, _ = reader.read()
                gear_display = "N" if physics.gear == 0 else ("R" if physics.gear == -1 else str(physics.gear))
                print(f"{physics.rpm:6d} | {gear_display:>4} | {physics.speed:10.1f}")
                time.sleep(0.1)  # 100ms poll interval
            except GameNotRunningError:
                print("\nGame has stopped. Exiting.")
                break
            except SharedMemoryDisconnectedError:
                print("\nLost connection to shared memory. Exiting.")
                break
            except Exception as e:
                print(f"\nError reading telemetry: {e}")
                break

    return 0


if __name__ == "__main__":
    sys.exit(main())

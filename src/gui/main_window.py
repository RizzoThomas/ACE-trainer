"""PyQt6 GUI for Assetto Corsa telemetry.

Provides a real-time dashboard showing RPM, gear, speed, and connection status.
Designed to run in a separate thread to avoid blocking the UI.
"""

import sys
import argparse
from pathlib import Path


def _add_src_to_path() -> Path:
    """Ensure 'src' is on sys.path and return the src path."""
    project_root = Path(__file__).parent.parent.resolve()  # this is the 'src' directory
    src_path = project_root
    print(f"[DEBUG] __file__ = {__file__}", file=sys.stderr)
    print(f"[DEBUG] project_root (src) = {project_root}", file=sys.stderr)
    print(f"[DEBUG] sys.path before = {sys.path[:3]}", file=sys.stderr)
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    print(f"[DEBUG] sys.path after = {sys.path[:3]}", file=sys.stderr)
    return src_path


# Add src to path immediately so subsequent imports can find 'telemetry'
_add_src_to_path()

# Import PyQt6 (external dependency, not affected by our src path)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont


# ============================================================================
# Worker Thread
# ============================================================================

class TelemetryThread(QThread):
    """Background thread that polls shared memory at ~60Hz.

    Signals:
        data_updated: Emitted with (physics, graphics, static) on successful read.
        connection_lost: Emitted when the game disconnects.
        error_occurred: Emitted with error message on fatal errors.
    """

    data_updated = pyqtSignal(object, object, object)
    connection_lost = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, reader: "SharedMemoryReader", poll_interval: float = 0.016) -> None:
        super().__init__()
        self.reader = reader
        self.poll_interval = poll_interval
        self._running = True
        self._connected = False

    def run(self) -> None:
        while self._running:
            try:
                physics, graphics, static = self.reader.read()
                self._connected = True
                self.data_updated.emit(physics, graphics, static)
            except GameNotRunningError:
                if self._connected:
                    self._connected = False
                    self.connection_lost.emit()
                self.msleep(int(self.poll_interval * 1000))
            except Exception as e:
                self.error_occurred.emit(str(e))
                break
            self.msleep(int(self.poll_interval * 1000))

    def stop(self) -> None:
        self._running = False
        self.wait()


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window with telemetry dashboard."""

    def __init__(self, reader: "SharedMemoryReader") -> None:
        super().__init__()
        self.reader = reader
        self.telemetry_thread: TelemetryThread | None = None
        self.current_physics = None
        self.current_graphics = None
        self.current_static = None
        self._connected = False

        self._setup_ui()
        self._start_telemetry()

    def _setup_ui(self) -> None:
        """Configure UI layout and widgets."""
        self.setWindowTitle("Assetto Corsa Telemetry Dashboard")
        self.setMinimumSize(400, 300)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Status label
        self.status_label = QLabel("Stato: Disconnesso")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.status_label)

        # RPM progress bar
        self.rpm_bar = QProgressBar()
        self.rpm_bar.setRange(0, 20000)
        self.rpm_bar.setValue(0)
        self.rpm_bar.setTextVisible(True)
        self.rpm_bar.setFormat("%v RPM")
        self.rpm_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                font-size: 16px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.rpm_bar)

        # Gear display (large)
        self.gear_label = QLabel("N")
        self.gear_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gear_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gear_label.setStyleSheet("""
            QLabel {
                font-size: 120px;
                font-weight: bold;
                color: #333;
            }
        """)
        layout.addWidget(self.gear_label)

        # Speed display
        self.speed_label = QLabel("0.0 km/h")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setStyleSheet("font-size: 24px; color: #666;")
        layout.addWidget(self.speed_label)

        # Additional info (optional)
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(self.info_label)

    def _start_telemetry(self) -> None:
        """Start the background telemetry thread."""
        self.telemetry_thread = TelemetryThread(self.reader)
        self.telemetry_thread.data_updated.connect(self._on_data_updated)
        self.telemetry_thread.connection_lost.connect(self._on_connection_lost)
        self.telemetry_thread.error_occurred.connect(self._on_error)
        self.telemetry_thread.start()

    def _on_data_updated(self, physics: object, graphics: object, static: object) -> None:
        """Handle new telemetry data from thread."""
        self.current_physics = physics
        self.current_graphics = graphics
        self.current_static = static

        if not self._connected:
            self._connected = True
            self.status_label.setText("Stato: Connesso")
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")

        self._update_rpm_bar(physics)
        self._update_gear_label(physics)
        self._update_speed_label(physics)

    def _on_connection_lost(self) -> None:
        """Handle game disconnection."""
        self._connected = False
        self.status_label.setText("Stato: Disconnesso")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        self.rpm_bar.setValue(0)
        self.gear_label.setText("N")
        self.speed_label.setText("0.0 km/h")

    def _on_error(self, message: str) -> None:
        """Handle fatal error from telemetry thread."""
        self.status_label.setText(f"Errore: {message}")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")

    def _update_rpm_bar(self, physics: object) -> None:
        """Update RPM progress bar with dynamic color."""
        rpm = physics.rpm
        self.rpm_bar.setValue(rpm)

        max_rpm = getattr(physics, "max_rpm", 20000) or 20000
        ratio = rpm / max_rpm if max_rpm > 0 else 0

        if ratio < 0.6:
            color = "#4CAF50"  # green
        elif ratio < 0.85:
            color = "#FFC107"  # amber/yellow
        else:
            color = "#F44336"  # red

        self.rpm_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #555;
                border-radius: 8px;
                text-align: center;
                font-size: 16px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

    def _update_gear_label(self, physics: object) -> None:
        """Update large gear display."""
        gear = physics.gear
        if gear == 0:
            text = "N"
        elif gear == -1:
            text = "R"
        else:
            text = str(gear)
        self.gear_label.setText(text)

    def _update_speed_label(self, physics: object) -> None:
        """Update speed display."""
        speed = physics.speed
        self.speed_label.setText(f"{speed:.1f} km/h")

    def closeEvent(self, event) -> None:
        """Handle window close — stop telemetry thread."""
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.stop()
        event.accept()


def main() -> int:
    """Parse arguments, create reader, and start Qt application."""
    try:
        # Import telemetry modules after src is already on path (from module-level call)
        from telemetry.reader import (
            SharedMemoryReader,
            WindowsSharedMemoryReader,
            MockSharedMemoryReader,
        )

        parser = argparse.ArgumentParser(description="Assetto Corsa Telemetry GUI")
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Use mock telemetry data instead of shared memory",
        )
        args = parser.parse_args()

        # Create appropriate reader
        if args.mock:
            reader = MockSharedMemoryReader()
            print("Using MOCK reader (synthetic data)")
        else:
            reader = WindowsSharedMemoryReader()
            print("Using WINDOWS shared memory reader (live data)")

        # Create and run Qt application
        app = QApplication(sys.argv)
        window = MainWindow(reader)
        window.show()
        return app.exec()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""PyQt6 GUI for Assetto Corsa telemetry - Professional Dashboard.

Provides a real-time racing dashboard with:
- RPM bar with color zones
- Large gear display
- Tire temperatures & pressures (4 tires)
- Throttle and brake vertical bars
- Lap timing (current, last, best, delta)
- Connection status
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# Add src to path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QProgressBar,
    QFrame,
    QSizePolicy,
    QGroupBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette

from telemetry.reader import (
    SharedMemoryReader,
    WindowsSharedMemoryReader,
    MockSharedMemoryReader,
    GameNotRunningError,
    PhysicsData,
    GraphicsData,
)


# ============================================================================
# Worker Thread
# ============================================================================

class TelemetryThread(QThread):
    """Background thread polling shared memory."""
    data_updated = pyqtSignal(object, object, object)
    connection_lost = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, reader: SharedMemoryReader, poll_interval: float = 0.016) -> None:
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
# Custom Widgets
# ============================================================================

class TireWidget(QFrame):
    """Widget showing a single tire's temperature and pressure."""

    def __init__(self, tire_name: str) -> None:
        super().__init__()
        self.tire_name = tire_name
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Name label (FL, FR, RL, RR)
        self.name_label = QLabel(tire_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.name_label)

        # Temperature color bar (colored rectangle)
        self.temp_bar = QLabel()
        self.temp_bar.setMinimumHeight(40)
        self.temp_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.temp_bar.setStyleSheet("background-color: gray; border: 1px solid #333; border-radius: 3px;")
        layout.addWidget(self.temp_bar)

        # Temperature value label
        self.temp_label = QLabel("--°C")
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.temp_label)

        # Pressure label
        self.pressure_label = QLabel("-- PSI")
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pressure_label.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(self.pressure_label)

    def update_data(self, temp_avg: float, temp_inner: float, temp_outer: float, pressure: float) -> None:
        """Update tire display.

        Args:
            temp_avg: Average of inner/center/outer (or center) in Celsius
            temp_inner: Inner edge temp (for color gradient)
            temp_outer: Outer edge temp (for info)
            pressure: Tire pressure in PSI
        """
        # Update temperature text (show average and range)
        self.temp_label.setText(f"{temp_avg:.0f}°C ({temp_inner:.0f}/{temp_outer:.0f})")

        # Update pressure
        self.pressure_label.setText(f"{pressure:.1f} PSI")

        # Compute color based on temperature (typical operating range 80-110°C)
        # Cold (<70): blue, Warm (70-90): green, Hot (90-110): yellow, Over (>110): red
        if temp_avg < 70:
            hue = 240  # blue
        elif temp_avg < 90:
            hue = int(240 - (temp_avg - 70) * 6)  # blue to green (240->120)
        elif temp_avg < 110:
            hue = int(120 - (temp_avg - 90) * 6)  # green to yellow (120->60)
        else:
            hue = 60  # yellow/orange (could go to red at 0, but keep at 60 for now)

        color = QColor.fromHsl(hue, 255, 200)
        self.temp_bar.setStyleSheet(f"""
            QLabel {{
                background-color: {color.name()};
                border: 1px solid #333;
                border-radius: 3px;
            }}
        """)


class PedalBars(QFrame):
    """Vertical bars for throttle and brake."""

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # Throttle bar
        throttle_layout = QVBoxLayout()
        throttle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.throttle_bar = QProgressBar()
        self.throttle_bar.setOrientation(Qt.Orientation.Vertical)
        self.throttle_bar.setRange(0, 100)
        self.throttle_bar.setValue(0)
        self.throttle_bar.setFormat("")  # No text overlay
        throttle_layout.addWidget(self.throttle_bar)
        self.throttle_label = QLabel("THROTTLE")
        self.throttle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.throttle_label.setStyleSheet("font-size: 10px; color: #888;")
        throttle_layout.addWidget(self.throttle_label)
        layout.addLayout(throttle_layout)

        # Brake bar
        brake_layout = QVBoxLayout()
        brake_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brake_bar = QProgressBar()
        self.brake_bar.setOrientation(Qt.Orientation.Vertical)
        self.brake_bar.setRange(0, 100)
        self.brake_bar.setValue(0)
        self.brake_bar.setFormat("")  # No text overlay
        brake_layout.addWidget(self.brake_bar)
        self.brake_label = QLabel("BRAKE")
        self.brake_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brake_label.setStyleSheet("font-size: 10px; color: #888;")
        brake_layout.addWidget(self.brake_label)
        layout.addLayout(brake_layout)

    def update_data(self, throttle: float, brake: float) -> None:
        """Update pedal bars (0.0-1.0 -> 0-100%)."""
        self.throttle_bar.setValue(int(throttle * 100))
        self.brake_bar.setValue(int(brake * 100))


class LapTimeWidget(QFrame):
    """Widget showing lap times and delta."""

    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(5)
        layout.setHorizontalSpacing(20)

        # Current Lap
        layout.addWidget(QLabel("CURRENT LAP:"), 0, 0)
        self.current_lap_label = QLabel("--:--")
        self.current_lap_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.current_lap_label, 0, 1)

        layout.addWidget(QLabel("Lap:"), 0, 2)
        self.lap_number_label = QLabel("0/10")
        layout.addWidget(self.lap_number_label, 0, 3)

        # Last Lap
        layout.addWidget(QLabel("LAST:"), 1, 0)
        self.last_lap_label = QLabel("--:--")
        self.last_lap_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.last_lap_label, 1, 1)

        # Best Lap
        layout.addWidget(QLabel("BEST:"), 2, 0)
        self.best_lap_label = QLabel("--:--")
        self.best_lap_label.setStyleSheet("font-size: 14px; color: #00C853;")
        layout.addWidget(self.best_lap_label, 2, 1)

        # Delta
        layout.addWidget(QLabel("DELTA:"), 1, 2)
        self.delta_label = QLabel("+0.00")
        self.delta_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.delta_label, 1, 3)

        # Fuel
        layout.addWidget(QLabel("FUEL:"), 2, 2)
        self.fuel_label = QLabel("-- L")
        layout.addWidget(self.fuel_label, 2, 3)

    def update_data(self, graphics: GraphicsData, fuel_level: float, fuel_capacity: float = 120.0) -> None:
        """Update lap time displays."""
        # Current lap time (mm:ss.ss)
        self.current_lap_label.setText(self._format_time(graphics.current_lap_time))
        self.lap_number_label.setText(f"{graphics.current_lap}/{graphics.total_laps}")

        # Last lap
        if graphics.last_lap_time > 0:
            self.last_lap_label.setText(self._format_time(graphics.last_lap_time))
        else:
            self.last_lap_label.setText("--:--")

        # Best lap
        if graphics.best_lap_time > 0:
            self.best_lap_label.setText(self._format_time(graphics.best_lap_time))
        else:
            self.best_lap_label.setText("--:--")

        # Delta
        delta = graphics.delta_to_best
        if abs(delta) < 0.01:
            delta = 0.0
        delta_str = f"{delta:+.2f}"
        color = "#4CAF50" if delta <= 0 else "#F44336"
        self.delta_label.setText(delta_str)
        self.delta_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

        # Fuel percentage
        fuel_pct = (fuel_level / fuel_capacity) * 100 if fuel_capacity > 0 else 0
        self.fuel_label.setText(f"{fuel_level:.1f} L ({fuel_pct:.0f}%)")

    def _format_time(self, seconds: float) -> str:
        """Format seconds to mm:ss.ss string."""
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:05.2f}"


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(QMainWindow):
    """Professional telemetry dashboard."""

    def __init__(self, reader: SharedMemoryReader) -> None:
        super().__init__()
        self.reader = reader
        self.telemetry_thread: TelemetryThread | None = None
        self._connected = False

        # Store static data for max_rpm reference
        self.max_rpm = 20000

        self._setup_ui()
        self._start_telemetry()

    def _setup_ui(self) -> None:
        """Configure professional dashboard layout."""
        self.setWindowTitle("Assetto Corsa Telemetry - Professional")
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === Top bar: Status + RPM ===
        top_layout = QHBoxLayout()
        self.status_label = QLabel("Stato: Disconnesso")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        top_layout.addWidget(self.status_label)
        top_layout.addStretch()
        self.rpm_bar = QProgressBar()
        self.rpm_bar.setRange(0, 20000)
        self.rpm_bar.setValue(0)
        self.rpm_bar.setTextVisible(True)
        self.rpm_bar.setFormat("%v RPM")
        self.rpm_bar.setFixedHeight(30)
        self.rpm_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                border-radius: 4px;
            }
        """)
        top_layout.addWidget(self.rpm_bar, stretch=2)
        main_layout.addLayout(top_layout)

        # === Middle section: Gear + Speed + Pedals ===
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(15)

        # Gear display (large)
        self.gear_label = QLabel("N")
        self.gear_label.setFixedSize(200, 200)
        self.gear_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gear_label.setStyleSheet("""
            QLabel {
                font-size: 140px;
                font-weight: bold;
                color: #333;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #eee, stop:1 #ccc);
                border-radius: 10px;
                border: 2px solid #999;
            }
        """)
        middle_layout.addWidget(self.gear_label)

        # Speed display next to gear
        speed_frame = QFrame()
        speed_layout = QVBoxLayout(speed_frame)
        self.speed_label = QLabel("0.0")
        self.speed_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #2196F3;")
        speed_layout.addWidget(self.speed_label, alignment=Qt.AlignmentFlag.AlignCenter)
        speed_unit = QLabel("km/h")
        speed_unit.setStyleSheet("font-size: 16px; color: #666;")
        speed_layout.addWidget(speed_unit, alignment=Qt.AlignmentFlag.AlignCenter)
        speed_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle_layout.addWidget(speed_frame)

        middle_layout.addStretch()

        # Pedal bars (throttle/brake)
        pedal_frame = QGroupBox("Pedals")
        pedal_layout = QVBoxLayout(pedal_frame)
        self.pedal_bars = PedalBars()
        pedal_layout.addWidget(self.pedal_bars)
        pedal_frame.setFixedWidth(100)
        middle_layout.addWidget(pedal_frame)

        main_layout.addLayout(middle_layout)

        # === Tire section: 4 tire rectangles ===
        tire_group = QGroupBox("Tire Temperatures & Pressures")
        tire_layout = QHBoxLayout(tire_group)
        tire_layout.setSpacing(10)

        self.tire_widgets: List[TireWidget] = []
        tire_names = ["FL", "FR", "RL", "RR"]
        for name in tire_names:
            widget = TireWidget(name)
            self.tire_widgets.append(widget)
            tire_layout.addWidget(widget)

        main_layout.addWidget(tire_group)

        # === Bottom: Lap times ===
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.lap_widget = LapTimeWidget()
        bottom_layout.addWidget(self.lap_widget)

        bottom_layout.addStretch()
        main_layout.addLayout(bottom_layout)

    def _start_telemetry(self) -> None:
        """Start background telemetry thread."""
        self.telemetry_thread = TelemetryThread(self.reader)
        self.telemetry_thread.data_updated.connect(self._on_data_updated)
        self.telemetry_thread.connection_lost.connect(self._on_connection_lost)
        self.telemetry_thread.error_occurred.connect(self._on_error)
        self.telemetry_thread.start()

    def _on_data_updated(self, physics: PhysicsData, graphics: GraphicsData, static: object) -> None:
        """Update UI with new telemetry."""
        # Update connection status on first data
        if not self._connected:
            self._connected = True
            self.status_label.setText("Stato: Connesso")
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
            # Store max_rpm from static if available
            if hasattr(static, 'max_rpm'):
                self.max_rpm = static.max_rpm or 20000

        # RPM bar with color
        self._update_rpm_bar(physics.rpm)

        # Gear
        self.gear_label.setText(self._format_gear(physics.gear))

        # Speed
        self.speed_label.setText(f"{physics.speed:.1f}")

        # Pedals
        self.pedal_bars.update_data(physics.throttle, physics.brake)

        # Tires: Use center temps from tire_temperature array
        # Order: FL inner/center/outer, FR inner/center/outer, RL, RR
        for i, widget in enumerate(self.tire_widgets):
            idx = i * 3
            inner = physics.tire_temperature[idx]
            center = physics.tire_temperature[idx + 1]
            outer = physics.tire_temperature[idx + 2]
            avg_temp = (inner + center + outer) / 3.0
            pressure = physics.tire_pressure[i] if i < len(physics.tire_pressure) else 30.0
            widget.update_data(avg_temp, inner, outer, pressure)

        # Lap times
        self.lap_widget.update_data(graphics, physics.fuel_level, getattr(static, 'fuel_capacity', 120.0))

    def _on_connection_lost(self) -> None:
        self._connected = False
        self.status_label.setText("Stato: Disconnesso")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        self.rpm_bar.setValue(0)
        self.gear_label.setText("N")
        self.speed_label.setText("0.0")
        self.pedal_bars.update_data(0.0, 0.0)
        for widget in self.tire_widgets:
            widget.update_data(0.0, 0.0, 0.0, 0.0)

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Errore: {message[:50]}")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")

    def _update_rpm_bar(self, rpm: int) -> None:
        """Update RPM bar with dynamic color."""
        self.rpm_bar.setValue(rpm)
        ratio = rpm / self.max_rpm if self.max_rpm > 0 else 0

        if ratio < 0.6:
            color_hex = "#4CAF50"  # green
        elif ratio < 0.85:
            color_hex = "#FFC107"  # amber
        else:
            color_hex = "#F44336"  # red

        self.rpm_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 4px;
            }}
        """)

    def _format_gear(self, gear: int) -> str:
        """Format gear number for display."""
        if gear == 0:
            return "N"
        elif gear == -1:
            return "R"
        else:
            return str(gear)

    def closeEvent(self, event) -> None:
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.stop()
        event.accept()


def main() -> int:
    try:
        from telemetry.reader import SharedMemoryReader, WindowsSharedMemoryReader, MockSharedMemoryReader
        import sys

        parser = argparse.ArgumentParser(description="Assetto Corsa Telemetry GUI")
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Use mock telemetry data instead of shared memory",
        )
        args = parser.parse_args()

        if args.mock:
            reader = MockSharedMemoryReader()
            print("Using MOCK reader (synthetic data)")
        else:
            reader = WindowsSharedMemoryReader()
            print("Using WINDOWS shared memory reader (live data)")

        app = QApplication(sys.argv)
        window = MainWindow(reader)
        window.resize(1000, 700)
        window.show()
        return app.exec()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

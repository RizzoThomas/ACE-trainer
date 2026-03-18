"""High-Tech Alcantara Dashboard for ACE-Trainer.

PyQt6 implementation of the stitch design live telemetry dashboard.
Full professional racing aesthetic with:
- Stitched borders (dashed lines)
- Glow effects on tires
- Segmented RPM bar
- Italic giant gear display
- G-Force circular widget
- Neon pedal bars
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
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QRect, QPointF
from PyQt6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QBrush,
    QFont,
    QFontDatabase,
    QRadialGradient,
    QPainterPath,
    QGraphicsDropShadowEffect,
    QPolygonF,
)

from telemetry.reader import (
    SharedMemoryReader,
    WindowsSharedMemoryReader,
    MockSharedMemoryReader,
    GameNotRunningError,
    PhysicsData,
    GraphicsData,
)

# ============================================================================
# Colors from design
# ============================================================================

COLORS = {
    'bg': QColor(8, 8, 8),  # #080808
    'primary': QColor(13, 127, 242),  # #0d7ff2 (blue)
    'accent': QColor(0, 255, 65),  # #00ff41 (green)
    'danger': QColor(255, 0, 60),  # #ff003c (red)
    'surface': QColor(18, 18, 18),  # #121212
    'card': QColor(26, 26, 26),  # #1a1a1a
    'text': QColor(255, 255, 255),
    'text_dim': QColor(150, 150, 150),
    'border': QColor(255, 255, 255, 40),  # white at 15% opacity
}

# ============================================================================
# Custom Widgets
# ============================================================================

class StitchFrame(QFrame):
    """Frame with dashed border simulating leather stitching."""

    def __init__(self, parent=None, color=COLORS['primary'], dash_pattern=None):
        super().__init__(parent)
        self.stitch_color = color
        if dash_pattern is None:
            self.dash_pattern = [4, 2]  # 4px line, 2px gap
        else:
            self.dash_pattern = dash_pattern
        self.setLineWidth(2)
        self.setMidLineWidth(0)
        self.setFrameShape(QFrame.Shape.Box)

    def paintEvent(self, event):
        """Custom paint to draw dashed border."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.stitch_color, 2)
        pen.setDashPattern(self.dash_pattern)
        painter.setPen(pen)
        # Draw inside the frame rect
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 8, 8)


class SegmentedRPMBar(QFrame):
    """RPM bar with separate segments like the design."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rpm = 0
        self.max_rpm = 20000
        self.segments = 12
        self.setFixedHeight(32)
        self.setStyleSheet("background: #00000080; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px;")

    def set_rpm(self, rpm: int) -> None:
        """Update RPM value."""
        self.rpm = min(rpm, self.max_rpm)
        self.update()

    def paintEvent(self, event):
        """Draw 12 segments with color zones."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        segment_width = (w - 2) / self.segments  # -2 for padding

        for i in range(self.segments):
            seg_rect = QRect(
                int(i * segment_width) + 1,
                1,
                int(segment_width) - 1,
                h - 2
            )
            # Determine if this segment should be lit based on current RPM
            seg_end_rpm = int((i + 1) * self.max_rpm / self.segments)
            is_lit = self.rpm >= seg_end_rpm

            # Color zones: 0-60% (7 segments) = blue, 60-85% (3 segments) = green, 85-100% (2 segments) = red
            if i < 7:
                color = COLORS['primary']
            elif i < 10:
                color = COLORS['accent']
            else:
                color = COLORS['danger']

            # Dim if not lit
            if not is_lit:
                color = QColor(60, 60, 60)

            painter.fillRect(seg_rect, color)

        # Optional: draw segment dividers
        painter.setPen(QColor(80, 80, 80))
        for i in range(1, self.segments):
            x = int(i * segment_width)
            painter.drawLine(x, 0, x, h)


class TireWidget(QFrame):
    """Tire temperature and pressure widget with glow effect."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFixedHeight(120)
        self.setStyleSheet("""
            TireWidget {
                background: #1a1a1a;
                border: 2px solid rgba(255,255,255,0.2);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Name label
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #aaa;")
        layout.addWidget(self.name_label)

        # Temperature bar (colored rectangle)
        self.temp_bar = QLabel()
        self.temp_bar.setFixedHeight(50)
        self.temp_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.temp_bar)

        # Temperature value
        self.temp_label = QLabel("--°C")
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.temp_label)

        # Pressure label
        self.pressure_label = QLabel("-- PSI")
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pressure_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self.pressure_label)

        # Glow effect
        self.glow = QGraphicsDropShadowEffect()
        self.glow.setBlurRadius(20)
        self.glow.setColor(QColor(0, 255, 65, 100))  # default green glow
        self.glow.setOffset(0, 0)
        self.temp_bar.setGraphicsEffect(self.glow)

        # Secondary glow for the whole widget border
        self.border_glow = QGraphicsDropShadowEffect()
        self.border_glow.setBlurRadius(15)
        self.border_glow.setColor(QColor(13, 127, 242, 80))
        self.border_glow.setOffset(0, 0)
        self.setGraphicsEffect(self.border_glow)

    def update_data(self, temp_avg: float, temp_inner: float, temp_outer: float, pressure: float) -> None:
        """Update tire display with temperature and pressure."""
        self.temp_label.setText(f"{temp_avg:.0f}°")
        self.pressure_label.setText(f"{pressure:.1f} PSI")

        # Color based on temperature: cold (blue) -> warm (green) -> hot (orange) -> very hot (red)
        if temp_avg < 70:
            # Cold - blue
            gradient = "qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #1e40af, stop:1 #3b82f6)"
            glow_color = QColor(59, 130, 246, 150)
        elif temp_avg < 90:
            # Warm - green
            gradient = "qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #166534, stop:1 #22c55e)"
            glow_color = QColor(34, 197, 94, 150)
        elif temp_avg < 110:
            # Hot - orange
            gradient = "qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #9a3412, stop:1 #f97316)"
            glow_color = QColor(249, 115, 22, 150)
        else:
            # Very hot - red
            gradient = "qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #991b1b, stop:1 #ef4444)"
            glow_color = QColor(239, 68, 68, 150)

        self.temp_bar.setStyleSheet(f"""
            QLabel {{
                background: {gradient};
                border-radius: 6px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
        """)
        self.glow.setColor(glow_color)


class GForceWidget(QFrame):
    """Circular G-force indicator with crosshair and glowing dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self.g_force_lat = 0.0
        self.g_force_long = 0.0
        self.max_g = 3.0
        self.setStyleSheet("background: #1a1a1a; border: 2px solid rgba(255,255,255,0.2); border-radius: 80px;")

    def set_g_forces(self, lateral: float, longitudinal: float) -> None:
        """Update G-force values.

        Args:
            lateral: Left/right G (negative = left, positive = right)
            longitudinal: Acceleration/braking G (positive = accel, negative = brake)
        """
        self.g_force_lat = lateral
        self.g_force_long = longitudinal
        self.update()

    def paintEvent(self, event):
        """Draw crosshair and G-force dot."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 10

        # Draw outer ring
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2)))

        # Draw crosshair lines
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        # Draw center circle (neutral)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 30, 30)))
        painter.drawEllipse(QRect(int(cx - 8), int(cy - 8), 16, 16))

        # Compute dot position from G-forces
        # Lateral: left/right -> x offset
        # Longitudinal: up/down -> y offset (accelerate = up)
        x = cx + (self.g_force_lat / self.max_g) * radius
        y = cy - (self.g_force_long / self.max_g) * radius  # negative because y goes down

        # Clamp to circle
        import math
        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        if dist > radius - 10:
            angle = math.atan2(y - cy, x - cx)
            x = cx + (radius - 10) * math.cos(angle)
            y = cy + (radius - 10) * math.sin(angle)

        # Draw glow
        glow_color = COLORS['accent'] if abs(self.g_force_lat) < 1.0 and abs(self.g_force_long) < 1.0 else COLORS['danger']
        painter.setBrush(QBrush(glow_color))
        painter.setPen(QPen(glow_color, 2))
        painter.drawEllipse(QRect(int(x - 6), int(y - 6), 12, 12))

        # Draw value text
        total_g = math.sqrt(self.g_force_lat ** 2 + self.g_force_long ** 2)
        painter.setPen(QPen(COLORS['text']))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(QRect(0, h - 25, w, 20), Qt.AlignmentFlag.AlignCenter, f"{total_g:.1f}G")


class PedalBarsNeon(QFrame):
    """Neon vertical bars for throttle and brake."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.throttle = 0.0
        self.brake = 0.0
        self.setFixedWidth(80)
        self.setStyleSheet("background: #0a0a0a; border: 1px solid #333; border-radius: 8px;")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 15)

        # Throttle
        self.throttle_bar = QProgressBar()
        self.throttle_bar.setOrientation(Qt.Orientation.Vertical)
        self.throttle_bar.setRange(0, 100)
        self.throttle_bar.setValue(0)
        self.throttle_bar.setText(False)
        self.throttle_bar.setFormat("")
        self.throttle_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #1a1a1a;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #065f46, stop:1 #22c55e);
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.throttle_bar, stretch=1)

        self.throttle_label = QLabel("THR")
        self.throttle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.throttle_label.setStyleSheet("font-size: 10px; color: #00ff41; font-weight: bold;")
        layout.addWidget(self.throttle_label)

        # Brake
        self.brake_bar = QProgressBar()
        self.brake_bar.setOrientation(Qt.Orientation.Vertical)
        self.brake_bar.setRange(0, 100)
        self.brake_bar.setValue(0)
        self.brake_bar.setText(False)
        self.brake_bar.setFormat("")
        self.brake_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #1a1a1a;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #991b1b, stop:1 #ef4444);
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.brake_bar, stretch=1)

        self.brake_label = QLabel("BRK")
        self.brake_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brake_label.setStyleSheet("font-size: 10px; color: #ff003c; font-weight: bold;")
        layout.addWidget(self.brake_label)

    def update_data(self, throttle: float, brake: float) -> None:
        """Update pedal positions (0.0-1.0)."""
        self.throttle_bar.setValue(int(throttle * 100))
        self.brake_bar.setValue(int(brake * 100))


class SpeedDisplay(QFrame):
    """Large speed display with km/h."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #121212; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;")
        self.setFixedHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        self.speed_value = QLabel("0")
        self.speed_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_value.setStyleSheet("""
            QLabel {
                font-size: 72px;
                font-weight: bold;
                color: #0d7ff2;
                font-family: 'Space Grotesk', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(self.speed_value)

        self.speed_unit = QLabel("KM/H")
        self.speed_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_unit.setStyleSheet("font-size: 18px; color: #0d7ff2; font-weight: bold; letter-spacing: 0.2em;")
        layout.addWidget(self.speed_unit)

    def set_speed(self, speed: float) -> None:
        """Update speed display."""
        self.speed_value.setText(f"{speed:.0f}")


class GearDisplay(QFrame):
    """Huge italic gear number with glow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gear = 0
        self.setFixedSize(200, 200)
        self.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a0a0a, stop:1 #050505); border: 2px solid #0d7ff2; border-radius: 20px;")

        # Glow effect
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(40)
        glow.setColor(QColor(13, 127, 242, 150))
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.gear_label = QLabel("N")
        self.gear_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gear_label.setStyleSheet("""
            QLabel {
                font-size: 140px;
                font-weight: 900;
                font-style: italic;
                color: white;
                font-family: 'Space Mono', 'Courier New', monospace;
            }
        """)
        layout.addWidget(self.gear_label)

    def set_gear(self, gear: int) -> None:
        """Update gear display."""
        if gear == 0:
            self.gear_label.setText("N")
        elif gear == -1:
            self.gear_label.setText("R")
        else:
            self.gear_label.setText(str(gear))


class LapTimeDisplay(QFrame):
    """Lap times widget: current, last, best, delta."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(120)
        self.setStyleSheet("background: #121212; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;")

        layout = QGridLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(5)

        # Current Lap
        layout.addWidget(QLabel("CURRENT"), 0, 0)
        self.current_time = QLabel("--:--")
        self.current_time.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(self.current_time, 1, 0)

        # Last Lap
        layout.addWidget(QLabel("LAST"), 0, 1)
        self.last_time = QLabel("--:--")
        self.last_time.setStyleSheet("font-size: 16px; color: #888;")
        layout.addWidget(self.last_time, 1, 1)

        # Best Lap
        layout.addWidget(QLabel("BEST"), 0, 2)
        self.best_time = QLabel("--:--")
        self.best_time.setStyleSheet("font-size: 16px; color: #00ff41;")
        layout.addWidget(self.best_time, 1, 2)

        # Delta
        layout.addWidget(QLabel("DELTA"), 0, 3)
        self.delta_label = QLabel("+0.00")
        self.delta_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #888;")
        layout.addWidget(self.delta_label, 1, 3)

        # Fuel
        layout.addWidget(QLabel("FUEL"), 2, 0)
        self.fuel_label = QLabel("-- L")
        self.fuel_label.setStyleSheet("font-size: 16px; color: #0d7ff2;")
        layout.addWidget(self.fuel_label, 3, 0, 1, 2)

    def update_data(self, graphics: GraphicsData, fuel_level: float, fuel_capacity: float = 120.0) -> None:
        """Update all lap time values."""
        self.current_time.setText(self._format_time(graphics.current_lap_time))
        self.last_time.setText(self._format_time(graphics.last_lap_time) if graphics.last_lap_time > 0 else "--:--")
        self.best_time.setText(self._format_time(graphics.best_lap_time) if graphics.best_lap_time > 0 else "--:--")

        delta = graphics.delta_to_best
        if abs(delta) < 0.01:
            delta = 0.0
        self.delta_label.setText(f"{delta:+.2f}")
        color = COLORS['accent'] if delta <= 0 else COLORS['danger']
        self.delta_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color.name()};")

        fuel_pct = (fuel_level / fuel_capacity) * 100 if fuel_capacity > 0 else 0
        self.fuel_label.setText(f"{fuel_level:.1f} L ({fuel_pct:.0f}%)")

    def _format_time(self, seconds: float) -> str:
        """Format seconds to mm:ss.ss."""
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:05.2f}"


class StatBox(StitchFrame):
    """Small stats box with colored left border."""

    def __init__(self, title: str, value: str = "--", unit: str = "", color=COLORS['primary'], parent=None):
        super().__init__(parent, color=color)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 10px; color: #888; font-weight: bold; text-transform: uppercase; letter-spacing: 0.1em;")
        layout.addWidget(title_lbl)

        val_layout = QHBoxLayout()
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color.name()};")
        val_layout.addWidget(self.value_lbl)

        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet("font-size: 12px; color: #666;")
            val_layout.addWidget(unit_lbl)

        val_layout.addStretch()
        layout.addLayout(val_layout)

    def set_value(self, value: str) -> None:
        """Update value."""
        self.value_lbl.setText(value)


# ============================================================================
# Main Window
# ============================================================================

class MainWindow(QMainWindow):
    """High-Tech Alcantara Dashboard."""

    def __init__(self, reader: SharedMemoryReader) -> None:
        super().__init__()
        self.reader = reader
        self.telemetry_thread: QThread | None = None
        self._connected = False
        self.max_rpm = 20000

        self._setup_ui()
        self._start_telemetry()

    def _setup_ui(self) -> None:
        """Build the professional HUD interface."""
        self.setWindowTitle("ACE-Trainer // High-Tech Telemetry")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet(f"background-color: {COLORS['bg'].name()}; color: {COLORS['text'].name()};")

        # Load Space Grotesk font if available
        # (In a real deployment, include the font file and use QFontDatabase)
        # For now, use system monospace

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === TOP BAR: Lap Time | RPM | Fuel ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)

        # Lap Time box (stitched)
        self.lap_time_box = StatBox("LAP TIME", "1:24.382", color=COLORS['primary'])
        top_bar.addWidget(self.lap_time_box)

        # RPM Bar (segmented)
        self.rpm_bar = SegmentedRPMBar()
        top_bar.addWidget(self.rpm_bar, stretch=1)

        # Fuel box (stitched, right border red)
        self.fuel_box = StatBox("FUEL REMAINING", "14.2", "L", color=COLORS['danger'])
        top_bar.addWidget(self.fuel_box)

        main_layout.addLayout(top_bar)

        # === CENTRAL GRID ===
        central_grid = QGridLayout()
        central_grid.setHorizontalSpacing(15)
        central_grid.setVerticalSpacing(15)

        # LEFT COLUMN (3 cols)
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Brake Temps box
        brake_box = StitchFrame(color=COLORS['danger'])
        brake_layout = QVBoxLayout(brake_box)
        brake_layout.setContentsMargins(12, 10, 12, 10)

        brake_title = QLabel("BRAKE TEMPERATURES")
        brake_title.setStyleSheet("font-size: 10px; color: #ff003c; font-weight: bold; text-transform: uppercase; letter-spacing: 0.1em;")
        brake_layout.addWidget(brake_title)

        self.brake_temp_labels = []
        for tire in ["FL", "FR", "RL", "RR"]:
            row = QHBoxLayout()
            name = QLabel(tire)
            name.setStyleSheet("font-size: 14px; color: #888; min-width: 30px;")
            temp = QLabel("---°C")
            temp.setStyleSheet("font-size: 16px; font-family: monospace; font-weight: bold;")
            row.addWidget(name)
            row.addStretch()
            row.addWidget(temp)
            brake_layout.addLayout(row)
            self.brake_temp_labels.append(temp)

        left_col.addWidget(brake_box)

        # DRS/ERS box
        drs_box = StitchFrame(color=COLORS['accent'])
        drs_layout = QVBoxLayout(drs_box)
        drs_layout.setContentsMargins(12, 10, 12, 10)

        drs_title = QLabel("DRS / ERS")
        drs_title.setStyleSheet("font-size: 10px; color: #00ff41; font-weight: bold; text-transform: uppercase; letter-spacing: 0.1em;")
        drs_layout.addWidget(drs_title)

        self.drs_bar = QProgressBar()
        self.drs_bar.setRange(0, 100)
        self.drs_bar.setValue(0)
        self.drs_bar.setText(False)
        self.drs_bar.setFormat("")
        self.drs_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #1a1a1a;
                border-radius: 4px;
                height: 12px;
            }
            QProgressBar::chunk {
                background: #00ff41;
                border-radius: 4px;
            }
        """)
        drs_layout.addWidget(self.drs_bar)

        self.drs_label = QLabel("DEPLOYMENT READY")
        self.drs_label.setStyleSheet("font-size: 10px; color: #00ff41; font-weight: bold; margin-top: 4px;")
        drs_layout.addWidget(self.drs_label)

        left_col.addWidget(drs_box)
        left_col.addStretch()

        central_grid.addLayout(left_col, 0, 0, 1, 3)

        # CENTER COLUMN (6 cols) - Gear + Tires + G-Force
        center_col = QVBoxLayout()
        center_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_col.setSpacing(20)

        # Gear display
        self.gear_display = GearDisplay()
        center_col.addWidget(self.gear_display, alignment=Qt.AlignmentFlag.AlignCenter)

        # Tire grid (4 tires in 2x2)
        tire_grid = QHBoxLayout()
        tire_grid.setSpacing(15)

        self.tire_widgets: List[TireWidget] = []
        for name in ["FL", "FR", "RL", "RR"]:
            tire = TireWidget(name)
            self.tire_widgets.append(tire)
            tire_grid.addWidget(tire)

        center_col.addLayout(tire_grid)

        # G-Force widget
        self.gforce_widget = GForceWidget()
        center_col.addWidget(self.gforce_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        central_grid.addLayout(center_col, 0, 3, 1, 6)

        # RIGHT COLUMN (3 cols)
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # Speed box
        self.speed_display = SpeedDisplay()
        right_col.addWidget(self.speed_display)

        # G-Force numeric (alternative, we already have widget)
        # Track Temp box
        track_box = StitchFrame(color=COLORS['primary'])
        track_layout = QVBoxLayout(track_box)
        track_layout.setContentsMargins(12, 10, 12, 10)

        track_title = QLabel("TRACK TEMP")
        track_title.setStyleSheet("font-size: 10px; color: #0d7ff2; font-weight: bold; text-transform: uppercase; letter-spacing: 0.1em;")
        track_layout.addWidget(track_title)

        self.track_temp_label = QLabel("34.5°C")
        self.track_temp_label.setStyleSheet("font-size: 28px; font-weight: bold; color: white;")
        track_layout.addWidget(self.track_temp_label)

        self.track_status = QLabel("OPTIMAL GRIP")
        self.track_status.setStyleSheet("font-size: 10px; color: #00ff41; font-weight: bold; margin-top: 4px;")
        track_layout.addWidget(self.track_status)

        right_col.addWidget(track_box)

        # Pedals box
        pedals_box = StitchFrame(color=COLORS['danger'])
        pedals_layout = QHBoxLayout(pedals_box)
        pedals_layout.setContentsMargins(10, 10, 10, 10)

        self.pedal_bars = PedalBarsNeon()
        pedals_layout.addWidget(self.pedal_bars)
        right_col.addWidget(pedals_box)

        right_col.addStretch()

        central_grid.addLayout(right_col, 0, 9, 1, 3)

        main_layout.addLayout(central_grid, stretch=1)

        # === FOOTER ===
        footer = QHBoxLayout()
        footer.setContentsMargins(10, 8, 10, 8)

        # Left: Status
        status_layout = QHBoxLayout()
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #ff003c; font-size: 14px;")
        self.status_text = QLabel("LIVE TELEMETRY ACTIVE")
        self.status_text.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #888;")
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        footer.addLayout(status_layout)

        # Center: Sync rate
        self.sync_label = QLabel("SYNC: 120Hz")
        self.sync_label.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #666;")
        footer.addWidget(self.sync_label)

        # Right: System info
        sys_layout = QHBoxLayout()
        sys_layout.setSpacing(10)

        for label in ["TC: LEVEL 2", "ABS: ON", "MAP: AGGRESSIVE"]:
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.05em; color: #666; border: 1px solid #444; border-radius: 4px; padding: 2px 8px;")
            sys_layout.addWidget(lbl)

        footer.addLayout(sys_layout)

        # Version
        version = QLabel("ACE-TRAINER // PC_PRO_BUILD_v2.4")
        version.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #444;")
        footer.addWidget(version)

        main_layout.addLayout(footer)

    def _start_telemetry(self) -> None:
        """Start background thread."""
        self.telemetry_thread = QThread()
        # We'll create worker object separately to avoid Qt parent issues
        from PyQt6.QtCore import QObject

        class Worker(QObject):
            data_updated = pyqtSignal(object, object, object)
            connection_lost = pyqtSignal()
            error_occurred = pyqtSignal(str)

            def __init__(self, reader):
                super().__init__()
                self.reader = reader
                self.running = True

            def run(self):
                import time
                while self.running:
                    try:
                        data = self.reader.read()
                        self.data_updated.emit(*data)
                    except GameNotRunningError:
                        self.connection_lost.emit()
                        time.sleep(0.5)
                    except Exception as e:
                        self.error_occurred.emit(str(e))
                        break
                    time.sleep(0.016)

            def stop(self):
                self.running = False

        self.worker = Worker(self.reader)
        self.worker.moveToThread(self.telemetry_thread)
        self.telemetry_thread.started.connect(self.worker.run)
        self.worker.data_updated.connect(self._on_data_updated)
        self.worker.connection_lost.connect(self._on_connection_lost)
        self.worker.error_occurred.connect(self._on_error)
        self.telemetry_thread.start()

    def _on_data_updated(self, physics: PhysicsData, graphics: GraphicsData, static: object) -> None:
        """Update all UI elements with new telemetry."""
        if not self._connected:
            self._connected = True
            self.status_indicator.setStyleSheet("color: #00ff41; font-size: 14px;")
            self.status_text.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #00ff41;")
            if hasattr(static, 'max_rpm'):
                self.max_rpm = static.max_rpm or 20000
                self.rpm_bar.max_rpm = self.max_rpm

        # RPM
        self.rpm_bar.set_rpm(physics.rpm)

        # Gear
        self.gear_display.set_gear(physics.gear)

        # Speed
        self.speed_display.set_speed(physics.speed)

        # Pedals
        self.pedal_bars.update_data(physics.throttle, physics.brake)

        # Tires (4 tires)
        for i, widget in enumerate(self.tire_widgets):
            idx = i * 3
            inner = physics.tire_temperature[idx]
            center = physics.tire_temperature[idx + 1]
            outer = physics.tire_temperature[idx + 2]
            avg_temp = (inner + center + outer) / 3.0
            pressure = physics.tire_pressure[i] if i < len(physics.tire_pressure) else 30.0
            widget.update_data(avg_temp, inner, outer, pressure)

        # G-Force (we don't have lateral/longitudinal in current physics, simulate from steering/accel)
        # For now, use placeholders based on steering and acceleration magnitude
        lat_g = (physics.steering / 900.0) * 2.0  # Rough approximation
        # Longitudinal from speed change (acc_x) but we have 0, so use throttle/brake
        long_g = 1.0 if physics.throttle > 0.5 else -1.0 if physics.brake > 0.5 else 0.0
        self.gforce_widget.set_g_forces(lat_g, long_g)

        # Lap times
        self.lap_time_box.set_value(self._format_time(graphics.current_lap_time))
        # For fuel, we need from physics
        fuel_level = getattr(physics, 'fuel_level', 0)
        fuel_capacity = getattr(static, 'fuel_capacity', 120) if hasattr(static, 'fuel_capacity') else 120
        self.fuel_box.set_value(f"{fuel_level:.1f} L")

    def _on_connection_lost(self) -> None:
        self._connected = False
        self.status_indicator.setStyleSheet("color: #ff003c; font-size: 14px;")
        self.status_text.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #888;")
        self.rpm_bar.set_rpm(0)
        self.gear_display.set_gear(0)
        self.speed_display.set_speed(0)
        self.pedal_bars.update_data(0, 0)

    def _on_error(self, message: str) -> None:
        self.status_text.setText(f"ERROR: {message[:20]}")
        self.status_text.setStyleSheet("font-size: 10px; font-weight: bold; letter-spacing: 0.1em; color: #ff003c;")

    def _format_time(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:05.2f}"

    def closeEvent(self, event) -> None:
        if hasattr(self, 'worker'):
            self.worker.stop()
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.quit()
            self.telemetry_thread.wait(2000)
        event.accept()


def main() -> int:
    try:
        from telemetry.reader import WindowsSharedMemoryReader, MockSharedMemoryReader
        import sys

        parser = argparse.ArgumentParser(description="ACE-Trainer High-Tech Dashboard")
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Use mock telemetry data",
        )
        args = parser.parse_args()

        if args.mock:
            reader = MockSharedMemoryReader()
            print("Using MOCK reader")
        else:
            reader = WindowsSharedMemoryReader()
            print("Using LIVE shared memory")

        app = QApplication(sys.argv)
        window = MainWindow(reader)
        window.resize(1600, 1000)
        window.show()
        return app.exec()
    except Exception as e:
        print(f"Fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

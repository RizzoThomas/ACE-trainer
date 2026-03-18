# Product Guidelines

## Voice and Tone

**Professional and technical** — the application should speak the language of sim racers. Use proper racing terminology (lap times, sectors, tire temps, brake pressures). Documentation should be precise and assume familiarity with racing concepts, but UI text should remain accessible to intermediate users.

- Do: "Real-time RPM monitoring with shift-light indicator"
- Don't: "See the car engine go round and round!"

## Design Principles

### 1. Real-time Performance
The application must deliver telemetry data with minimal latency (<100ms). UI updates must not block the shared memory reading loop. Use efficient data structures and avoid unnecessary recomputation.

### 2. Data Clarity
Telemetry visualization must be instantly understandable. Use clear colors, consistent scales, and intuitive graph layouts. RPM should be prominently displayed, speed in large digits, gear indicator unmistakable.

### 3. Export Flexibility
Setup export functionality should support multiple formats (CSV, JSON, proprietary). The export process should be straightforward — one-click from the current session or lap.

### 4. Reliability
Shared memory access is inherently fragile. The application must handle missing game processes gracefully and provide clear error messages when telemetry sources aren't available.

### 5. Simplicity
Avoid feature bloat. Focus on core telemetry display and analysis. Advanced analytics (delta times, trajectory comparison) can be future phases.

## Quality Standards

- All telemetry data must be timestamped with high precision
- UI must remain responsive even at maximum telemetry update rates
- File exports should be compatible with common analysis tools (Excel, Python pandas)
- Error logging should capture shared memory read failures for debugging

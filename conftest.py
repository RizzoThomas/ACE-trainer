"""Pytest configuration to ensure src/ is on sys.path for imports."""
import sys
from pathlib import Path

print(f"[conftest] BEFORE: sys.path = {sys.path}", file=sys.stderr)

# Insert src directory at the beginning of sys.path
project_root = Path(__file__).parent.resolve()
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
    print(f"[conftest] Added {src_dir} to sys.path at index 0", file=sys.stderr)
else:
    print(f"[conftest] {src_dir} already in sys.path", file=sys.stderr)

print(f"[conftest] AFTER: sys.path = {sys.path}", file=sys.stderr)

# Test import to verify connectivity
try:
    import telemetry.reader  # noqa: F401
    print("[conftest] Successfully imported telemetry.reader", file=sys.stderr)
except Exception as e:
    print(f"[conftest] FAILED to import telemetry.reader: {e}", file=sys.stderr)
    import traceback; traceback.print_exc()

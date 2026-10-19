"""Every signal Window.qml declares must be connected in Service.qml, and
every property the window receives from the service must be bound there.
Losing one fails silently in QML (a button that does nothing), so check it.

Run: python3 tests/test_wiring.py
"""

import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
window = (root / "Window.qml").read_text()
service = (root / "Service.qml").read_text()

# The window's own declarations (two-space indent: the root item's).
signals = re.findall(r"(?m)^  signal (\w+)\(", window)
properties = re.findall(r"(?m)^  property (?:bool|int|string|var|real) (\w+)", window)
# Properties the window keeps for itself, not set by the service.
own = {"sectionIndex", "selection", "actionCursor", "notice", "openedOn"}

missing = [f"signal {s}" for s in signals if f"item.{s}.connect(" not in service]
missing += [f"property {p}" for p in properties
            if p not in own and f"item.{p} = Qt.binding(" not in service]
if missing:
    print("Not wired in Service.qml:\n  " + "\n  ".join(missing))
    sys.exit(1)
print(f"ok: {len(signals)} signals and {len(properties) - len(own & set(properties))} properties wired")

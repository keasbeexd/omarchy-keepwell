"""The Accept sheet (ui/AcceptSheet.qml), run in Qt's offscreen renderer:
it opens on "Select all", the keyboard ticks rows and reaches Save, Save
is offered only when a tick changed, and Escape cancels. The shell's theme
singletons are stood in for by fixed values, so this needs only Qt's qml
tool. Set KEEPWELL_SHEET_PNG to also save a picture of the sheet.

Run: python3 tests/test_accept_sheet.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
qml = shutil.which("qml6") or ("/usr/lib/qt6/bin/qml" if os.path.exists("/usr/lib/qt6/bin/qml") else None)
if not qml:
    print("skipped: Qt's qml tool isn't installed, so the sheet wasn't run")
    sys.exit(0)

STUBS = {
    "Color.qml": 'pragma Singleton\nimport QtQuick\nQtObject { readonly property color foreground: "#e6e6e6"; '
                 'readonly property color background: "#1c1c1c"; readonly property color accent: "#7aa2f7"; '
                 'readonly property color urgent: "#f7768e" }\n',
    "Style.qml": 'pragma Singleton\nimport QtQuick\nQtObject { property int cornerRadius: 4; property var font: '
                 '({ family: "sans-serif", caption: 11, bodySmall: 12, body: 13, subtitle: 14, title: 16, heading: 18 }); '
                 'property var spacing: ({ hairline: 1, controlHeight: 28, rowPaddingX: 10, rowGap: 6 }); '
                 'function space(n) { return n } }\n',
    "Util.qml": 'pragma Singleton\nimport QtQuick\nQtObject { function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) } }\n',
    "qmldir": "module qs.Commons\nsingleton TestColor 1.0 Color.qml\nsingleton Style 1.0 Style.qml\nsingleton Util 1.0 Util.qml\n",
}
ITEMS = [{"key": "a" * 16, "label": "openssl", "detail": "High · crafted input could run code",
          "sub": "fixed in 3.0.2 — update · 2 CVEs", "on": True},
         {"key": "b" * 16, "label": "libxml2", "detail": "High · crafted input could crash it",
          "sub": "fixed in 2.13.1 — update · 4 CVEs", "on": False},
         {"key": "c" * 16, "label": "zlib", "detail": "Low · kind not recorded", "sub": "no fix released yet", "on": False}]
png = os.environ.get("KEEPWELL_SHEET_PNG", "")
MAIN = """
import QtQuick
import QtQuick.Window
import "ui"
Window {
  width: 760; height: 620; visible: true; color: "#1c1c1c"
  property var log: []
  AcceptSheet {
    id: sheet
    anchors.fill: parent
    title: "Accept findings: Known vulnerabilities"
    context: "Security · Known vulnerabilities"
    items: %(items)s
    checked: ({ "%(a)s": true })
    onToggled: function(key) { var n = {}; for (var k in checked) n[k] = checked[k];
                               if (n[key]) delete n[key]; else n[key] = true; checked = n; log.push("toggled " + key) }
    onAllToggled: log.push("all")
    onConfirmed: log.push("confirmed")
    onCanceled: log.push("canceled")
  }
  function key(k) { sheet.handleKey({ key: k, modifiers: 0 }) }
  function state(tag) { return [tag, sheet.cursor, sheet.changes, sheet.chosen.length] }
  Timer {
    interval: 300; running: true
    onTriggered: {
      var out = []
      sheet.opened = true
      out.push(state("open"))                     // cursor on Select all, nothing changed
      key(Qt.Key_Return); out.push(state("save before change"))   // Enter on Select all: "all", no save
      key(Qt.Key_J); key(Qt.Key_J); key(Qt.Key_Space); out.push(state("ticked libxml2"))
      key(Qt.Key_Tab); out.push(state("tab"))     // on Save
      key(Qt.Key_Return); out.push(state("saved"))
      key(Qt.Key_Escape)
      out.push(["log", log])
      console.warn("RESULT " + JSON.stringify(out))
      if ("%(png)s") sheet.grabToImage(function(r) { r.saveToFile("%(png)s"); Qt.quit() })
      else Qt.quit()
    }
  }
}
""" % {"items": json.dumps(ITEMS), "a": "a" * 16, "png": png}

tmp = tempfile.mkdtemp(prefix="keepwell-qml-")
try:
    os.makedirs(os.path.join(tmp, "qs", "Commons"))
    for name, text in STUBS.items():
        with open(os.path.join(tmp, "qs", "Commons", name), "w") as f:
            f.write(text)
    shutil.copytree(root / "ui", os.path.join(tmp, "ui"))
    # Qt's own QtQuick module has a Color singleton that wins over the stand-in
    # outside the shell, so the copy's Tokens.qml reads the stand-in by name.
    tokens = os.path.join(tmp, "ui", "Tokens.qml")
    with open(tokens) as f:
        src = f.read().replace("Color.", "TestColor.")
    with open(tokens, "w") as f:
        f.write(src)
    shutil.copytree(root / "model", os.path.join(tmp, "model"))
    with open(os.path.join(tmp, "main.qml"), "w") as f:
        f.write(MAIN)
    # Qt logs to the journal when stderr is not a terminal; keep it here.
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_FORCE_STDERR_LOGGING="1")
    proc = subprocess.run([qml, "-I", tmp, os.path.join(tmp, "main.qml")], cwd=tmp, env=env,
                          capture_output=True, timeout=60)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
text = (proc.stdout + proc.stderr).decode("utf-8", "replace")
line = next((l for l in text.splitlines() if "RESULT " in l), None)
if not line:
    print("the sheet didn't run (exit %s):\n%s" % (proc.returncode, text[-2000:]))
    sys.exit(1)
got = json.loads(line.split("RESULT ", 1)[1])
B = "b" * 16
want = [["open", 0, 0, 1], ["save before change", 0, 0, 1], ["ticked libxml2", 2, 1, 2],
        ["tab", 5, 1, 2], ["saved", 5, 1, 2], ["log", ["all", "toggled " + B, "confirmed", "canceled"]]]
warnings = [l for l in text.splitlines() if "AcceptSheet.qml" in l]
if got != want or warnings:
    print("got  %s\nwant %s\n%s" % (got, want, "\n".join(warnings)))
    sys.exit(1)
print("ok: the Accept sheet works from the keyboard and offers Save only for a change")

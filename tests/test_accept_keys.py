"""The keyboard reaches every Accepted box: Shift+Down/Up (or Shift+J/K)
steps through a check's findings that have one, Space ticks the one under
the cursor, and the cursor stays on that finding when ticking moves it.
Runs Window.qml's ackKeys, moveAck and toggleAck under node.

Run: python3 tests/test_accept_keys.py
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
node = shutil.which("node")
if not node:
    print("skipped: node isn't installed, so Window.qml's key functions weren't run")
    sys.exit(0)
window = (root / "Window.qml").read_text()
funcs = []
for name in ("ackKeys", "moveAck", "toggleAck"):
    m = re.search(r"(?ms)^  function %s\(.*?^  }$" % name, window)
    if not m:
        print("couldn't find %s in Window.qml" % name)
        sys.exit(1)
    funcs.append(m.group(0))
# The key handler must route Shift+J/K and Space to them.
handler = window[window.index("Keys.onPressed"):]
for want in ("shift && (event.key === Qt.Key_Down || event.key === Qt.Key_J)", "root.moveAck(1)",
             "shift && (event.key === Qt.Key_Up || event.key === Qt.Key_K)", "root.moveAck(-1)",
             "event.key === Qt.Key_Space", "root.toggleAck()"):
    if want not in handler:
        print("key handler lacks: " + want)
        sys.exit(1)
if handler.index("root.moveAck(1)") > handler.index("root.selectCheck(root.checkIndex + 1)"):
    print("Shift+J reaches plain j's branch first")
    sys.exit(1)

script = """
var sent = [];
var root = { check: null, ackCursor: "", actionCursor: 2,
             actionRequested: function(a, id, ctx) { sent.push(a) } };
with (root) { %s
  root.ackKeys = ackKeys; root.moveAck = moveAck; root.toggleAck = toggleAck }
function facts(on) {   // b accepted moves to the bottom, as Present.js orders them
  var a = { k: "openssl", ack: { check: "audit", key: "aaaaaaaaaaaaaaaa", on: false } }
  var b = { k: "zlib", ack: { check: "audit", key: "bbbbbbbbbbbbbbbb", on: on } }
  return on ? [{ k: "Checked" }, a, b] : [{ k: "Checked" }, b, a]
}
var out = [];
root.check = { id: "audit", facts: facts(false) };
out.push(root.ackKeys());
root.moveAck(1); out.push([root.ackCursor, root.actionCursor]);   // first box, button cursor off
root.moveAck(-1); out.push(root.ackCursor);                       // stays at the top
root.toggleAck(); out.push(sent[sent.length - 1]);                // ticks zlib
root.check = { id: "audit", facts: facts(true) };                 // zlib moved down
out.push(root.ackCursor);                                         // cursor followed it
root.toggleAck(); out.push(sent[sent.length - 1]);                // unticks zlib
root.moveAck(-1); out.push(root.ackCursor);
root.moveAck(5); out.push(root.ackCursor);                        // stops at the last
root.check = { id: "fw", facts: [{ k: "Status" }] };
root.ackCursor = "aaaaaaaaaaaaaaaa"; var n = sent.length; root.toggleAck();
out.push([sent.length - n, root.ackCursor]);                      // a stale cursor sends nothing
root.moveAck(1); out.push(root.ackCursor);                        // no boxes: nothing to move to
console.log(JSON.stringify(out));
""" % "\n".join(funcs)
proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
if proc.returncode != 0:
    print(proc.stderr.decode())
    sys.exit(1)
A, B = "a" * 16, "b" * 16
want = [[B, A], [B, -1], B, {"accept": B, "check": "audit", "on": True}, B,
        {"accept": B, "check": "audit", "on": False}, A, B, [0, ""], ""]
got = json.loads(proc.stdout)
if got != want:
    print("got  %s\nwant %s" % (got, want))
    sys.exit(1)
print("ok: the keyboard reaches every Accepted box and stays on the finding it ticked")

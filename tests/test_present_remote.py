"""The Remote access row may only say "No remote login running" when every
running program could be seen and no sshd runs from any unit, and only say
"keys only" when the checker had no doubt. Runs model/Present.js under node.

Run: python3 tests/test_present_remote.py
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
    print("skipped: node isn't installed, so model/Present.js wasn't run")
    sys.exit(0)


def body(name):
    text = (root / "model" / name).read_text()
    return "\n".join(l for l in text.splitlines() if not l.startswith((".pragma", ".import")))


status = body("Status.js")
names = re.findall(r"^function ([A-Za-z0-9_]+)", status, re.M)
BASE = {"installed": True, "enabled": "disabled", "active": "inactive", "socket": False, "passwords": False,
        "rootLogin": "no", "port": "22", "unsure": [], "firewallAllows": False, "authorizedKeys": 1,
        "keepwellKeysOnly": False}
CASES = [
    ("all off", {}, "good", "No remote login running"),
    ("sshd outside a service, units off", {"outside": 1, "unsure": ["an sshd runs outside a system service"]},
     "attn", "couldn't confirm keys only"),
    ("other unit running, units off", {"elsewhere": ["my-sshd.service"], "passwords": True},
     "attn", "accepts passwords"),
    ("processes hidden, units off", {"runningUnknown": True, "unsure": ["running programs couldn't be listed"]},
     "attn", "couldn't see every running program"),
    ("on, unsure", {"active": "active", "unsure": ["x"]}, "attn", "couldn't confirm keys only"),
    ("on, keys only", {"active": "active"}, "good", "keys only"),
]
script = status + "\nvar Status = {%s};\n" % ",".join("%s: %s" % (n, n) for n in names) + body("Present.js") + """
var base = %s, cases = %s, out = [];
cases.forEach(function(c) { var r = remote(Object.assign({}, base, c[1]));
  out.push([c[0], r.kind, r.status, (r.facts || []).map(function(f) { return f.k + ": " + f.v })]) });
console.log(JSON.stringify(out));
""" % (json.dumps(BASE), json.dumps(CASES))
proc = subprocess.run([node, "-"], input=script.encode(), capture_output=True, timeout=30)
if proc.returncode != 0:
    print(proc.stderr.decode())
    sys.exit(1)
bad = []
for (name, _, kind, words), (_, got_kind, got_status, facts) in zip(CASES, json.loads(proc.stdout)):
    if got_kind != kind or words not in got_status:
        bad.append("%s: %s %r" % (name, got_kind, got_status))
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: %d Remote access states shown as they should be" % len(CASES))

"""A ClamAV scan only counts as clean when clamscan printed its summary,
exited 0 or 1, reported no errors, and every listed file was handed to it.
ClamAV 1.5.4 exits 2 after a normal summary when it can't read a file, so
that case must come out incomplete, never "nothing found".

Run: python3 tests/test_clam_outcome.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import keepwell_av  # noqa: E402

SUMMARY = """
----------- SCAN SUMMARY -----------
Known viruses: 3628258
Engine version: 1.5.4
Scanned directories: 0
Scanned files: %d
Infected files: %d
%sData scanned: 0 B
Time: 4.637 sec (0 m 4 s)
"""


def log(files=2, infected=0, errors=0, rc=0, odd=0, found=""):
    text = found + SUMMARY % (files, infected, "Total errors: %d\n" % errors if errors else "")
    if odd:
        text += "Keepwell: %d file(s) with control characters in their names were not scanned\n" % odd
    if rc is not None:
        text += "Keepwell: clamscan exit status %d\n" % rc
    return text


cases = [
    ("clean", log(), True),
    ("infected, exit 1", log(infected=1, rc=1, found="/home/u/x.exe: Win.Test FOUND\n"), True),
    ("unreadable file, exit 2", log(files=1, errors=1, rc=2), False),
    ("errors but exit 0", log(errors=1, rc=0), False),
    ("exit 2, no error count", log(rc=2), False),
    ("killed after summary", log(rc=-15), False),
    ("names skipped", log(odd=3), False),
    ("no status line (older log)", log(rc=None), False),
    ("no summary", "Scanning /home/u/a\n", False),
    # A status line before the last summary must not answer for it.
    ("status only before summary", "Keepwell: clamscan exit status 0\n" + log(rc=None), False),
]

bad = []
for name, text, want in cases:
    got = keepwell_av.outcome(text)
    if got["complete"] is not want:
        bad.append("%s: complete=%s, want %s (%r)" % (name, got["complete"], want, got))
    elif not want and got["finished"] and not keepwell_av.incomplete_text(got):
        bad.append("%s: no reason given" % name)

o = keepwell_av.outcome(log(files=1, errors=1, rc=2))
if keepwell_av.incomplete_text(o) != "1 file couldn't be read":
    bad.append("reason text: %r" % keepwell_av.incomplete_text(o))

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: %d scan outcomes" % len(cases))

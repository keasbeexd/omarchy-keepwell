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


def log(files=2, infected=0, errors=0, rc=0, odd=0, unread=0, found=""):
    text = found + SUMMARY % (files, infected, "Total errors: %d\n" % errors if errors else "")
    if odd:
        text += "Keepwell: %d file(s) with control characters in their names were not scanned\n" % odd
    if unread:
        text += "Keepwell: %d folder(s) or file(s) couldn't be read and were not scanned\n" % unread
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
    ("folder couldn't be listed", log(unread=1), False),
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

# The listing itself: an unreadable folder below the scanned one is counted,
# so its files are never silently missing from a "complete" scan.
import io, os, runpy, tempfile  # noqa: E402
if os.geteuid() != 0:
    run = runpy.run_path(str(Path(__file__).resolve().parent.parent / "bin" / "keepwell-run"), run_name="keepwell_run")
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "locked", "inner"))
        os.makedirs(os.path.join(root, "skipme"))
        for rel in ("a.txt", "locked/inner/b.txt", "skipme/c.txt"):
            open(os.path.join(root, rel), "w").close()
        os.symlink("/etc/passwd", os.path.join(root, "link"))
        listing = io.BytesIO()
        got = run["_list_files"](root, [os.path.join(root, "skipme")], listing)
        if got != (2, 0, 0) or listing.getvalue().count(b"\n") != 2:
            bad.append("readable tree: %r" % (got,))
        os.chmod(os.path.join(root, "locked"), 0)
        try:
            listing = io.BytesIO()
            got = run["_list_files"](root, [os.path.join(root, "skipme")], listing)
            if got != (1, 0, 1):
                bad.append("unreadable folder: got %r, want (1, 0, 1)" % (got,))
            got = run["_list_files"](os.path.join(root, "missing"), [], io.BytesIO())
            if got != (0, 0, 1):
                bad.append("missing root: got %r, want (0, 0, 1)" % (got,))
        finally:
            os.chmod(os.path.join(root, "locked"), 0o700)

        class Full(io.BytesIO):
            def write(self, b):
                raise OSError(28, "No space left on device")
        try:
            run["_list_files"](root, [], Full())
            bad.append("a failed write to the file list was swallowed")
        except OSError:
            pass

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: %d scan outcomes" % len(cases))

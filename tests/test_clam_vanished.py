"""A home scan takes hours, and files come and go while it runs. A file
deleted between Keepwell listing it and clamscan reaching it makes clamscan
exit 2 with nothing to scan. Such a scan must still count as complete, but
only when Keepwell checked each such file again and it is really gone:
not when it came back, was swapped for something clamscan can't read, sat in
Downloads, or when far more vanished than a home folder's usual churn. Any
file that wasn't scanned is named in the log, with clamscan's reason.

Runs the real clam_scan and /usr/bin/clamscan, with a one-signature database
instead of ClamAV's, in a throwaway HOME.

Run: python3 tests/test_clam_vanished.py
"""

import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "bin"))
if not os.path.exists("/usr/bin/clamscan"):
    print("skipped: ClamAV isn't installed")
    sys.exit(0)

bad = []


def scan(target, before, after=lambda home: None, odd=False):
    """Runs clam_scan on a fresh HOME. before(home) runs once the list is
    written and clamscan is about to start; after(home) once it has exited.
    Returns (exit code, outcome, log text)."""
    with tempfile.TemporaryDirectory() as home:
        os.environ["HOME"] = home
        for mod in ("keepwell_state", "keepwell_av"):
            sys.modules.pop(mod, None)
        os.makedirs(os.path.join(home, "Downloads"))
        os.makedirs(os.path.join(home, ".cache", "mise"))
        for rel, body in (("a.txt", "hi"), ("gone.txt", "x"), ("a: b.txt", "x"), ("back.txt", "x"),
                          ("swap.txt", "x"), ("Downloads/dl.txt", "x"), (".cache/mise/tool", "keepwelltest")):
            Path(home, rel).write_text(body)
        if odd:
            Path(home, "line\nbreak.txt").write_text("x")
        sig = os.path.join(home, "t.ndb")
        Path(sig).write_text("Test.Sig:0:*:6b65657077656c6c74657374\n")
        run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
        real = subprocess.Popen

        class Proc(real):
            def wait(self, *a, **k):
                rc = super().wait(*a, **k)
                after(home)
                return rc

        class Shim:
            PIPE, DEVNULL = subprocess.PIPE, subprocess.DEVNULL

            @staticmethod
            def Popen(argv, **kw):
                before(home)
                return Proc([argv[0], "-d", sig] + argv[1:], **kw)

        # run_path hands back a copy of the globals; patch the ones clam_scan uses.
        run["clam_scan"].__globals__["subprocess"] = Shim
        rc = run["clam_scan"](target)
        st = run["keepwell_state"]
        name, raw = st.latest_log(target)
        text = raw.decode("utf-8", "replace")
        import keepwell_av
        return rc, keepwell_av.outcome(text), text


def rm(*rels):
    return lambda home: [os.unlink(os.path.join(home, r)) for r in rels]


def check(name, got, want):
    if got != want:
        bad.append("%s: got %r, want %r" % (name, got, want))


# 1. Files deleted mid-scan, one with ": " in its name: complete, and said.
rc, o, log = scan("home", rm("gone.txt", "a: b.txt"))
check("vanished: complete", o["complete"], True)
check("vanished: count", (o["vanished"], o["vanishedDownloads"], o["notScanned"]), (2, 0, 0))
check("vanished: ~/.cache scanned, tool found", "/.cache/mise/tool: Test.Sig.UNOFFICIAL FOUND" in log, True)
check("vanished: exit code", rc, 0)

# 2. Deleted, then made again while clamscan ran: never scanned.
rc, o, log = scan("home", rm("back.txt"), lambda h: Path(h, "back.txt").write_text("x"))
check("came back: complete", o["complete"], False)
check("came back: counted", (o["vanished"], o["notScanned"]), (0, 1))
check("came back: named", any(i.endswith("/back.txt: came back after clamscan couldn't open it")
                              for i in o["notScannedItems"]), True)

# 3. Swapped for a FIFO: clamscan's own reason is kept.
def fifo(home):
    os.unlink(os.path.join(home, "swap.txt"))
    os.mkfifo(os.path.join(home, "swap.txt"))
rc, o, log = scan("home", fifo)
check("fifo: complete", o["complete"], False)
check("fifo: reason", any(i.endswith("/swap.txt: Not supported file type") for i in o["notScannedItems"]), True)

# 4. A file in Downloads vanished: incomplete, in a home scan and a Downloads scan.
for target in ("home", "downloads"):
    rc, o, log = scan(target, rm("Downloads/dl.txt"))
    check("downloads (%s): complete" % target, o["complete"], False)
    check("downloads (%s): count" % target, o["vanishedDownloads"], 1)

# 5. A name with a line break: not scanned, named with the break escaped.
rc, o, log = scan("home", lambda h: None, odd=True)
check("odd name: complete", o["complete"], False)
check("odd name: shown", o["oddItems"] and o["oddItems"][0].endswith("/line\\x0abreak.txt"), True)
check("odd name: log has no raw break", "line\nbreak" in log, False)

# 6. Nothing odd at all: complete, exit 1 for the found tool.
rc, o, log = scan("home", lambda h: None)
check("clean: complete", (o["complete"], o["rc"], rc), (True, 1, 0))

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: vanished files count only when they're really gone, and every unscanned file is named")

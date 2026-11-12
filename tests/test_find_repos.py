"""The repository search behind the secrets and dependency scans must say
what it couldn't cover: an unreadable folder, a missing root, a search cut
short by its limits. Otherwise a scan of the repositories it did find would
be shown as covering the whole folder.

Run: python3 tests/test_find_repos.py
"""

import os
import runpy
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "bin"))
run = runpy.run_path(str(root / "bin" / "keepwell-run"), run_name="keepwell_run")
find_repos, gap_text = run["find_repos"], run["search_gap_text"]
bad = []
top = tempfile.mkdtemp(prefix="keepwell-test-")
try:
    for name in ("a", "b", "locked/c", "node_modules/d", ".hidden/e"):
        os.makedirs(os.path.join(top, name, ".git"))

    repos, gaps = find_repos(top)
    names = sorted(os.path.relpath(r, top) for r in repos)
    if names != ["a", "b", "locked/c"] or gaps != {"unlisted": 0, "cut": ""}:
        bad.append("readable tree: %r %r" % (names, gaps))
    if gap_text(gaps):
        bad.append("a full search has a gap text: %r" % gap_text(gaps))

    if os.geteuid() != 0:
        os.chmod(os.path.join(top, "locked"), 0)
        try:
            repos, gaps = find_repos(top)
            if gaps["unlisted"] != 1 or len(repos) != 2:
                bad.append("unreadable folder: %r %r" % (repos, gaps))
            if "1 folder couldn't be searched" not in gap_text(gaps):
                bad.append("gap text: %r" % gap_text(gaps))
        finally:
            os.chmod(os.path.join(top, "locked"), 0o700)

    _, gaps = find_repos(os.path.join(top, "missing"))
    if gaps["unlisted"] != 1:
        bad.append("missing root: %r" % gaps)

    _, gaps = find_repos(top, limit=1)
    if gaps["cut"] != "limit" or "stopped at 100" not in gap_text(gaps):
        bad.append("repository limit: %r" % gaps)

    _, gaps = find_repos(top, seconds=0)
    if gaps["cut"] != "time":
        bad.append("time limit: %r" % gaps)

    wide = os.path.join(top, "wide")
    os.makedirs(wide)
    for i in range(2001):
        open(os.path.join(wide, "f%04d" % i), "w").close()
    _, gaps = find_repos(wide)
    if gaps["cut"] != "entries":
        bad.append("2,000 entry limit: %r" % gaps)
finally:
    shutil.rmtree(top, ignore_errors=True)

if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ok: the repository search reports what it couldn't cover")

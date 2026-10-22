"""What the newest ClamAV scan found, minus the files you marked as not a
threat.

A file is marked by its path and its SHA-256. A marked file stays hidden
only while its contents are unchanged: if it is replaced or modified, the
hash no longer matches and the next scan that flags it shows it again. The
scanner itself is never told; it still reads the file and reports it, and
Keepwell leaves the match out of the check, the notification and the count.

Kept in ~/.local/state/keepwell/av-allowed.json:
  {"allowed": [{"path": "/home/you/...", "sha256": "<64 hex>", "signature": "..."}]}
"""

import hashlib
import json
import os
import re
import stat

import keepwell_state

HOME = os.path.expanduser("~")
UID = os.geteuid()
FILE = "av-allowed.json"
LIMIT = 200                    # entries kept
HASH_CAP = 512 << 20           # larger files are never treated as allowed
FOUND = re.compile(r"(?m)^(/.+): ([^:\n]+) FOUND$")


def summary(log):
    """Just clamscan's final SCAN SUMMARY block, so no earlier line can
    answer for it."""
    marker = "----------- SCAN SUMMARY -----------"
    return log.rsplit(marker, 1)[1] if marker in log else ""


def findings(log):
    """[(path, signature)] named in a scan log, at most 50, in log order."""
    out = []
    for m in FOUND.finditer(log):
        if m.group(1) not in [p for p, _ in out]:
            out.append((m.group(1), m.group(2).strip()))
        if len(out) >= 50:
            break
    return out


def item_id(path):
    """A short, stable id for a found file that the window can hand back
    without passing a path through argv."""
    return hashlib.sha256(path.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def sha256(path):
    """The file's SHA-256, or None when it can't be read safely: not a
    regular file you own, a symlink, or too large."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != UID or st.st_size > HASH_CAP:
            return None
        os.set_blocking(fd, True)
        h = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                return h.hexdigest()
            h.update(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)


def allowed():
    """The marked files, as {path: sha256}."""
    doc = keepwell_state.read_json(FILE) or {}
    out = {}
    for e in doc.get("allowed") or []:
        if isinstance(e, dict) and isinstance(e.get("path"), str) and e["path"].startswith("/") \
                and isinstance(e.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", e["sha256"]):
            out[e["path"]] = e["sha256"]
    return out


def split(found, marks=None):
    """(shown, hidden): the findings still to show, and those marked as not
    a threat whose contents haven't changed since."""
    marks = allowed() if marks is None else marks
    shown, hidden = [], []
    for path, sig in found:
        want = marks.get(path)
        (hidden if want and sha256(path) == want else shown).append((path, sig))
    return shown, hidden


def allow(path, signature):
    """Mark one found file as not a threat. False when it can't be hashed."""
    digest = sha256(path)
    if not digest:
        return False
    doc = keepwell_state.read_json(FILE) or {}
    entries = [e for e in doc.get("allowed") or [] if isinstance(e, dict) and e.get("path") != path]
    entries.append({"path": path, "sha256": digest, "signature": signature[:120]})
    keepwell_state.write(FILE, json.dumps({"allowed": entries[-LIMIT:]}).encode())
    return True


def forget_all():
    keepwell_state.remove(FILE)


def count():
    return len(allowed())

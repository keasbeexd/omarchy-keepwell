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


STATUS = re.compile(r"(?m)^Keepwell: clamscan exit status (-?\d+)$")
ERRORS = re.compile(r"(?m)^Total errors: (\d+)$")
SCANNED = re.compile(r"(?m)^Scanned files: (\d+)$")
UNLISTED = re.compile(r"(?m)^Keepwell: (\d+) file\(s\) with control characters in their names were not scanned$")
UNREAD = re.compile(r"(?m)^Keepwell: (\d+) folder\(s\) or file\(s\) couldn't be read and were not scanned$")
VANISHED = re.compile(r"(?m)^Keepwell: (\d+) file\(s\) were deleted during the scan, (\d+) of them in Downloads$")
NOTSCANNED = re.compile(r"(?m)^Keepwell: (\d+) file\(s\) couldn't be scanned$")
OTHER = re.compile(r"(?m)^Keepwell: clamscan reported (\d+) other error\(s\)$")
NOTSCANNED_ITEM = re.compile(r"(?m)^Keepwell: not scanned: (/.+)$")
ODD_ITEM = re.compile(r"(?m)^Keepwell: unusual name, not scanned: (/.+)$")
SAID_ITEM = re.compile(r"(?m)^Keepwell: clamscan said: (.+)$")


def vanish_limit(scanned):
    """How many files may disappear during a scan before that alone makes it
    incomplete: 1% of the files scanned, and at least 100. A home folder
    always has some churn (browser profiles, editor swap files); far more
    than that is not ordinary."""
    return max(100, (scanned or 0) // 100)


def outcome(log):
    """How a scan log ended: {finished, complete, rc, errors, unscanned,
    unreadable, vanished, vanishedDownloads, notScanned, otherErrors, ...}.
    finished: clamscan printed its final summary. complete: it also exited
    0 or 1 with no errors, listing the folder reached every file in it, and
    every file it couldn't open was checked afterwards and is really gone.

    A file deleted between Keepwell listing it and clamscan reaching it makes
    clamscan exit 2 with no error count, though there is nothing left to
    scan. Keepwell checks each one again after the scan and writes how many
    are really gone; only then does exit 2 count, and only when no other
    error was reported, fewer than vanish_limit() files vanished and none of
    them was in Downloads, where files don't normally come and go. Anything
    else (a file clamscan couldn't read, a folder Keepwell couldn't list, an
    unexplained exit 2, a log from before Keepwell recorded the status) is
    never reported as a clean scan. Only lines after the last summary
    count: clamscan's own, then the ones Keepwell writes after it exits.
    Paths in the log are absolute, so no file name can start one of these
    lines."""
    tail = summary(log)

    def num(rx, group=1):
        m = rx.search(tail)
        return int(m.group(group)) if m else 0

    rc = STATUS.search(tail)
    out = {"finished": bool(tail), "rc": int(rc.group(1)) if rc else None,
           "errors": num(ERRORS), "unscanned": num(UNLISTED), "unreadable": num(UNREAD),
           "vanished": num(VANISHED), "vanishedDownloads": num(VANISHED, 2),
           "notScanned": num(NOTSCANNED), "otherErrors": num(OTHER),
           "scanned": num(SCANNED),
           "notScannedItems": NOTSCANNED_ITEM.findall(tail)[:5],
           "oddItems": ODD_ITEM.findall(tail)[:5],
           "said": SAID_ITEM.findall(tail)[:3]}
    out["tooManyVanished"] = out["vanished"] > vanish_limit(out["scanned"])
    explained = out["rc"] == 2 and out["vanished"] > 0 and not out["otherErrors"]
    out["complete"] = (out["finished"] and (out["rc"] in (0, 1) or explained)
                       and not out["errors"] and not out["unscanned"] and not out["unreadable"]
                       and not out["notScanned"] and not out["vanishedDownloads"]
                       and not out["tooManyVanished"])
    return out


def _n(count, one, many):
    return "%d %s" % (count, one if count == 1 else many)


def incomplete_text(o):
    """Why a finished scan doesn't count as complete, in a few words."""
    why = []
    if o["errors"]:
        why.append(_n(o["errors"], "file", "files") + " couldn't be read")
    if o.get("notScanned"):
        why.append(_n(o["notScanned"], "file", "files") + " couldn't be scanned")
    if o["unreadable"]:
        why.append(_n(o["unreadable"], "folder", "folders") + " couldn't be listed")
    if o["unscanned"]:
        why.append(_n(o["unscanned"], "file", "files") + " with unusual names skipped")
    if o.get("vanishedDownloads"):
        why.append(_n(o["vanishedDownloads"], "file", "files") + " in Downloads deleted or renamed during the scan")
    if o.get("tooManyVanished"):
        why.append(_n(o["vanished"], "file", "files") + " deleted during the scan, more than usual")
    if not why:
        why.append("ClamAV stopped with an error" if o["rc"] is not None else "ClamAV's exit status wasn't recorded")
    return ", ".join(why)


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

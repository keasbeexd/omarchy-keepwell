"""Findings you have looked at and decided to live with ("accepted").

An accepted finding stays on screen, greyed out, but no longer raises the
check's state, the shield or a notification. Each finding is named by a key
made from everything that describes it, so a change brings it back: a new
CVE or a new fixed version for a package, a new vulnerability or version
for a dependency, a secret found in another commit or line.

The key is the first 16 hex digits of a SHA-256 over the finding's fields,
made here and only here: bin/keepwell-check attaches it to each finding
("ack"), the window sends it back to accept or un-accept one, and
bin/keepwell-run uses it to leave accepted findings out of its
notifications.

Kept in ~/.local/state/keepwell/accepted.json:
  {"accepted": {"audit": ["<16 hex>", ...], "deps": [...], ...}}
"""

import hashlib
import json
import re

import keepwell_state

FILE = "accepted.json"
CHECKS = ("audit", "deps", "leaks", "outside", "failed")
LIMIT = 200                    # keys kept per check, the newest
KEY = re.compile(r"[0-9a-f]{16}")


def _key(check, *fields):
    raw = json.dumps([check] + [str(f) for f in fields], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def audit_key(name, severity, fixed, cves):
    """A package arch-audit names. cves: every CVE id in its line."""
    return _key("audit", name, severity, fixed, ",".join(sorted(set(cves))))


def dep_key(folder, f):
    """A dependency osv-scanner flagged, in the scan of folder."""
    ids = sorted(str(v.get("id", "")) for v in f.get("vulns") or [] if isinstance(v, dict))
    return _key("deps", folder, f.get("repo", ""), f.get("file", ""), f.get("package", ""),
                f.get("version", ""), ",".join(ids))


def leak_key(folder, f):
    """A possible secret gitleaks found, in the scan of folder."""
    return _key("leaks", folder, f.get("repo", ""), f.get("file", ""), f.get("line", 0),
                f.get("rule", ""), f.get("commit", ""))


def outside_key(kind, name, where=""):
    """Software omarchy update misses: kind "hand" (a program copied in,
    where it is) or "aur" (a package no longer in the AUR)."""
    return _key("outside", kind, name, where)


def failed_key(unit, user):
    return _key("failed", unit, bool(user))


def load():
    """{check: [keys]} for every check, oldest first. Anything malformed is
    left out, never taken as accepted."""
    try:
        doc = keepwell_state.read_json(FILE) or {}
    except (OSError, ValueError):
        doc = {}
    got = doc.get("accepted") if isinstance(doc, dict) else None
    got = got if isinstance(got, dict) else {}
    out = {}
    for check in CHECKS:
        keys = got.get(check)
        keys = [k for k in keys if isinstance(k, str) and KEY.fullmatch(k)] if isinstance(keys, list) else []
        out[check] = list(dict.fromkeys(keys))[-LIMIT:]
    return out


def accepted(check):
    return set(load().get(check, []))


def apply(check, changes):
    """Apply changes, each "+<key>" (accept) or "-<key>" (stop accepting),
    in one write. False, and nothing written, for an unknown check, a
    malformed change or more than LIMIT of them."""
    if check not in CHECKS or not isinstance(changes, list) or not 0 < len(changes) <= LIMIT:
        return False
    if not all(isinstance(c, str) and c[:1] in ("+", "-") and KEY.fullmatch(c[1:]) for c in changes):
        return False
    doc = load()
    keys = doc[check]
    for c in changes:
        keys = [k for k in keys if k != c[1:]]
        if c[0] == "+":
            keys.append(c[1:])
    doc[check] = keys[-LIMIT:]
    keepwell_state.write(FILE, json.dumps({"accepted": doc}, separators=(",", ":")).encode())
    return True


def mark(check, key, on):
    """Accept (on) or stop accepting one finding."""
    return apply(check, [("+" if on else "-") + str(key)])

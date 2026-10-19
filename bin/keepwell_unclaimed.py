"""The unclaimed-files finder: app folders in your home that nothing
installed still claims, and that haven't changed in a long time.

pacman never installs into a home folder, so "owned by a package" says
nothing there. Instead a folder is claimed when its name matches something
that is installed or expected:
  - a package name (pacman -Qq), or a program in /usr/bin, ~/.local/bin or
    mise's shims;
  - a desktop app entry, by file name or the last part of a reverse-DNS id;
  - a Flatpak app;
  - a folder Omarchy's own files mention (.config/<name>, .local/share/<name>),
    since Omarchy creates folders for apps you may install later;
  - a standard desktop location (keyrings, Trash, autostart…).
Matching leans towards "claimed": a name that starts like something
installed (or that something installed starts like) is never suggested. A folder is only suggested when nothing claims it AND nothing
inside it has changed for the chosen number of days.

Only three places are looked at: hidden entries directly in ~, and entries
in ~/.config and ~/.local/share. Your own files (Documents and the like) are
never looked at, and symlinks are never suggested.
"""

import json
import os
import re
import select
import signal
import stat
import subprocess
import time

import keepwell_state

HOME = os.path.expanduser("~")
UID = os.geteuid()
ROOTS = (("", True), (".config", False), (".local/share", False))
DAY_CHOICES = (90, 180, 365, 730)
DEFAULT_DAYS = 180
ENTRY_BUDGET = 8000          # entries examined across all candidates
PER_FOLDER = 600             # entries examined inside one folder
SECONDS = 4.0

# Names that belong to the desktop or the shell rather than to an app.
STANDARD = {
    "config", "local", "cache", "share", "state", "bin", "ssh", "gnupg", "pki", "var", "icons", "themes",
    "fonts", "bashrc", "bashprofile", "bashlogout", "bashhistory", "profile", "inputrc", "xcompose",
    "xresources", "xinitrc", "xprofile", "gitconfig", "trash", "keyrings", "autostart", "applications",
    "desktopdirectories", "mime", "mimeappslist", "recentlyusedxbel", "systemd", "environmentd", "dconf",
    "userdirsdirs", "userdirslocale", "menus", "sounds", "icc", "gvfsmetadata", "xdgdesktopportal",
    "fontconfig", "pulse", "pulsecookie", "wireplumber", "gtk20", "gtk30", "gtk40", "gtkrc20", "qtprojectconf",
    "uwsm", "keepwell", "lesshst", "wget-hsts", "wgethsts", "python_history", "pythonhistory", "nodereplhistory",
    "sqlitehistory", "viminfo", "kdeglobals", "trolltech", "trolltechconf", "flatpak", "packagekit",
}

SKIP_NAMES = {".config", ".local", ".cache"}


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _capture(argv, timeout=10.0, cap=4 << 20):
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env={"PATH": "/usr/bin", "LC_ALL": "C"}, cwd="/", start_new_session=True)
    except OSError:
        return ""
    deadline, out, size = time.monotonic() + timeout, [], 0
    fd = proc.stdout.fileno()
    while True:
        left = deadline - time.monotonic()
        if left <= 0 or size > cap:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return ""
        if not select.select([fd], [], [], left)[0]:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        size += len(chunk)
        out.append(chunk)
    proc.stdout.close()
    proc.wait()
    return b"".join(out).decode("utf-8", "replace") if proc.returncode == 0 else ""


def _names(directory, limit=20000):
    try:
        return os.listdir(directory)[:limit]
    except OSError:
        return []


def _omarchy_mentions(budget_bytes=24 << 20):
    """Folder names Omarchy's own scripts and configs refer to under
    .config or .local/share. Text files only, bounded."""
    found, used = set(), 0
    pattern = re.compile(rb"\.(?:config|local/share)/([A-Za-z0-9._-]+)")
    for root, dirs, files in os.walk("/usr/share/omarchy"):
        dirs[:] = [d for d in dirs if d not in ("themes", "backgrounds", "icons", ".git")]
        for f in files:
            if f.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ttf", ".otf", ".woff2")):
                continue
            path = os.path.join(root, f)
            try:
                st = os.lstat(path)
                if not stat.S_ISREG(st.st_mode) or st.st_size > 512 * 1024:
                    continue
                if used + st.st_size > budget_bytes:
                    return found
                with open(path, "rb") as fh:
                    data = fh.read(512 * 1024)
                used += len(data)
            except OSError:
                continue
            found.update(m.group(1).decode() for m in pattern.finditer(data))
    return found


# Bump when the way claims are gathered changes, so an old cache is rebuilt.
CLAIMS_VERSION = 2


def _cache_key():
    """Claims change when packages do; pacman's database records that."""
    try:
        return "%d-%d" % (CLAIMS_VERSION, int(os.stat("/var/lib/pacman/local").st_mtime))
    except OSError:
        return "%d-0" % CLAIMS_VERSION


def _stable_claims():
    key = _cache_key()
    try:
        cached = keepwell_state.read_json("claims.json")
    except (OSError, ValueError):
        cached = None
    if cached and cached.get("key") == key and isinstance(cached.get("tokens"), list):
        return set(cached["tokens"])
    tokens = set()
    tokens.update(norm(p) for p in _capture(["/usr/bin/pacman", "-Qq"]).split())
    tokens.update(norm(n) for n in _names("/usr/bin"))
    for d in ("/usr/share/applications", "/var/lib/flatpak/exports/share/applications"):
        for n in _names(d):
            if n.endswith(".desktop"):
                tokens.add(norm(n[:-8]))
                tokens.add(norm(n[:-8].split(".")[-1]))
    tokens.update(norm(n) for n in _omarchy_mentions())
    tokens.update(norm(n) for n in _names("/usr/share/omarchy/config"))
    tokens.discard("")
    try:
        keepwell_state.write("claims.json", json.dumps({"key": key, "tokens": sorted(tokens)}).encode())
    except (OSError, ValueError):
        pass
    return tokens


def claims():
    """Everything that claims a name: the cached system part plus the parts
    of your home that change without pacman (local programs, Flatpak apps)."""
    tokens = _stable_claims() | STANDARD
    for d in (os.path.join(HOME, ".local", "bin"), os.path.join(HOME, ".local", "share", "mise", "shims"),
              os.path.join(HOME, ".local", "share", "applications"), os.path.join(HOME, ".var", "app")):
        for n in _names(d, 2000):
            base = n[:-8] if n.endswith(".desktop") else n
            tokens.add(norm(base))
            tokens.add(norm(base.split(".")[-1]))
    tokens.discard("")
    return tokens


def claimed(name, tokens):
    n = norm(name)
    if len(n) < 3 or n in tokens:
        return True
    # A prefix either way: "hypr" is claimed by "hyprland", "gtk-3.0" by
    # "gtk3". Not a substring anywhere: /usr/bin has short common names
    # ("test", "file") that would claim almost everything.
    return any(len(t) >= 4 and n.startswith(t) for t in tokens) or \
        (len(n) >= 4 and any(t.startswith(n) for t in tokens))


def settings():
    try:
        doc = keepwell_state.read_json("unclaimed.json") or {}
    except (OSError, ValueError):
        doc = {}
    days = doc.get("days") if doc.get("days") in DAY_CHOICES else DEFAULT_DAYS
    ignored = [i for i in doc.get("ignored", []) if isinstance(i, str) and _valid_id(i)][:500]
    return {"days": days, "ignored": ignored}


def save_settings(days, ignored):
    keepwell_state.write("unclaimed.json", json.dumps({"days": days, "ignored": sorted(set(ignored))[:500]}).encode())


def _valid_id(item):
    parts = item.split("/")
    if len(parts) == 1:
        return parts[0].startswith(".") and _plain_name(parts[0])
    prefix, name = "/".join(parts[:-1]), parts[-1]
    return prefix in (".config", ".local/share") and _plain_name(name)


def _plain_name(name):
    return bool(re.fullmatch(r"[A-Za-z0-9._@+ -]{1,128}", name)) and name not in (".", "..")


def _look(path, budget, deadline):
    """(newest mtime, bytes, complete) of a folder or file, never following
    symlinks; incomplete when a budget ran out."""
    st = os.lstat(path)
    newest, total = st.st_mtime, st.st_blocks * 512
    if not stat.S_ISDIR(st.st_mode):
        return newest, total, True
    seen, stack = 0, [path]
    while stack:
        if seen >= PER_FOLDER or budget[0] <= 0 or time.monotonic() > deadline:
            return newest, total, False
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    seen += 1
                    budget[0] -= 1
                    try:
                        s = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    newest = max(newest, s.st_mtime)
                    if stat.S_ISDIR(s.st_mode):
                        stack.append(e.path)
                    else:
                        total += s.st_blocks * 512
        except OSError:
            continue
    return newest, total, True


def find(days=None, ignored=None):
    """Candidates, oldest first: {id, path, bytes, days}. A folder whose
    contents couldn't all be looked at is left out, since something inside
    it may have changed recently."""
    conf = settings()
    days = conf["days"] if days is None else days
    ignored = set(conf["ignored"] if ignored is None else ignored)
    tokens = claims()
    now, deadline, budget = time.time(), time.monotonic() + SECONDS, [ENTRY_BUDGET]
    out, looked = [], 0
    for rel, dot_only in ROOTS:
        base = os.path.join(HOME, rel) if rel else HOME
        for name in sorted(_names(base, 1000)):
            if dot_only and (not name.startswith(".") or name in SKIP_NAMES):
                continue
            item = os.path.join(rel, name) if rel else name
            if item in ignored or not _valid_id(item) or claimed(name, tokens):
                continue
            path = os.path.join(base, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode) or st.st_uid != UID:
                continue
            looked += 1
            try:
                newest, size, complete = _look(path, budget, deadline)
            except OSError:
                continue
            age = int((now - newest) // 86400)
            if complete and age >= days:
                out.append({"id": item, "path": "~/" + item, "bytes": size, "days": age})
    out.sort(key=lambda c: -c["days"])
    return {"days": days, "ignored": len(ignored), "looked": looked, "items": out[:60]}


def resolve(item):
    """The path for a candidate id, only if it is still a candidate now."""
    if not _valid_id(item):
        return None
    ids = {c["id"] for c in find()["items"]}
    return os.path.join(HOME, item) if item in ids else None

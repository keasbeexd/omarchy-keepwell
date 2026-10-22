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

It also finds broken launchers: your own app entries and autostart entries
(.desktop files) whose program is gone, usually left by an app you removed or
by a Wine game you deleted. Here too it leans towards "fine": an entry is
only broken when the program it names is clearly missing.
"""

import json
import os
import re
import select
import shlex
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

# C0 and C1 controls and the characters that reorder text on screen, so a
# name can't break a line or show itself backwards.
UNSAFE_TEXT = re.compile("[\x00-\x1f\x7f-\x9f؜‎‏‪-‮⁦-⁩]")


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _capture(argv, timeout=10.0, cap=4 << 20):
    env = {"PATH": "/usr/bin", "LC_ALL": "C"}
    # `systemctl --user` reaches your session's service manager through these.
    env.update({k: os.environ[k] for k in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS") if k in os.environ})
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=env, cwd="/", start_new_session=True)
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


def _read_regular(path, cap, owner=None):
    """(bytes, stat) of a regular file read through one descriptor, or None:
    a symlink, a FIFO or other special file, a file owned by someone other
    than owner (when given) or one larger than cap is refused, not cut short."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > cap or (owner is not None and st.st_uid != owner):
            return None
        os.set_blocking(fd, True)
        data = b""
        while len(data) <= cap:
            chunk = os.read(fd, cap + 1 - len(data))
            if not chunk:
                break
            data += chunk
        return (data, st) if len(data) <= cap else None
    except OSError:
        return None
    finally:
        os.close(fd)


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
            got = _read_regular(os.path.join(root, f), 512 * 1024)
            if got is None:
                continue
            data = got[0]
            if used + len(data) > budget_bytes:
                return found
            used += len(data)
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


# ---------------------------------------------------------------- launchers

LAUNCHER_DIRS = (".local/share/applications", ".config/autostart")
LAUNCHER_BUDGET = 3000       # entries examined across both folders
LAUNCHER_DEPTH = 4           # Wine nests its entries in Programs/<game>/
FIXED_BIN_DIRS = ("/usr/bin", "/usr/local/bin", "/usr/share/omarchy/bin")
# Shells run a command line we'd have to guess at, so an entry that starts
# one is never called broken.
SHELLS = {"sh", "bash", "zsh", "dash", "fish"}


def _search_dirs():
    """Where a launcher's program may be: the usual places, your session's
    PATH (what launchers actually run with) and this process's PATH."""
    dirs = list(FIXED_BIN_DIRS) + [os.path.join(HOME, d) for d in (".local/bin", "bin", ".local/share/mise/shims")]
    for line in _capture(["/usr/bin/systemctl", "--user", "show-environment"], timeout=3, cap=256 * 1024).splitlines():
        if line.startswith("PATH="):
            dirs += line[5:].split(":")
    dirs += os.environ.get("PATH", "").split(":")
    return [d for d in dict.fromkeys(dirs) if os.path.isabs(d)]


def _found(program, dirs):
    if "/" in program:
        # A relative path depends on the working directory: can't tell.
        return not os.path.isabs(program) or os.path.exists(program)
    return any(os.access(os.path.join(d, program), os.X_OK) for d in dirs)


def _flatpak_installed(app_id):
    return any(os.path.isdir(os.path.join(d, app_id))
               for d in ("/var/lib/flatpak/app", os.path.join(HOME, ".local", "share", "flatpak", "app")))


def _desktop_keys(data):
    """The [Desktop Entry] group's keys (unlocalised only)."""
    keys, inside = {}, False
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            keys.setdefault(k.strip(), v.strip())
    return keys


def why_broken(keys, dirs):
    """What is missing, in a few words, or None when the entry may work."""
    if keys.get("Hidden", "").lower() == "true" or keys.get("Type", "Application") != "Application":
        return None
    try_exec = keys.get("TryExec")
    if try_exec and not _found(try_exec, dirs):
        return os.path.basename(try_exec) + " is gone"
    try:
        argv = shlex.split(keys.get("Exec", ""))
    except ValueError:
        return None
    if argv and argv[0] == "env":
        argv = argv[1:]
        while argv and "=" in argv[0] and not argv[0].startswith("-"):
            name, value = argv[0].split("=", 1)
            if name == "WINEPREFIX" and os.path.isabs(value) and not os.path.isdir(value):
                return "its Wine folder is gone"
            argv = argv[1:]
        if argv and argv[0].startswith("-"):
            return None
    if not argv or os.path.basename(argv[0]) in SHELLS:
        return None
    if not _found(argv[0], dirs):
        return os.path.basename(argv[0]) + " is gone"
    if os.path.basename(argv[0]) == "flatpak" and "run" in argv:
        rest = [a for a in argv[argv.index("run") + 1:] if not a.startswith("-")]
        if rest and re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", rest[0]) and not _flatpak_installed(rest[0]):
            return "Flatpak app " + rest[0] + " is gone"
    return None


def _valid_launcher_id(item):
    parts = item.split("/")
    prefix = next((d for d in LAUNCHER_DIRS if item.startswith(d + "/")), None)
    return (prefix is not None and item.endswith(".desktop") and len(item) <= 128
            and all(_plain_name(p) for p in parts[len(prefix.split("/")):]))


def broken_launchers():
    """[{id, path, label, bytes}] for your own .desktop entries whose
    program is gone. Symlinks and files you don't own are never listed."""
    dirs, budget, out = _search_dirs(), [LAUNCHER_BUDGET], []
    for rel in LAUNCHER_DIRS:
        stack = [(rel, 0)]
        while stack and budget[0] > 0:
            folder, depth = stack.pop()
            for name in sorted(_names(os.path.join(HOME, folder), 1000)):
                budget[0] -= 1
                item = folder + "/" + name
                path = os.path.join(HOME, item)
                try:
                    st = os.lstat(path)
                except OSError:
                    continue
                if st.st_uid != UID:
                    continue
                if stat.S_ISDIR(st.st_mode) and depth < LAUNCHER_DEPTH:
                    stack.append((item, depth + 1))
                if not stat.S_ISREG(st.st_mode) or not _valid_launcher_id(item):
                    continue
                # The listing above only chose the name; what is read is
                # whatever that name is now, checked again on its descriptor.
                got = _read_regular(path, 64 * 1024, owner=UID)
                if got is None:
                    continue
                data, st = got
                keys = _desktop_keys(data)
                why = why_broken(keys, dirs)
                if why:
                    label = UNSAFE_TEXT.sub("", keys.get("Name", "") or name[:-8])[:80]
                    out.append({"id": item, "path": "~/" + item, "label": label + " — " + why,
                                "bytes": st.st_blocks * 512})
    return out[:60]


def resolve_launcher(item):
    """The path for a broken launcher id, only if it is still broken now."""
    if not _valid_launcher_id(item):
        return None
    return os.path.join(HOME, item) if item in {c["id"] for c in broken_launchers()} else None

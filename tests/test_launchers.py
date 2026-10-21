"""The broken-launcher finder, against a throw-away home: it must call an
entry broken only when its program is clearly gone, and never list
symlinks or entries it can't be sure about.

Run: python3 tests/test_launchers.py
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

home = tempfile.mkdtemp(prefix="keepwell-test-")
atexit.register(shutil.rmtree, home)
os.environ["HOME"] = home
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import keepwell_unclaimed as u  # noqa: E402

GONE = "keepwell-no-such-program"
ENTRIES = {
    # name: (contents, expected to be listed)
    "gone.desktop": (f"Exec={GONE} %U", True),
    "gone-path.desktop": (f"Exec=/opt/{GONE}/run", True),
    "gone-tryexec.desktop": (f"TryExec={GONE}\nExec=sh", True),
    "wine.desktop": (f'Exec=env WINEPREFIX="{home}/.wine-gone" /usr/bin/true "C:\\\\game.exe"', True),
    "fine.desktop": ("Exec=sh -c 'anything'", False),
    "fine-env.desktop": ("Exec=env FOO=1 sh", False),
    "shell.desktop": (f"Exec=bash -c '{GONE}'", False),
    "hidden.desktop": (f"Hidden=true\nExec={GONE}", False),
    "link.desktop": (f"Type=Link\nURL=https://example.org\nExec={GONE}", False),
    "relative.desktop": (f"Exec=./{GONE}", False),
    "other-group.desktop": (f"Exec=sh\n[Desktop Action new]\nExec={GONE}", False),
}

apps = Path(home, ".local/share/applications")
nested = apps / "wine/Programs/Some Game"
nested.mkdir(parents=True)
Path(home, ".config/autostart").mkdir(parents=True)
for name, (body, _) in ENTRIES.items():
    (apps / name).write_text(f"[Desktop Entry]\nName={name}\n{body}\n")
(nested / "Some Game.desktop").write_text(f"[Desktop Entry]\nName=Some Game\nExec={GONE}\n")
(Path(home, ".config/autostart") / "old.desktop").write_text(f"[Desktop Entry]\nExec={GONE}\n")
os.symlink(apps / "gone.desktop", apps / "symlinked.desktop")

found = {i["id"] for i in u.broken_launchers()}
expected = {".local/share/applications/" + n for n, (_, listed) in ENTRIES.items() if listed}
expected |= {".local/share/applications/wine/Programs/Some Game/Some Game.desktop",
             ".config/autostart/old.desktop"}

problems = [f"missed {i}" for i in sorted(expected - found)] + [f"wrongly listed {i}" for i in sorted(found - expected)]
for bad in ("../etc/passwd", ".local/share/applications/../../x.desktop", ".config/other/x.desktop",
            ".local/share/applications/fine.desktop"):
    if u.resolve_launcher(bad) is not None:
        problems.append(f"resolved {bad}")
if u.resolve_launcher(".local/share/applications/gone.desktop") != str(apps / "gone.desktop"):
    problems.append("didn't resolve a broken entry")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"ok: {len(found)} broken launchers found, the others left alone")

"""Developer caches that live outside ~/.cache. A fixed map, so nothing a
file or another program says can name a path. Each is a download cache its
tool fills again the next time a project needs it.

Left out on purpose:
  - Go's module cache (~/go/pkg/mod): Go makes its files read-only, so it
    moves to the Trash but emptying the Trash then fails on it.
    `go clean -modcache` is the way to clear it.
  - pnpm's store: projects hard-link their files from it, so moving it frees
    far less than its size says. `pnpm store prune` is the way to clear it.
"""

import os
import stat

HOME = os.path.expanduser("~")

DEV_CACHES = {
    "npm": ("npm downloads", ".npm/_cacache"),
    "cargo-registry": ("Cargo crate downloads", ".cargo/registry"),
    "cargo-git": ("Cargo git checkouts", ".cargo/git"),
    "maven": ("Maven downloads", ".m2/repository"),
    "gradle": ("Gradle caches", ".gradle/caches"),
    "bun": ("bun downloads", ".bun/install/cache"),
    "nuget": ("NuGet packages", ".nuget/packages"),
}


def resolve(key):
    """The cache's path if it is a folder you own, reached without a symlink
    anywhere below your home; otherwise None."""
    entry = DEV_CACHES.get(key)
    if not entry:
        return None
    path = os.path.join(HOME, entry[1])
    if os.path.realpath(path) != os.path.join(os.path.realpath(HOME), entry[1]):
        return None
    try:
        st = os.lstat(path)
    except OSError:
        return None
    return path if stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() else None

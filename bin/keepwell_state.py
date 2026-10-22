"""Keepwell's own state directory, ~/.local/state/keepwell.

Shared by the helpers in this folder. Every path below the home directory is
opened one component at a time without following symlinks, and each held
directory is checked to be a real directory you own; Keepwell's own
directories are kept at 0700 and its files at 0600. Files are read through
one descriptor, capped, and written through a fresh temporary and a rename.

What lives here:
  pending.json        the terminal Keepwell is waiting on (survives a shell
                      restart, e.g. during `omarchy update`)
  gitleaks.json       the last secrets scan: counts and locations, redacted
  clamav/*.log        ClamAV scan logs, the newest ten kept
  clamav/filelist-*.txt  the files the running scan was told to read
"""

import json
import os
import re
import secrets
import stat

PARTS = (".local", "state", "keepwell")
MAX_BYTES = 256 * 1024
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}(\.json|\.log)")
SUBDIRS = ("clamav",)
UID = os.geteuid()
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _check_dir(fd, own):
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != UID:
        raise PermissionError("untrusted directory")
    if own and st.st_mode & 0o077:
        os.fchmod(fd, 0o700)


def open_dir(sub=None, create=True):
    """A held descriptor for the state directory (or one of its fixed
    subdirectories), or None when it doesn't exist and create is False."""
    if sub is not None and sub not in SUBDIRS:
        raise ValueError("unknown subdirectory")
    parts = PARTS + ((sub,) if sub else ())
    fd = os.open(os.path.expanduser("~"), DIR_FLAGS)
    try:
        _check_dir(fd, False)
        for depth, name in enumerate(parts):
            own = depth >= 2          # keepwell/ and below are ours
            try:
                nfd = os.open(name, DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    os.close(fd)
                    return None
                os.mkdir(name, 0o700, dir_fd=fd)
                nfd = os.open(name, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nfd
            _check_dir(fd, own)
        if create:
            _tidy(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _tidy(dirfd):
    """Anything in our directory that isn't a regular file we own, or one of
    our subdirectories, is removed; our files are kept at 0600."""
    for entry in os.listdir(dirfd)[:500]:
        try:
            st = os.stat(entry, dir_fd=dirfd, follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISDIR(st.st_mode) and entry in SUBDIRS:
            continue
        if stat.S_ISREG(st.st_mode) and st.st_uid == UID:
            if st.st_mode & 0o077:
                fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
                try:
                    os.fchmod(fd, 0o600)
                finally:
                    os.close(fd)
            continue
        if not stat.S_ISDIR(st.st_mode):
            try:
                os.unlink(entry, dir_fd=dirfd)
            except OSError:
                pass


def read(name, sub=None, cap=MAX_BYTES):
    """Bytes of a state file, or None if it isn't there or isn't trustworthy."""
    if not NAME.fullmatch(name):
        raise ValueError("bad name")
    dirfd = open_dir(sub, create=False)
    if dirfd is None:
        return None
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        except OSError:
            return None
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != UID or st.st_nlink != 1:
                return None
            if st.st_size > cap:
                os.lseek(fd, st.st_size - cap, os.SEEK_SET)   # logs: the tail is what matters
            os.set_blocking(fd, True)
            data = bytearray()
            while len(data) < cap:
                chunk = os.read(fd, min(65536, cap - len(data)))
                if not chunk:
                    break
                data += chunk
            return bytes(data)
        finally:
            os.close(fd)
    finally:
        os.close(dirfd)


def write(name, data, sub=None):
    if not NAME.fullmatch(name) or len(data) > MAX_BYTES:
        raise ValueError("bad name or too large")
    dirfd = open_dir(sub)
    tmp = ".%s.%s.tmp" % (name, secrets.token_hex(8))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)
        os.fsync(dirfd)
    except BaseException:
        try:
            os.unlink(tmp, dir_fd=dirfd)
        except OSError:
            pass
        raise
    finally:
        os.close(dirfd)


def remove(name, sub=None):
    if not NAME.fullmatch(name):
        raise ValueError("bad name")
    dirfd = open_dir(sub, create=False)
    if dirfd is None:
        return
    try:
        os.unlink(name, dir_fd=dirfd)
    except FileNotFoundError:
        pass
    finally:
        os.close(dirfd)


def read_json(name, cap=MAX_BYTES):
    raw = read(name, cap=cap)
    if raw is None:
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def new_log(kind, keep=10):
    """Create an empty, private log file for a scan and return its path.
    The file is made here (exclusive, 0600) so the scanner appends to a file
    Keepwell just created. Older logs beyond `keep` are removed."""
    if kind not in ("home", "downloads"):
        raise ValueError("bad kind")
    dirfd = open_dir("clamav")
    try:
        logs = sorted(n for n in os.listdir(dirfd) if re.fullmatch(r"\d{10}-(home|downloads)\.log", n))
        for old in logs[:max(0, len(logs) - keep + 1)]:
            try:
                os.unlink(old, dir_fd=dirfd)
            except OSError:
                pass
        import time
        name = "%010d-%s.log" % (int(time.time()), kind)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
        os.close(fd)
        return os.path.join(os.path.expanduser("~"), *PARTS, "clamav", name)
    finally:
        os.close(dirfd)


def new_filelist(kind):
    """Create an empty, private file for the list of files a scan will read,
    replacing the previous one, and return its path."""
    if kind not in ("home", "downloads"):
        raise ValueError("bad kind")
    dirfd = open_dir("clamav")
    name = "filelist-%s.txt" % kind
    try:
        try:
            os.unlink(name, dir_fd=dirfd)
        except FileNotFoundError:
            pass
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dirfd)
        os.close(fd)
        return os.path.join(os.path.expanduser("~"), *PARTS, "clamav", name)
    finally:
        os.close(dirfd)


def latest_log():
    """(name, bytes of its last 64 KiB) of the newest scan log, or None."""
    dirfd = open_dir("clamav", create=False)
    if dirfd is None:
        return None
    try:
        logs = sorted(n for n in os.listdir(dirfd)[:200] if re.fullmatch(r"\d{10}-(home|downloads)\.log", n))
    finally:
        os.close(dirfd)
    if not logs:
        return None
    return logs[-1], read(logs[-1], sub="clamav", cap=64 * 1024)


# ---------------------------------------------------------------- user config
# The background-check timer's unit files live where systemd looks for them,
# ~/.config/systemd/user. Same care as above, except that these folders are
# yours rather than Keepwell's, so their permissions are left alone.

UNIT_PARTS = (".config", "systemd", "user")
UNIT_NAME = re.compile(r"keepwell-[a-z]{1,20}\.(service|timer)")
UNIT_MARK = b"# Written by the Keepwell plugin"


def _unit_dir(create):
    fd = os.open(os.path.expanduser("~"), DIR_FLAGS)
    try:
        for name in UNIT_PARTS:
            try:
                nfd = os.open(name, DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    os.close(fd)
                    return None
                os.mkdir(name, 0o755, dir_fd=fd)
                nfd = os.open(name, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nfd
            _check_dir(fd, False)
        return fd
    except BaseException:
        os.close(fd)
        raise


def write_unit(name, data):
    """Write one of Keepwell's unit files. Refuses to replace a file of that
    name that Keepwell didn't write."""
    if not UNIT_NAME.fullmatch(name) or not data.startswith(UNIT_MARK):
        raise ValueError("bad unit")
    dirfd = _unit_dir(True)
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
            try:
                if not os.read(fd, len(UNIT_MARK)).startswith(UNIT_MARK):
                    raise PermissionError("%s exists and isn't Keepwell's" % name)
            finally:
                os.close(fd)
        except FileNotFoundError:
            pass
        tmp = ".%s.%s.tmp" % (name, secrets.token_hex(8))
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644, dir_fd=dirfd)
        try:
            os.fchmod(fd, 0o644)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.rename(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)
        except BaseException:
            os.unlink(tmp, dir_fd=dirfd)
            raise
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def unit_free(name):
    """True when Keepwell may write this unit: absent, or written by Keepwell."""
    if not UNIT_NAME.fullmatch(name):
        return False
    dirfd = _unit_dir(False)
    if dirfd is None:
        return True
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        try:
            return os.read(fd, len(UNIT_MARK)).startswith(UNIT_MARK)
        finally:
            os.close(fd)
    finally:
        os.close(dirfd)


def remove_unit(name):
    """Remove one of Keepwell's unit files, only if Keepwell wrote it."""
    if not UNIT_NAME.fullmatch(name):
        raise ValueError("bad unit")
    dirfd = _unit_dir(False)
    if dirfd is None:
        return
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        except FileNotFoundError:
            return
        try:
            ours = os.read(fd, len(UNIT_MARK)).startswith(UNIT_MARK)
        finally:
            os.close(fd)
        if ours:
            os.unlink(name, dir_fd=dirfd)
    finally:
        os.close(dirfd)

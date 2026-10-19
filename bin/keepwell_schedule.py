"""Keepwell's optional deep-scan schedule, shared by keepwell-check (status)
and keepwell-run (setting up and running).

The quick checks need no schedule: Keepwell runs them by itself, hourly and
when you open it. The deep scans are the long ones you opt in to: a virus
scan of Downloads or your home folder, the secrets scan and the dependency
scan (osv-scanner uses the network); minutes to hours.

A run that would start more than LATE seconds after its time — because the
computer was off, suspended or hibernating — doesn't run late. It's missed:
Keepwell says so (the shield, a notification, a strip in the window) and you
choose when to run it. A run never changes anything.

Settings live in schedules.json, what happened in runs.json.
"""

import json
import os
import re
import time

import keepwell_state

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
KINDS = ("deep",)
DEEP_PARTS = ("scan-downloads", "scan-home", "leaks", "osv")
LATE = 600
DEFAULTS = {"deep": {"days": ["sat"], "time": "13:00"}}
TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def units(kind):
    return "keepwell-%s.timer" % kind, "keepwell-%s.service" % kind


def calendar(conf):
    return "%s *-*-* %s:00" % (",".join(d.capitalize() for d in conf["days"]), conf["time"])


def settings():
    """Both schedules' settings, valid or replaced by defaults."""
    try:
        doc = keepwell_state.read_json("schedules.json") or {}
    except (OSError, ValueError):
        doc = {}
    out = {}
    for kind in KINDS:
        d = doc.get(kind) if isinstance(doc.get(kind), dict) else {}
        days = [x for x in DAYS if x in (d.get("days") or [])]
        conf = {"days": days or list(DEFAULTS[kind]["days"]),
                "time": d["time"] if TIME.fullmatch(str(d.get("time"))) else DEFAULTS[kind]["time"],
                "since": d["since"] if isinstance(d.get("since"), int) else 0}
        conf["parts"] = [x for x in DEEP_PARTS if x in (d.get("parts") or [])] or ["scan-downloads"]
        conf["battery"] = d.get("battery") is not False   # True: skip the scans on battery
        out[kind] = conf
    return out


def save_settings(all_settings):
    keepwell_state.write("schedules.json", json.dumps(all_settings, separators=(",", ":")).encode())


def runs():
    try:
        doc = keepwell_state.read_json("runs.json") or {}
    except (OSError, ValueError):
        doc = {}
    return {k: (doc.get(k) if isinstance(doc.get(k), dict) else {}) for k in KINDS}


def save_run(kind, **fields):
    doc = runs()
    doc[kind].update(fields)
    keepwell_state.write("runs.json", json.dumps(doc, separators=(",", ":")).encode())


def last_slot(conf, now):
    """The most recent scheduled time at or before `now` (epoch), or None."""
    hh, mm = (int(x) for x in conf["time"].split(":"))
    lt = time.localtime(now)
    for back in range(0, 8):
        slot = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - back, hh, mm, 0, 0, 0, -1))
        if slot <= now and DAYS[time.localtime(slot).tm_wday] in conf["days"]:
            return int(slot)
    return None


def missed_slot(conf, run, now, enabled, running):
    """The scheduled time that was missed, or None: one whose grace has run
    out with no run since, set up before it, and not dismissed."""
    if not enabled or running:
        return None
    slot = last_slot(conf, now - LATE)
    if slot is None or slot < conf.get("since", 0):
        return None
    if run.get("at", 0) >= slot or run.get("dismissed", 0) >= slot:
        return None
    return slot


def status(capture):
    """Everything the window shows about both schedules. `capture(argv)`
    returns a command's output as text."""
    conf, done, now = settings(), runs(), time.time()
    out = {}
    for kind in KINDS:
        timer, service = units(kind)
        enabled = capture(["/usr/bin/systemctl", "--user", "is-enabled", timer]).strip() == "enabled"
        running = capture(["/usr/bin/systemctl", "--user", "is-active", service]).strip() in ("active", "activating") \
            or capture(["/usr/bin/systemctl", "--user", "is-active", "keepwell-%s-now.service" % kind]).strip() in ("active", "activating")
        c = conf[kind]
        item = dict(c, enabled=enabled, running=running)
        if enabled:
            m = re.search(r"(?m)^\s*Next elapse: (.+)$", capture(["/usr/bin/systemd-analyze", "calendar", "--", calendar(c)]))
            item["next"] = m.group(1).strip()[:64] if m else None
        run = done[kind]
        if isinstance(run.get("at"), int):
            item["last"] = {"at": run["at"], "summary": str(run.get("summary", ""))[:300]}
        slot = missed_slot(c, run, now, enabled, running)
        if slot:
            item["missed"] = slot
        out[kind] = item
    return out

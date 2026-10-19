.pragma library

// Preview data for the skeleton build. Every value here is invented and
// mirrors the design renders; the real checks replace this file's role one
// section at a time, each from a bounded helper in bin/.
//
// Shape of a check:
//   id, kind (crit | attn | good | info | off), title, tool, status, meta,
//   what (plain-language explanation), facts [{ k, v, owner }], note,
//   actions [{ label, primary, elevated, trash, disabled }]

var sections = [
  {
    id: "security",
    name: "Security",
    hero: {
      crit: ["Action needed", "A package with a known high-risk issue is installed. Updating fixes it."],
      attn: ["Some things to review", "Nothing urgent, but a few checks want a look."],
      good: ["Security looks good", "Nothing needs your attention."]
    },
    checks: [
      { id: "audit", kind: "crit", title: "Known vulnerabilities", tool: "arch-audit",
        status: "1 high-risk issue in installed packages", meta: "3 packages · checked 2 h ago",
        what: "arch-audit compares your installed packages with the Arch security tracker. Almost every fix arrives with your next system update.",
        facts: [
          { k: "High", v: "libxml2 — fixed in update", owner: "" },
          { k: "Medium", v: "curl, python-jinja", owner: "" },
          { k: "Last checked", v: "Today 12:41", owner: "" },
          { k: "Auto-refresh", v: "Off", owner: "Keepwell timer" }
        ],
        note: "",
        actions: [{ label: "Update system", primary: true, elevated: true }, { label: "Check again" }] },
      { id: "av", kind: "attn", title: "Antivirus", tool: "ClamAV · ClamTK",
        status: "Virus definitions are 9 days old", meta: "Scan Sundays 10:00 · managed by ClamTK",
        what: "ClamAV checks files against a list of known malware. On Linux it mostly catches Windows malware in downloads and in files you pass on to others.",
        facts: [
          { k: "Definitions", v: "9 days old", owner: "" },
          { k: "Auto-update", v: "Off", owner: "clamav-freshclam" },
          { k: "Scheduled scan", v: "Sundays at 10:00", owner: "managed by ClamTK" },
          { k: "Scan folder", v: "~/Downloads", owner: "managed by ClamTK" },
          { k: "Last scan", v: "6 days ago · nothing found", owner: "" }
        ],
        note: "Antivirus is one layer, not a force field. Updates and the firewall do more of the work.",
        actions: [{ label: "Turn on auto-update", primary: true, elevated: true }, { label: "Edit schedule…" }, { label: "Open ClamTK" }] },
      { id: "upd", kind: "attn", title: "System updates", tool: "omarchy update",
        status: "Last updated 12 days ago", meta: "Never scheduled — you choose when",
        what: "Updates bring security fixes for everything installed. Keepwell only reminds you; it never updates on its own.",
        facts: [
          { k: "Last update", v: "12 days ago", owner: "" },
          { k: "Schedule", v: "None, by design", owner: "" }
        ],
        note: "",
        actions: [{ label: "Update now", primary: true, elevated: true }] },
      { id: "fw", kind: "good", title: "Firewall", tool: "UFW · GufW",
        status: "On — blocks incoming, allows outgoing", meta: "4 rules · edit in GufW",
        what: "The firewall decides which network connections may reach this computer. Blocking incoming and allowing outgoing is the right default for a desktop or laptop.",
        facts: [
          { k: "Status", v: "Active", owner: "" },
          { k: "Incoming", v: "Deny", owner: "" },
          { k: "Outgoing", v: "Allow", owner: "" },
          { k: "Rules", v: "4", owner: "managed by GufW" }
        ],
        note: "",
        actions: [{ label: "Edit rules in GufW", primary: true }, { label: "Turn off…", elevated: true }] },
      { id: "leaks", kind: "off", title: "Secrets in your code", tool: "gitleaks",
        status: "Not set up — optional", meta: "Finds keys and passwords committed to git",
        what: "If you write code, gitleaks scans a folder of git repositories for passwords and API keys that were committed by accident. Read-only: it reports, it never changes a repo.",
        facts: [
          { k: "Installed", v: "No", owner: "" },
          { k: "Folder", v: "Not chosen", owner: "" }
        ],
        note: "",
        actions: [{ label: "Install gitleaks", primary: true, elevated: true }] }
    ]
  },
  {
    id: "privacy",
    name: "Privacy",
    hero: {
      crit: ["Action needed", "Something here needs your attention."],
      attn: ["Two things to review", "Chromium and VS Code send usage data. You decide what stays on."],
      good: ["Privacy looks good", "Nothing needs your attention."]
    },
    checks: [
      { id: "browser", kind: "attn", title: "Browser telemetry", tool: "Chromium",
        status: "Usage statistics and crash reports are on", meta: "Close Chromium to make changes",
        what: "Chromium can send usage statistics and crash reports to Google. Keepwell shows each setting and changes only the ones you tick — never anything else in your profile.",
        facts: [
          { k: "Usage statistics", v: "On", owner: "Local State" },
          { k: "Crash reports", v: "On", owner: "Local State" },
          { k: "Search suggestions", v: "On", owner: "Preferences" }
        ],
        note: "Chromium is running. It rewrites its settings on exit, so changes wait until it is closed. A backup is taken first.",
        actions: [{ label: "Review changes…", primary: true, disabled: true }, { label: "Firefox: not installed", disabled: true }] },
      { id: "apps", kind: "attn", title: "Data from your apps", tool: "Reporter",
        status: "2 installed apps send usage data", meta: "Arch itself sends nothing",
        what: "Arch Linux sends no telemetry. Some apps you install do. This lists the ones Keepwell knows, and their opt-out state where it can be read.",
        facts: [
          { k: "VS Code", v: "Telemetry on", owner: "open its settings" },
          { k: "Spotify", v: "Can't be read", owner: "guide" }
        ],
        note: "",
        actions: [{ label: "Open VS Code settings", primary: true }, { label: "How to opt out of Spotify" }] },
      { id: "cam", kind: "good", title: "Camera & microphone", tool: "PipeWire",
        status: "Not in use right now", meta: "Live — updates as apps start and stop",
        what: "Shows which apps are using your camera or microphone. Keepwell only watches; it never blocks a device.",
        facts: [
          { k: "Camera", v: "Idle", owner: "" },
          { k: "Microphone", v: "Idle", owner: "" },
          { k: "Last used", v: "Firefox · today 14:02", owner: "" }
        ],
        note: "A sliding camera cover or hardware mute switch is the only guarantee. Software can only report.",
        actions: [] },
      { id: "traces", kind: "info", title: "Activity traces", tool: "GTK · shell",
        status: "Recent files, history and thumbnails", meta: "312 recent files · 84 MB thumbnails",
        what: "Your desktop remembers recent files, commands and image previews. Clearing them moves them to Trash, so you can still change your mind.",
        facts: [
          { k: "Recent files", v: "312 entries", owner: "" },
          { k: "Shell history", v: "4,180 lines", owner: "" },
          { k: "Thumbnails", v: "84 MB", owner: "" }
        ],
        note: "",
        actions: [{ label: "Choose what to clear…", primary: true, trash: true }] },
      { id: "perms", kind: "off", title: "App permissions", tool: "Flatseal",
        status: "Flatseal isn't installed", meta: "4 Flatpak apps could be reviewed",
        what: "Flatpak apps ask for access to files, devices and the network. Flatseal shows and changes those permissions, one app at a time.",
        facts: [
          { k: "Flatpak apps", v: "4", owner: "" },
          { k: "Flatseal", v: "Not installed", owner: "" }
        ],
        note: "",
        actions: [{ label: "Install Flatseal", primary: true, elevated: true }, { label: "What permissions mean" }] }
    ]
  },
  {
    id: "care",
    name: "System Care",
    hero: {
      crit: ["Action needed", "Something here needs your attention."],
      attn: ["Some things to review", "Nothing urgent, but a few checks want a look."],
      good: ["Your system is in good shape", "6.2 GB can be freed whenever you like."],
      goodCta: "Review cleanup"
    },
    checks: [
      { id: "clean", kind: "info", title: "Cleanup", tool: "paccache · pacman · journal",
        status: "6.2 GB can be freed safely", meta: "Package cache 4.1 GB · logs 1.3 GB · app cache 0.8 GB",
        what: "Old package downloads, unused packages, logs and app caches build up over time. You see every item and its size before anything is removed.",
        facts: [
          { k: "Package cache", v: "4.1 GB", owner: "Safe" },
          { k: "Old logs", v: "1.3 GB", owner: "Safe" },
          { k: "App cache", v: "0.8 GB", owner: "Safe" },
          { k: "Unused packages", v: "3 · 212 MB", owner: "Advanced" }
        ],
        note: "",
        actions: [{ label: "Review cleanup…", primary: true }, { label: "Take a snapshot first", elevated: true }] },
      { id: "unclaimed", kind: "info", title: "Unclaimed files", tool: "Keepwell",
        status: "14 items nothing has claimed in 180+ days", meta: "1.1 GB · verify before removing",
        what: "Folders in your home that no installed package owns and that haven't changed in a long time — often leftovers from apps you removed. Suggestions only.",
        facts: [
          { k: "Candidates", v: "14 · 1.1 GB", owner: "" },
          { k: "Older than", v: "180 days", owner: "adjustable" },
          { k: "Last scan", v: "Today 12:43", owner: "" }
        ],
        note: "",
        actions: [{ label: "Review…", primary: true }] },
      { id: "snap", kind: "good", title: "Snapshots", tool: "Snapper · Limine",
        status: "Last snapshot 2 days ago", meta: "Boot menu in sync · 8 snapshots",
        what: "A snapshot is a restore point for the system (not your home folder). To roll back, pick it from the boot menu.",
        facts: [
          { k: "Snapper", v: "Running", owner: "" },
          { k: "Boot menu", v: "In sync", owner: "Limine" },
          { k: "Snapshots", v: "8", owner: "" }
        ],
        note: "",
        actions: [{ label: "Take snapshot now", primary: true, elevated: true }, { label: "Manage in Snapshots plugin ↗" }] },
      { id: "disk", kind: "good", title: "Disk usage", tool: "Disk Usage Analyzer",
        status: "61% used — 186 GB free", meta: "/ · 476 GB",
        what: "See which folders take the most space. Large caches and package downloads are normal; Cleanup handles those.",
        facts: [
          { k: "Used", v: "290 GB of 476 GB", owner: "" },
          { k: "Largest folder", v: "~/Videos · 92 GB", owner: "" }
        ],
        note: "",
        actions: [{ label: "Open Disk Usage Analyzer", primary: true }] },
      { id: "timers", kind: "off", title: "Background checks", tool: "Keepwell timer",
        status: "Nothing runs in the background", meta: "Optional weekly reports — notify, never act",
        what: "Keepwell can check for vulnerabilities and reclaimable space on a schedule and send a notification. It never removes or changes anything on its own.",
        facts: [
          { k: "Vulnerability check", v: "Off", owner: "" },
          { k: "Cleanup report", v: "Off", owner: "" }
        ],
        note: "",
        actions: [{ label: "Set up…", primary: true }] }
    ]
  }
]

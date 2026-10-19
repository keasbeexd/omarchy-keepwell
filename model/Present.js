.pragma library
.import "Status.js" as Status

// Turns the helper's facts (bin/keepwell-check) into what the window shows:
// a state, a sentence, the facts and the actions for each check. All of the
// plugin's wording lives here; the helper only measures.
//
// build(doc, now) -> [section, ...] in the shape model/SampleData.js uses.
// doc may be null (no result yet): every check then reads "Checking…".

// ---------------------------------------------------------------- formatting

function bytes(n) {
  if (typeof n !== "number" || !isFinite(n) || n < 0) return "—"
  var units = ["B", "KB", "MB", "GB", "TB"]
  var i = 0
  while (n >= 1000 && i < units.length - 1) { n /= 1000; i++ }
  return (i === 0 || n >= 100 ? Math.round(n) : n.toFixed(1)) + " " + units[i]
}

function ago(at, now) {
  if (typeof at !== "number" || !isFinite(at)) return "unknown"
  var s = Math.max(0, now - at)
  if (s < 90) return "just now"
  if (s < 3600) return Math.round(s / 60) + " min ago"
  if (s < 86400) return Math.round(s / 3600) + " h ago"
  var d = Math.floor(s / 86400)
  return d === 1 ? "yesterday" : d + " days ago"
}

function days(at, now) {
  return typeof at === "number" && isFinite(at) ? Math.floor(Math.max(0, now - at) / 86400) : null
}

function plural(n, one, many) { return n + " " + (n === 1 ? one : many) }

var WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six"]
function word(n) { return n < WORDS.length ? WORDS[n] : String(n) }

function onOff(v) { return v === true ? "On" : v === false ? "Off" : "Browser default" }

function fact(k, v, owner) { return { k: k, v: v, owner: owner || "" } }

function check(base, fields) {
  var c = { facts: [], actions: [], note: "", meta: "" }
  for (var k in base) c[k] = base[k]
  for (var f in fields) c[f] = fields[f]
  return c
}

// act: an action id in bin/keepwell-run (opens the confirm sheet, then a
// terminal). launch: a desktop entry to open. run: "network" re-runs checks
// with arch-audit. None of these: arrives in a later build.
function install(label, act) { return { label: label, primary: true, elevated: true, act: act } }

// ---------------------------------------------------------------- catalog

var CATALOG = {
  audit: { id: "audit", title: "Known vulnerabilities", tool: "arch-audit",
    what: "arch-audit compares your installed packages with the Arch security tracker. Almost every fix arrives with your next system update." },
  av: { id: "av", title: "Antivirus", tool: "ClamAV",
    what: "ClamAV checks files against a list of known malware. On Linux it mostly catches Windows malware in downloads and in files you pass on to others." },
  upd: { id: "upd", title: "System updates", tool: "omarchy update",
    what: "Updates bring security fixes for everything installed. Keepwell only reminds you; it never updates on its own." },
  fw: { id: "fw", title: "Firewall", tool: "UFW",
    what: "The firewall decides which network connections may reach this computer. Blocking incoming and allowing outgoing is the right default for a desktop or laptop." },
  leaks: { id: "leaks", title: "Secrets in your code", tool: "gitleaks",
    what: "If you write code, gitleaks scans a folder of git repositories for passwords and API keys that were committed by accident. Read-only: it reports, it never changes a repo." },

  browser: { id: "browser", title: "Browser telemetry", tool: "Chromium",
    what: "Chromium can send usage statistics and crash reports. Keepwell shows each setting; changing them comes in a later build, and will only ever touch the settings you tick." },
  netpriv: { id: "netpriv", title: "Network privacy", tool: "hosts · resolved · NetworkManager",
    what: "Small, optional settings that cut what this computer tells the network: telemetry hosts, backup DNS servers, Arch's connection check, your hardware address, local announcements and debug lookups. Each has a small cost, shown before anything changes." },
  apps: { id: "apps", title: "Data from your apps", tool: "Reporter",
    what: "Arch Linux sends no telemetry. Some apps you install do. This lists the ones Keepwell knows, and their opt-out state where it can be read." },
  cam: { id: "cam", title: "Camera & microphone", tool: "PipeWire",
    what: "Shows which apps are using your camera or microphone. Keepwell only watches; it never blocks a device." },
  traces: { id: "traces", title: "Activity traces", tool: "GTK · shell",
    what: "Your desktop remembers recent files, commands and image previews. Clearing them moves them to Trash, so you can still change your mind." },
  perms: { id: "perms", title: "App permissions", tool: "Flatseal",
    what: "Flatpak apps ask for access to files, devices and the network. Flatseal shows and changes those permissions, one app at a time." },

  clean: { id: "clean", title: "Cleanup", tool: "paccache · pacman",
    what: "Old package downloads, unused packages, logs and app caches build up over time. You see every item and its size before anything is removed." },
  unclaimed: { id: "unclaimed", title: "Unclaimed files", tool: "Keepwell",
    what: "Folders in your home that no installed package owns and that haven't changed in a long time — often leftovers from apps you removed. Suggestions only." },
  snap: { id: "snap", title: "Snapshots", tool: "Snapper · Limine",
    what: "A snapshot is a restore point for the system (not your home folder). To roll back, pick it from the boot menu." },
  disk: { id: "disk", title: "Disk usage", tool: "Disk usage",
    what: "See which folders take the most space. Large caches and package downloads are normal; Cleanup handles those." },
  timers: { id: "timers", title: "Background checks", tool: "Keepwell timer",
    what: "Keepwell can check for vulnerabilities and reclaimable space on a schedule and send a notification. It never removes or changes anything on its own." }
}

var LAYOUT = [
  { id: "security", name: "Security", checks: ["audit", "av", "upd", "fw", "leaks"] },
  { id: "privacy", name: "Privacy", checks: ["browser", "netpriv", "apps", "cam", "traces", "perms"] },
  { id: "care", name: "System Care", checks: ["clean", "unclaimed", "snap", "disk", "timers"] }
]

// ---------------------------------------------------------------- security

function audit(p, net, now) {
  var b = CATALOG.audit
  var note = "Checking downloads Arch's public security list from security.archlinux.org."
  if (!p.installed) return check(b, { kind: "off", status: "arch-audit isn't installed",
    meta: "Small, official tool from the Arch repos", note: note,
    facts: [fact("Installed", "No")], actions: [install("Install arch-audit", "install-arch-audit")] })
  if (p.error) return check(b, { kind: "attn", status: "Couldn't reach the security tracker",
    meta: "Check your connection, then check again", note: note,
    actions: [{ label: "Check again", primary: true, run: "network" }] })
  if (!p.ran) return check(b, { kind: "info", status: "Not checked yet",
    meta: "Runs when you ask — it uses the network", note: note,
    actions: [{ label: "Check now", primary: true, run: "network" }] })

  var c = p.counts || {}
  var serious = (c.Critical || 0) + (c.High || 0)
  var total = serious + (c.Medium || 0) + (c.Low || 0) + (c.Unknown || 0)
  var facts = []
  var bySev = {}
  var pkgs = p.packages || []
  for (var i = 0; i < pkgs.length; i++) {
    var s = pkgs[i].severity
    ;(bySev[s] = bySev[s] || []).push(pkgs[i].name + (pkgs[i].fixed ? "" : " (no fix yet)"))
  }
  var sevs = ["Critical", "High", "Medium", "Low", "Unknown"]
  for (var j = 0; j < sevs.length; j++) {
    if (!c[sevs[j]]) continue
    var names = bySev[sevs[j]] || []
    facts.push(fact(sevs[j], names.slice(0, 3).join(", ") + (names.length > 3 ? " +" + (names.length - 3) : "")))
  }
  if (total === 0) facts.push(fact("Packages", "No known issues"))
  facts.push(fact("Auto-refresh", "Off", "Keepwell timer"))

  var kind = serious > 0 ? "crit" : (c.Medium || 0) > 0 ? "attn" : "good"
  var status = serious > 0 ? plural(serious, "high-risk issue", "high-risk issues") + " in installed packages"
    : total > 0 ? plural(total, "lower-risk issue", "lower-risk issues") + " in installed packages"
    : "No known issues in installed packages"
  return check(b, { kind: kind, status: status, note: note,
    meta: plural(total, "package", "packages") + " flagged · checked just now", facts: facts,
    actions: total > 0 ? [{ label: "Update system", primary: true, elevated: true, act: "update" }, { label: "Check again", run: "network" }]
      : [{ label: "Check again", run: "network" }] })
}

function antivirus(p, now) {
  var b = CATALOG.av
  var honest = "Antivirus is one layer, not a force field. Updates and the firewall do more of the work."
  if (!p.clamav) return check(b, { kind: "off", status: "Not installed — optional",
    meta: "Useful if you share files with Windows users", note: honest,
    facts: [fact("ClamAV", "Not installed")], actions: [install("Install ClamAV", "install-clamav")] })
  var age = days(p.definitionsAt, now)
  var auto = p.freshclamEnabled === "enabled"
  var facts = [
    fact("Definitions", age === null ? "None downloaded yet" : age === 0 ? "Updated today" : plural(age, "day", "days") + " old"),
    fact("Auto-update", auto ? "On" : "Off", "clamav-freshclam"),
    fact("Scheduled scan", p.scanAt ? "Daily at " + p.scanAt : "None", p.clamtk ? "managed by ClamTK" : ""),
    fact("Last scan", p.lastScanAt ? ago(p.lastScanAt, now) : "No scans recorded", p.clamtk ? "ClamTK history" : "")
  ]
  var stale = age === null || age > 7
  var actions = []
  if (!auto) actions.push({ label: "Turn on auto-update", primary: true, elevated: true, act: "freshclam-on" })
  if (age !== null) actions.push({ label: "Scan Downloads", primary: auto, elevated: true, act: "scan-downloads" })
  return check(b, { tool: p.clamtk ? "ClamAV · ClamTK" : "ClamAV",
    kind: stale ? "attn" : "good",
    status: age === null ? "No virus definitions yet" : stale ? "Virus definitions are " + age + " days old" : "Definitions are up to date",
    meta: p.scanAt ? "Scan daily " + p.scanAt + " · managed by ClamTK" : "No scheduled scan",
    facts: facts, note: honest, actions: actions })
}

function updates(p, now) {
  var b = CATALOG.upd
  var d = days(p.lastUpgradeAt, now)
  if (d === null) return check(b, { kind: "attn", status: "No recent full update found",
    meta: "Never scheduled — you choose when", facts: [fact("Last update", "Not in the recent log")],
    actions: [{ label: "Update now", primary: true, elevated: true, act: "update" }] })
  return check(b, { kind: d > 14 ? "attn" : "good",
    status: d === 0 ? "Updated today" : "Last updated " + ago(p.lastUpgradeAt, now),
    meta: "Never scheduled — you choose when",
    facts: [fact("Last update", ago(p.lastUpgradeAt, now)), fact("Schedule", "None, by design")],
    actions: [{ label: "Update now", primary: d > 14, elevated: true, act: "update" }] })
}

function firewall(p) {
  var b = CATALOG.fw
  if (!p.installed) return check(b, { kind: "crit", status: "No firewall installed",
    meta: "UFW is the standard choice", facts: [fact("UFW", "Not installed")],
    actions: [install("Install UFW", "install-ufw")] })
  var on = p.enabled === true && p.unitActive === "active"
  var blocks = p.incoming === "drop" || p.incoming === "reject"
  var gui = p.gufw ? { label: "Edit rules in GufW", primary: on && blocks, launch: "gufw.desktop" }
    : { label: "Install GufW to edit rules", elevated: true, act: "install-gufw" }
  var facts = [
    fact("Status", on ? "Active" : p.enabled === true ? "Enabled, not running" : "Off"),
    fact("Incoming", p.incoming === "accept" ? "Allow" : p.incoming ? "Deny" : "Unknown"),
    fact("Outgoing", p.outgoing === "accept" ? "Allow" : p.outgoing ? "Deny" : "Unknown"),
    fact("Rules", String(p.rules), p.gufw ? "managed by GufW" : "")
  ]
  if (!on) return check(b, { tool: p.gufw ? "UFW · GufW" : "UFW", kind: "crit", status: "The firewall is off",
    meta: "Nothing is filtering incoming connections", facts: facts,
    actions: [{ label: "Turn on", primary: true, elevated: true, act: "ufw-on" }, gui] })
  if (!blocks) return check(b, { tool: p.gufw ? "UFW · GufW" : "UFW", kind: "attn", status: "On, but incoming connections are allowed",
    meta: "The usual default is to deny incoming", facts: facts,
    actions: [{ label: "Deny incoming…", primary: true, elevated: true, act: "ufw-deny-incoming" }, gui] })
  return check(b, { tool: p.gufw ? "UFW · GufW" : "UFW", kind: "good", status: "On — blocks incoming, allows outgoing",
    meta: plural(p.rules, "rule", "rules") + (p.gufw ? " · edit in GufW" : ""), facts: facts,
    actions: [gui, { label: "Turn off…", elevated: true, act: "ufw-off" }] })
}

function leaks(tools) {
  var b = CATALOG.leaks
  if (!tools.gitleaks) return check(b, { kind: "off", status: "Not set up — optional",
    meta: "Finds keys and passwords committed to git", facts: [fact("Installed", "No")],
    actions: [install("Install gitleaks", "install-gitleaks")] })
  return check(b, { kind: "off", status: "Ready — choose a folder to scan",
    meta: "Read-only report", facts: [fact("Installed", "Yes"), fact("Folder", "Not chosen")],
    actions: [{ label: "Choose a folder…", primary: true }] })
}

// ---------------------------------------------------------------- privacy

var BLACK_OPS = "managed by Black Ops"

function browser(p, policy) {
  var b = CATALOG.browser
  if (!p.chromium) return check(b, { kind: "off", status: "Chromium isn't installed",
    meta: p.firefox ? "Firefox support comes later" : "No supported browser found" })
  policy = policy || {}
  var locked = policy.total > 0 && policy.set === policy.total
  var policyFact = fact("Privacy policy",
    !policy.set ? "Not installed" : locked ? "All " + policy.total + " in force" : policy.set + " of " + policy.total + " in force",
    policy.blackOps ? BLACK_OPS : "system-wide policy")
  var actions = policy.blackOps || locked ? [] : [{ label: "Apply privacy policy…", primary: true, elevated: true }]
  if (!p.profile) return check(b, { kind: locked ? "good" : "off", status: "No Chromium profile yet",
    meta: "Open Chromium once, then check again", facts: [policyFact], actions: actions })
  var explicitOn = p.metrics === true || p.safeBrowsingReports === true
  var allDefault = p.metrics === null && p.searchSuggest === null && p.safeBrowsingReports === null
  return check(b, {
    kind: locked ? "good" : explicitOn ? "attn" : allDefault ? "info" : "good",
    status: locked ? "Privacy policy is in force"
      : explicitOn ? "Usage reporting is switched on"
      : allDefault ? "Using Chromium's built-in defaults" : "Usage reporting is off",
    meta: p.running ? "Chromium is running" : "Chromium is closed",
    facts: [
      fact("Usage statistics", onOff(p.metrics), "Local State"),
      fact("Search suggestions", onOff(p.searchSuggest), "Preferences"),
      fact("Safe Browsing reports", onOff(p.safeBrowsingReports), "Preferences"),
      policyFact
    ],
    note: locked ? "A policy overrides the profile settings above, whatever they say."
      : "The privacy policy is the sturdy route: Chromium can't overwrite it, and it covers 14 settings at once without touching your profile."
        + (p.running ? " It applies the next time Chromium starts." : ""),
    actions: actions
  })
}

function networkPrivacy(p) {
  var b = CATALOG.netpriv
  var items = []
  function item(applies, on, k, v, owner) { if (applies) items.push({ on: on, f: fact(k, v, owner) }) }

  var h = p.hosts || { blocked: 0, total: 0 }
  item(h.total > 0, h.blocked === h.total, "Telemetry hosts",
    h.blocked === 0 ? "Not blocked" : h.blocked === h.total ? "All " + h.total + " blocked" : h.blocked + " of " + h.total + " blocked",
    h.blackOps ? BLACK_OPS : "/etc/hosts")
  item(p.fallbackDns !== null && p.fallbackDns !== undefined, p.fallbackDns === "off", "Backup DNS servers",
    p.fallbackDns === "off" ? "Off" : p.fallbackDns === "custom" ? "Your own servers" : "Public resolvers (Quad9, Cloudflare, Google)",
    p.fallbackDnsBlackOps ? BLACK_OPS : "systemd-resolved")
  item(p.connectivity !== null && p.connectivity !== undefined, p.connectivity === "off", "Connection check",
    p.connectivity === "off" ? "Off" : "Asks " + (p.connectivityHost || "a web server"),
    p.nmBlackOps ? BLACK_OPS : "NetworkManager")
  var id = p.identity
  item(!!id, !!id && id.mac && id.hostname, "Network identity",
    !id ? "" : (id.mac ? "Private address per network" : "Real hardware address") + (id.hostname ? "" : " · sends computer name"),
    p.nmBlackOps ? BLACK_OPS : "NetworkManager")
  item(p.avahiAnnounces !== null && p.avahiAnnounces !== undefined, p.avahiAnnounces === false, "Local announcements",
    p.avahiAnnounces ? "Announces this computer on the network" : "Off",
    p.avahiBlackOps ? BLACK_OPS : "Avahi")
  item(true, !p.debuginfod, "Debug symbol lookups",
    p.debuginfod ? "Asks debuginfod.archlinux.org when a program crashes" : "Off", "session")

  var on = items.filter(function(i) { return i.on }).length
  var n = items.length
  var managed = items.some(function(i) { return i.f.owner === BLACK_OPS })
  return check(b, {
    kind: on === n ? "good" : "info",
    status: on === 0 ? "Using Arch's defaults" : on === n ? "All " + n + " protections on" : on + " of " + n + " protections on",
    meta: on === n ? "Nothing more to turn on" : (n - on) + " optional — each has a small cost",
    facts: items.map(function(i) { return i.f }),
    note: managed ? "The Black Ops plugin manages some of these. Keepwell shows them but leaves them to it." : "",
    actions: on === n ? [] : [{ label: "Choose what to turn on…", primary: true, elevated: true }]
  })
}

var APP_NAMES = { vscode: "VS Code", spotify: "Spotify", discord: "Discord", steam: "Steam" }

function apps(p, net) {
  var b = CATALOG.apps
  var list = p.apps || []
  var dnt = fact("Do Not Track signal", net && net.doNotTrack ? "Sent to tools that honour it" : "Not set", "session")
  var dntAction = net && net.doNotTrack ? [] : [{ label: "Turn on Do Not Track" }]
  if (list.length === 0) return check(b, { kind: "good", status: "No known reporting apps installed",
    meta: "Arch itself sends nothing", facts: [dnt], actions: dntAction })
  var facts = [], on = 0, actions = []
  for (var i = 0; i < list.length; i++) {
    var a = list[i], name = APP_NAMES[a.id] || a.id
    if (a.id === "vscode") {
      var level = a.state === "off" ? "Telemetry off" : a.state === null ? "Settings unreadable" : "Telemetry on"
      if (a.state !== "off") { on++; actions.push({ label: "Open VS Code", primary: actions.length === 0, launch: "code.desktop" }) }
      facts.push(fact(name, level, "its own settings"))
    } else {
      facts.push(fact(name, "Can't be read here", "its own settings"))
    }
  }
  return check(b, { kind: on > 0 ? "attn" : "info",
    status: on > 0 ? plural(on, "installed app sends", "installed apps send") + " usage data"
      : plural(list.length, "installed app may send", "installed apps may send") + " usage data",
    meta: "Arch itself sends nothing", facts: facts.concat([dnt]), actions: actions.concat(dntAction),
    note: "Apps whose setting can't be read here usually have a usage-data or privacy option in their own settings. Do Not Track is a signal many developer tools read as “don't collect usage data”; apps that ignore it are unaffected." })
}

function media(p) {
  var b = CATALOG.cam
  var note = "A sliding camera cover or hardware mute switch is the only guarantee. Software can only report."
  if (p.error) return check(b, { kind: "off", status: "Couldn't read PipeWire", meta: "Check again in a moment", note: note })
  var mic = p.micUsers || [], cam = p.cameraUsers || []
  var busy = mic.length + cam.length > 0
  var parts = []
  if (cam.length) parts.push("Camera in use by " + cam.join(", "))
  if (mic.length) parts.push("Microphone in use by " + mic.join(", "))
  return check(b, { kind: busy ? "info" : "good",
    status: busy ? parts.join(" · ") : "Not in use right now",
    meta: "Checked when Keepwell opens",
    facts: [
      fact("Camera", p.cameras === 0 ? "None found" : cam.length ? "In use" : "Idle"),
      fact("Microphone", p.microphones === 0 ? "None found" : mic.length ? "In use" : plural(p.microphones, "found", "found") + ", idle")
    ], note: note })
}

function traces(p) {
  var b = CATALOG.traces
  var bits = []
  if (p.recentFiles !== null && p.recentFiles !== undefined) bits.push(plural(p.recentFiles, "recent file", "recent files"))
  if (p.thumbnailBytes) bits.push(bytes(p.thumbnailBytes) + " thumbnails")
  return check(b, { kind: "info", status: "Recent files, history and thumbnails",
    meta: bits.join(" · ") || "Nothing recorded",
    facts: [
      fact("Recent files", p.recentFiles === null ? "None" : plural(p.recentFiles, "entry", "entries")),
      fact("Shell history", p.historyLines === null ? "None" : plural(p.historyLines, "line", "lines")),
      fact("Thumbnails", bytes(p.thumbnailBytes) + (p.thumbnailsComplete ? "" : "+"))
    ],
    actions: [{ label: "Choose what to clear…", primary: true, trash: true }] })
}

function permissions(p) {
  var b = CATALOG.perms
  if (!p.flatpak) return check(b, { kind: "good", status: "No Flatpak apps on this computer",
    meta: "Nothing to review", facts: [fact("Flatpak", "Not installed")] })
  if (p.apps === 0) return check(b, { kind: "good", status: "No Flatpak apps installed", meta: "Nothing to review" })
  if (!p.flatseal) return check(b, { kind: "off", status: "Flatseal isn't installed",
    meta: plural(p.apps, "Flatpak app", "Flatpak apps") + " could be reviewed",
    facts: [fact("Flatpak apps", String(p.apps)), fact("Flatseal", "Not installed")],
    actions: [install("Install Flatseal", "install-flatseal")] })
  return check(b, { kind: "good", status: "Flatseal is ready",
    meta: plural(p.apps, "Flatpak app", "Flatpak apps"),
    facts: [fact("Flatpak apps", String(p.apps))], actions: [{ label: "Open Flatseal", primary: true, launch: "com.github.tchx84.Flatseal.desktop" }] })
}

// ---------------------------------------------------------------- system care

function cleanup(p) {
  var b = CATALOG.clean
  var safe = (p.pkgCache ? p.pkgCache.bytes || 0 : 0)
  var extraPkgs = p.pkgCacheAll ? Math.max(0, (p.pkgCacheAll.bytes || 0) - safe) : 0
  var orphans = p.orphans || { count: 0, bytes: 0 }
  var home = p.homeCache || { bytes: 0, complete: true }
  var total = safe + extraPkgs + (orphans.bytes || 0) + (home.bytes || 0)
  return check(b, { kind: "info",
    status: total > 0 ? "Up to " + bytes(total) + " can be freed" : "Nothing to clean up",
    meta: "App cache " + bytes(home.bytes) + " · package cache " + bytes(safe + extraPkgs) + " · logs " + bytes(p.journalBytes),
    facts: [
      fact("Old package versions", bytes(safe), "Safe · keeps 3"),
      fact("All but newest", bytes(extraPkgs), "Advanced · keeps 1"),
      fact("Unused packages", orphans.count ? plural(orphans.count, "package", "packages") + " · " + bytes(orphans.bytes) : "None", "Advanced"),
      fact("App cache", bytes(home.bytes) + (home.complete ? "" : "+"), "Review each"),
      fact("System logs", bytes(p.journalBytes), "journal")
    ],
    actions: [{ label: "Review cleanup…", primary: true }] })
}

function unclaimed() {
  return check(CATALOG.unclaimed, { kind: "off", status: "Not available in this build",
    meta: "Arrives with the cleanup tools" })
}

function snapshots(p) {
  var b = CATALOG.snap
  if (!p.snapper || !p.rootConfig) return check(b, { kind: "attn", status: "Snapshots aren't set up",
    meta: "Omarchy normally sets this up", facts: [fact("Snapper", p.snapper ? "Installed, no root config" : "Not installed")] })
  var sync = p.limineSync === "enabled"
  return check(b, { kind: sync ? "good" : "attn",
    status: sync ? "Set up — boot menu stays in sync" : "Set up, but the boot menu isn't syncing",
    meta: "Snapshot list needs admin rights to read",
    facts: [fact("Snapper", "Set up for the system"), fact("Boot menu", sync ? "In sync" : "Sync off", "limine-snapper-sync"),
            fact("Snapshots", "Ask the Snapshots plugin", "")],
    actions: [{ label: "Take snapshot now", primary: true, elevated: true, act: "snapshot" }] })
}

function disk(p) {
  var b = CATALOG.disk
  if (!p.size) return check(b, { kind: "off", status: "Couldn't read disk usage" })
  var pct = Math.round(100 * p.used / p.size)
  return check(b, { kind: pct >= 90 ? "crit" : pct >= 80 ? "attn" : "good",
    status: pct + "% used — " + bytes(p.free) + " free", meta: "/ · " + bytes(p.size),
    facts: [fact("Used", bytes(p.used) + " of " + bytes(p.size)), fact("Free", bytes(p.free))],
    actions: [p.baobab ? { label: "Open Disk Usage Analyzer", primary: true, launch: "org.gnome.baobab.desktop" }
      : install("Install Disk Usage Analyzer", "install-baobab")] })
}

function timers() {
  return check(CATALOG.timers, { kind: "off", status: "Nothing runs in the background",
    meta: "Optional weekly reports — notify, never act",
    facts: [fact("Vulnerability check", "Off"), fact("Cleanup report", "Off")],
    actions: [{ label: "Set up…", primary: true, disabled: true }] })
}

// ---------------------------------------------------------------- assembly

function loading(id) {
  return check(CATALOG[id], { kind: "off", status: "Checking…", meta: "" })
}

function hero(section, checks) {
  var w = Status.worst(checks)
  var hero = { crit: ["", ""], attn: ["", ""], good: ["", ""] }
  var crit = checks.filter(function(c) { return c.kind === "crit" })
  var attn = checks.filter(function(c) { return c.kind === "attn" })
  if (crit.length) hero.crit = ["Action needed", crit[0].status + "."]
  if (attn.length) hero.attn = [word(attn.length) + (attn.length === 1 ? " thing" : " things") + " to review",
    attn.map(function(c) { return c.title }).join(" · ")]
  // A healthy banner still says what isn't being checked, so "looks good"
  // never hides a switched-off check.
  var off = checks.filter(function(c) { return c.kind === "off" }).length
  hero.good = [section.id === "care" ? "Your system is in good shape" : section.name + " looks good",
    "Nothing needs your attention." + (off ? " " + word(off) + (off === 1 ? " optional check is" : " optional checks are") + " off." : "")]
  if (section.id === "care") {
    var clean = checks.filter(function(c) { return c.id === "clean" })[0]
    if (clean && clean.status.indexOf("Up to ") === 0) {
      hero.good[1] = clean.status.replace("can be freed", "can be freed whenever you like") + "."
      hero.goodCta = "Review cleanup"
    }
  }
  return hero
}

function build(doc, now) {
  var probes = doc && doc.probes ? doc.probes : null
  var net = doc ? doc.network === true : false
  function p(name) { return probes && probes[name] && typeof probes[name] === "object" ? probes[name] : {} }
  var makers = {
    audit: function() { return audit(p("audit"), net, now) },
    av: function() { return antivirus(p("antivirus"), now) },
    upd: function() { return updates(p("updates"), now) },
    fw: function() { return firewall(p("firewall")) },
    leaks: function() { return leaks(p("tools")) },
    browser: function() { return browser(p("browser"), p("chromiumPolicy")) },
    netpriv: function() { return networkPrivacy(p("netPrivacy")) },
    apps: function() { return apps(p("apps"), p("netPrivacy")) },
    cam: function() { return media(p("media")) },
    traces: function() { return traces(p("traces")) },
    perms: function() { return permissions(p("permissions")) },
    clean: function() { return cleanup(p("cleanup")) },
    unclaimed: unclaimed,
    snap: function() { return snapshots(p("snapshots")) },
    disk: function() { return disk(p("disk")) },
    timers: timers
  }
  var out = []
  for (var i = 0; i < LAYOUT.length; i++) {
    var s = LAYOUT[i]
    var checks = s.checks.map(function(id) {
      if (!probes) return loading(id)
      var probeName = { audit: "audit", av: "antivirus", upd: "updates", fw: "firewall", leaks: "tools",
        browser: "browser", netpriv: "netPrivacy", apps: "apps", cam: "media", traces: "traces", perms: "permissions",
        clean: "cleanup", snap: "snapshots", disk: "disk" }[id]
      var probe = probeName ? probes[probeName] : null
      if (probe && (probe.error === true && id !== "audit" && id !== "cam" || probe.skipped))
        return check(CATALOG[id], { kind: "off", status: "Couldn't check this time", meta: "Try Check again" })
      try { return makers[id]() } catch (e) { return check(CATALOG[id], { kind: "off", status: "Couldn't check this time" }) }
    })
    out.push({ id: s.id, name: s.name, checks: checks, hero: probes ? hero(s, checks) : {
      crit: ["", ""], attn: ["", ""], good: ["Checking…", "Reading your system's state. Nothing is changed."] } })
  }
  return out
}

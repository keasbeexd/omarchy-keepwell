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

// "Mon 19 Oct, 12:05" in local time.
function stamp(at) {
  var d = new Date(at * 1000)
  var pad = function(n) { return (n < 10 ? "0" : "") + n }
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][d.getDay()] + " " + d.getDate() + " "
    + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getMonth()]
    + ", " + pad(d.getHours()) + ":" + pad(d.getMinutes())
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
  deps: { id: "deps", title: "Dependency vulnerabilities", tool: "osv-scanner",
    what: "If you write software, osv-scanner checks the libraries your projects depend on — read from their lockfiles (package-lock.json, Cargo.lock, go.sum, requirements.txt and others) — against the OSV vulnerability database, and shows which have known problems and which version fixes them. It reports only; it never changes your projects." },
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
    what: "App folders in your home that nothing installed uses any more and that haven't changed in a long time — usually left behind by apps you removed. Suggestions only; nothing is removed unless you tick it." },
  snap: { id: "snap", title: "Snapshots", tool: "Snapper · Limine",
    what: "A snapshot is a restore point for the system (not your home folder). To roll back, pick it from the boot menu." },
  disk: { id: "disk", title: "Disk usage", tool: "Disk usage",
    what: "See which folders take the most space. Large caches and package downloads are normal; Cleanup handles those." }
}

var LAYOUT = [
  { id: "security", name: "Security", checks: ["audit", "av", "upd", "fw", "leaks", "deps"] },
  { id: "privacy", name: "Privacy", checks: ["browser", "netpriv", "apps", "cam", "traces", "perms"] },
  { id: "care", name: "System Care", checks: ["clean", "unclaimed", "snap", "disk"] }
]

// ---------------------------------------------------------------- security

// What each kind of problem arch-audit names means, in plain words.
var AUDIT_KINDS = {
  "arbitrary code execution": "crafted input could run code",
  "arbitrary command execution": "crafted input could run commands",
  "arbitrary filesystem access": "could reach files it shouldn't",
  "privilege escalation": "could gain more rights than it should",
  "denial of service": "crafted input could crash it",
  "information disclosure": "could leak information",
  "certificate verification bypass": "could trust a fake certificate",
  "signature forgery": "could accept a forged signature",
  "directory traversal": "could reach files outside its folder",
  "access restriction bypass": "could get past an access check",
  "authentication bypass": "could get past a login check",
  "insufficient validation": "doesn't check some input properly",
  "content spoofing": "could show forged content",
  "cross-site scripting": "web pages could inject scripts",
  "unknown": "kind not recorded"
}

function auditKinds(kinds) {
  var words = (kinds || []).filter(function(k) { return k !== "unknown" })
                           .map(function(k) { return AUDIT_KINDS[k] || k })
  return words.filter(function(w, i) { return words.indexOf(w) === i }).join("; ") || "kind not recorded"
}

function audit(p, net, now) {
  var b = CATALOG.audit
  var note = "Keepwell checks this every hour while you're logged in, downloading Arch's public security list (about 900 KB) from security.archlinux.org — except on a connection marked as metered."
  if (!p.installed) return check(b, { kind: "off", status: "arch-audit isn't installed",
    meta: "Small, official tool from the Arch repos", note: note,
    facts: [fact("Installed", "No")], actions: [install("Install arch-audit", "install-arch-audit")] })
  if (p.error) return check(b, { kind: "attn", status: "Couldn't reach the security tracker",
    meta: "Check your connection, then check again", note: note,
    actions: [{ label: "Check again", primary: true, run: "network" }] })
  if (!p.ran) return check(b, { kind: "info", status: "Not checked yet",
    meta: "Runs when you ask — it uses the network", note: note,
    actions: [{ label: "Check now", primary: true, run: "network" }] })

  var pkgs = p.packages || []
  var fixable = pkgs.filter(function(x) { return x.fixed })
  var seriousFix = fixable.filter(function(x) { return x.severity === "Critical" || x.severity === "High" })
  var seriousOpen = pkgs.filter(function(x) { return !x.fixed && (x.severity === "Critical" || x.severity === "High") })
  var order = { Critical: 0, High: 1, Medium: 2, Low: 3, Unknown: 4 }
  var facts = pkgs.slice().sort(function(x, y) {
    return (x.fixed ? 0 : 1) - (y.fixed ? 0 : 1) || order[x.severity] - order[y.severity]
  }).map(function(x) {
    var f = fact(x.name, x.severity + " · " + auditKinds(x.kinds),
      (x.fixed ? "fixed in " + x.fixed + " — update" : "no fix released yet") + (x.cves ? " · " + plural(x.cves, "CVE", "CVEs") : ""))
    // Each package's page on the tracker lists its CVEs and their details.
    if (/^[A-Za-z0-9@._+-]{1,128}$/.test(x.name)) f.url = "https://security.archlinux.org/package/" + x.name
    return f
  })
  if (pkgs.length === 0) facts.push(fact("Packages", "No known issues"))

  // Only a released fix is something to act on. An open issue with no fix
  // is worth knowing about, never worth alarming anyone over.
  var kind = seriousFix.length ? "crit" : fixable.length ? "attn" : seriousOpen.length ? "info" : "good"
  var status = fixable.length
    ? "An update fixes " + plural(fixable.length, "known issue", "known issues")
    : pkgs.length ? plural(pkgs.length, "package has", "packages have") + " known issues, none fixed yet"
    : "No known issues in installed packages"
  var meta = (fixable.length ? fixable.length + " fixable · " : "") + (pkgs.length - fixable.length) + " waiting for a fix · checked " + ago(p.at, now)
    + (p.refreshFailed ? " · couldn't refresh (offline?)" : p.skipped === "metered" ? " · not refreshed on a metered connection" : "")
  var whatNow = fixable.length
    ? "Updating installs the fixed versions. Issues still waiting for a fix need nothing from you yet."
    : "There is nothing to do right now: no fixed versions have been released. They arrive through normal updates, and Keepwell will flag them when they do. Most of these need someone to send you a specially crafted file or page."
  return check(b, { kind: kind, status: status, meta: meta, facts: facts,
    note: whatNow + " Click a package to see its CVEs on the Arch security tracker. " + note,
    actions: (fixable.length ? [{ label: "Update system", primary: true, elevated: true, act: "update" }] : [])
      .concat([{ label: "Check again", run: "network" }, { label: "Arch security tracker ↗", url: "https://security.archlinux.org/" }]) })
}

function antivirus(p, now) {
  var b = CATALOG.av
  var honest = "Antivirus is one layer, not a force field. Updates and the firewall do more of the work."
  if (!p.clamav) return check(b, { kind: "off", status: "Not installed — optional",
    meta: "Useful if you share files with Windows users", note: honest,
    facts: [fact("ClamAV", "Not installed")], actions: [install("Install ClamAV", "install-clamav")] })
  var age = days(p.definitionsAt, now)
  var auto = p.freshclamEnabled === "enabled"
  var last = p.lastScan
  var where = function(t) { return t === "home" ? "Home folder" : "Downloads" }
  var lastText = !last ? "No scans yet"
    : !last.finished ? where(last.target) + " · " + ago(last.at, now) + " · stopped before the end"
    : where(last.target) + " · " + ago(last.at, now) + " · " + (last.infected ? plural(last.infected, "infected file", "infected files")
        : "nothing found") + (typeof last.files === "number" ? " in " + plural(last.files, "file", "files") : "")
  var facts = [
    fact("Definitions", age === null ? "None downloaded yet" : age === 0 ? "Updated today" : plural(age, "day", "days") + " old"),
    fact("Auto-update", auto ? "On" : "Off", "clamav-freshclam"),
    fact("Last scan", p.scanning ? "Scanning now…" : lastText, "Keepwell")
  ]
  var found = last && last.finished && last.infected ? last.found || [] : []
  for (var i = 0; i < found.length; i++) facts.push(fact(i === 0 ? "Found" : "", found[i]))
  var stale = age === null || age > 7
  var actions = []
  if (p.scanning) actions.push({ label: "Stop scan", primary: true, stop: "clamscan" })
  else if (age !== null) {
    actions.push({ label: "Scan Downloads", primary: !stale || auto, scan: "downloads" })
    actions.push({ label: "Scan home folder", scan: "home" })
  }
  if (!auto) actions.push({ label: "Turn on auto-update", primary: !p.scanning, elevated: true, act: "freshclam-on" })
  return check(b, {
    kind: found.length ? "crit" : stale ? "attn" : "good",
    status: p.scanning ? "Scanning in the background…"
      : found.length ? plural(found.length, "infected file", "infected files") + " found"
      : age === null ? "No virus definitions yet" : stale ? "Virus definitions are " + age + " days old" : "Definitions are up to date",
    meta: p.scanning ? "You'll get a notification when it's done" : last ? "Last scan " + ago(last.at, now) : "No scans yet",
    facts: facts,
    note: found.length
      ? "Keepwell doesn't delete anything. Check each file: if you don't recognise it, move it to the Trash yourself; if you do, it may be a false alarm."
      : "Scans run in the background at low priority and skip caches and the Trash. A home-folder scan can take half an hour or more. " + honest,
    actions: actions })
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

function leaks(tools, now) {
  var b = CATALOG.leaks
  if (!tools.gitleaks) return check(b, { kind: "off", status: "Not set up — optional",
    meta: "Finds keys and passwords committed to git", facts: [fact("Installed", "No")],
    actions: [install("Install gitleaks", "install-gitleaks")] })
  var last = tools.leaks
  var home = { label: "Scan home folder", primary: !last, rescan: "leaks", folder: "~" }
  var choose = { label: "Choose another folder…", pick: "leaks" }
  if (tools.leaksScanning) return check(b, { kind: "info", status: "Scanning in the background…",
    meta: "You'll get a notification when it's done", facts: last ? [fact("Folder", last.folder)] : [],
    actions: [{ label: "Stop scan", primary: true, stop: "gitleaks" }] })
  if (!last) return check(b, { kind: "off", status: "Ready to scan",
    meta: "Read-only: it reports, it never changes a repo", facts: [fact("Installed", "Yes")],
    note: "Keepwell finds the git repositories in your home folder (up to four levels down, following links like ~/Projects) and checks their history in the background. Secrets are masked; only where they are is kept.",
    actions: [home, choose] })
  var f = last.findings || []
  var facts = [fact("Folder", last.folder === "~" ? "Home folder" : last.folder), fact("Repositories", plural(last.scanned, "scanned", "scanned") + (last.failed ? " · " + last.failed + " couldn't be read" : ""))]
  for (var i = 0; i < Math.min(f.length, 30); i++)
    facts.push(fact(f[i].repo, f[i].file + (f[i].line ? ":" + f[i].line : ""), f[i].rule + (f[i].commit ? " · " + f[i].commit : "")))
  return check(b, { kind: f.length ? "attn" : "good",
    status: f.length ? plural(f.length, "possible secret", "possible secrets") + " in your repositories"
      : last.repos ? "No secrets found" : "No git repositories in that folder",
    meta: "Scanned " + ago(last.at, now) + " · " + plural(last.repos, "repository", "repositories"),
    facts: facts,
    note: f.length ? "Each line is a file and line where something looks like a key or password, and the commit it was added in. If it's real, change that password or key — removing it from the file doesn't remove it from git history." : "",
    actions: [{ label: "Scan again", primary: f.length > 0, rescan: "leaks", folder: last.folder }]
      .concat(last.folder === "~" ? [choose] : [home, choose]) })
}

// The higher of two version strings, comparing number runs as numbers
// ("4.17.21" > "4.17.9"). Good enough to name the version that fixes all.
function newer(a, b) {
  var x = String(a).split(/[^0-9A-Za-z]+/), y = String(b).split(/[^0-9A-Za-z]+/)
  for (var i = 0; i < Math.max(x.length, y.length); i++) {
    var p = x[i] || "0", q = y[i] || "0"
    var np = /^\d+$/.test(p), nq = /^\d+$/.test(q)
    var c = np && nq ? Number(p) - Number(q) : p < q ? -1 : p > q ? 1 : 0
    if (c !== 0) return c > 0 ? a : b
  }
  return a
}

function deps(tools, now) {
  var b = CATALOG.deps
  var network = "Scanning sends your projects' dependency names and versions to Google's OSV.dev service; nothing else leaves this computer."
  if (!tools.osvScanner) return check(b, { kind: "off", status: "Not set up — optional",
    meta: "For people who write software", facts: [fact("Installed", "No")], note: network,
    actions: [install("Install osv-scanner", "install-osv-scanner")] })
  var last = tools.osv
  var home = { label: "Scan home folder", primary: !last, rescan: "osv", folder: "~" }
  var choose = { label: "Choose another folder…", pick: "osv" }
  if (tools.osvScanning) return check(b, { kind: "info", status: "Scanning in the background…",
    meta: "You'll get a notification when it's done", facts: last ? [fact("Folder", last.folder === "~" ? "Home folder" : last.folder)] : [],
    actions: [{ label: "Stop scan", primary: true, stop: "osv" }] })
  if (!last) return check(b, { kind: "off", status: "Ready to scan",
    meta: "Reads your projects' lockfiles; changes nothing", facts: [fact("Installed", "Yes")],
    note: "Keepwell finds your projects (git repositories up to four levels down) and checks each one in the background. " + network,
    actions: [home, choose] })
  var f = last.findings || []
  var fixable = f.filter(function(x) { return x.fixable })
  var facts = [fact("Folder", last.folder === "~" ? "Home folder" : last.folder),
               fact("Projects", plural(last.scanned, "scanned", "scanned")
                 + (last.noLockfiles ? " · " + last.noLockfiles + " without dependency files" : "")
                 + (last.failed ? " · " + last.failed + " couldn't be read" : ""))]
  for (var i = 0; i < Math.min(f.length, 40); i++) {
    var x = f[i]
    var fixes = (x.vulns || []).reduce(function(all, v) { return all.concat(v.fixed || []) }, [])
    var target = fixes.length ? fixes.reduce(newer) : ""
    var cves = (x.vulns || []).map(function(v) { return v.cve }).filter(function(c) { return c })
    var row = fact(x.package + " " + x.version,
      x.severity + " · " + plural(x.count, "vulnerability", "vulnerabilities")
        + (cves.length ? " (" + cves.slice(0, 2).join(", ") + (cves.length > 2 ? "…" : "") + ")" : "")
        + (x.vulns && x.vulns[0] && x.vulns[0].summary ? " — " + x.vulns[0].summary : ""),
      (x.fixable ? "update to " + target + " or later" : target ? "partly fixed in " + target : "no fix released yet")
        + " · " + x.repo + "/" + x.file + (x.ecosystem ? " (" + x.ecosystem + ")" : ""))
    if (x.vulns && x.vulns[0] && /^[A-Za-z0-9._:-]{1,64}$/.test(x.vulns[0].id)) row.url = "https://osv.dev/vulnerability/" + x.vulns[0].id
    facts.push(row)
  }
  // A project osv-scanner couldn't check (offline, OSV.dev unreachable) is
  // never counted as clean.
  if (last.failed && !f.length) return check(b, { kind: "attn",
    status: last.scanned ? "Only " + last.scanned + " of " + (last.scanned + last.failed) + " projects could be checked"
      : "Couldn't check your projects",
    meta: "osv-scanner couldn't reach OSV.dev, or stopped — check your connection and scan again",
    facts: facts, note: network,
    actions: [{ label: "Scan again", primary: true, rescan: "osv", folder: last.folder }]
      .concat(last.folder === "~" ? [choose] : [home, choose]) })
  return check(b, {
    kind: fixable.length || last.failed ? "attn" : f.length ? "info" : "good",
    status: f.length ? plural(f.length, "dependency has", "dependencies have") + " known vulnerabilities"
      : !last.scanned ? "No projects found in that folder"
      : last.noLockfiles >= last.scanned ? "Nothing to check: no dependency files in " + plural(last.scanned, "project", "projects")
      : "No known vulnerabilities in your projects' dependencies",
    meta: (fixable.length ? fixable.length + " fixable by updating · " : "") + "scanned " + ago(last.at, now) + " · " + plural(last.scanned, "project", "projects"),
    facts: facts,
    note: f.length ? "Each row is a library one of your projects uses, the worst problem it has, and the version that fixes it. Update it in that project (for example npm update, cargo update, go get -u, pip install -U), then scan again. Click a row for the advisory on osv.dev. Keepwell never changes your projects. " + network : network,
    actions: [{ label: "Scan again", primary: fixable.length > 0, rescan: "osv", folder: last.folder }]
      .concat(last.folder === "~" ? [choose] : [home, choose]) })
}

// ---------------------------------------------------------------- privacy

var BLACK_OPS = "managed by Black Ops"
var KEEPWELL = "set by Keepwell"

// Who owns a setting, for its fact line: Black Ops, Keepwell, or the
// component it belongs to.
function owner(blackOps, keepwell, component) { return blackOps ? BLACK_OPS : keepwell ? KEEPWELL : component }

function browser(p, policy) {
  var b = CATALOG.browser
  if (!p.chromium) return check(b, { kind: "off", status: "Chromium isn't installed",
    meta: p.firefox ? "Firefox support comes later" : "No supported browser found" })
  policy = policy || {}
  var locked = policy.total > 0 && policy.set === policy.total
  var policyFact = fact("Privacy policy",
    !policy.set ? "Not installed" : locked ? "All " + policy.total + " in force" : policy.set + " of " + policy.total + " in force",
    policy.blackOps ? BLACK_OPS : policy.keepwell ? "set by Keepwell" : "system-wide policy")
  var actions = policy.blackOps ? []
    : policy.keepwell ? [{ label: "Remove privacy policy…", elevated: true, act: "chromium-policy-off" }]
    : locked ? [] : [{ label: "Apply privacy policy…", primary: true, elevated: true, act: "chromium-policy" }]
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
    owner(h.blackOps, h.keepwell, "/etc/hosts"))
  item(p.fallbackDns !== null && p.fallbackDns !== undefined, p.fallbackDns === "off", "Backup DNS servers",
    p.fallbackDns === "off" ? "Off" : p.fallbackDns === "custom" ? "Your own servers" : "Public resolvers (Quad9, Cloudflare, Google)",
    owner(p.fallbackDnsBlackOps, p.fallbackDnsKeepwell, "systemd-resolved"))
  item(p.connectivity !== null && p.connectivity !== undefined, p.connectivity === "off", "Connection check",
    p.connectivity === "off" ? "Off" : "Asks " + (p.connectivityHost || "a web server"),
    owner(p.nmBlackOps, p.connectivityKeepwell, "NetworkManager"))
  var id = p.identity
  item(!!id, !!id && id.mac && id.hostname, "Network identity",
    !id ? "" : (id.mac ? "Private address per network" : "Real hardware address") + (id.hostname ? "" : " · sends computer name"),
    owner(p.nmBlackOps, p.identityKeepwell, "NetworkManager"))
  item(p.avahiAnnounces !== null && p.avahiAnnounces !== undefined, p.avahiAnnounces === false, "Local announcements",
    p.avahiAnnounces ? "Announces this computer on the network" : "Off",
    owner(p.avahiBlackOps, p.avahiKeepwell, "Avahi"))
  item(true, !p.debuginfod, "Debug symbol lookups",
    p.debuginfod ? "Asks debuginfod.archlinux.org when a program crashes" : "Off", owner(false, p.debuginfodKeepwell, "session"))

  var on = items.filter(function(i) { return i.on }).length
  var n = items.length
  var managed = items.some(function(i) { return i.f.owner === BLACK_OPS })
  return check(b, {
    kind: on === n ? "good" : "info",
    status: on === 0 ? "Using Arch's defaults" : on === n ? "All " + n + " protections on" : on + " of " + n + " protections on",
    meta: on === n ? "Nothing more to turn on" : (n - on) + " optional — each has a small cost",
    facts: items.map(function(i) { return i.f }),
    note: managed ? "The Black Ops plugin manages some of these. Keepwell shows them but leaves them to it." : "",
    actions: [{ label: on === n ? "Change settings…" : "Choose what to turn on…", primary: on < n, elevated: true, act: "privacy" }]
  })
}

var APP_NAMES = { vscode: "VS Code", spotify: "Spotify", discord: "Discord", steam: "Steam" }

function apps(p, net) {
  var b = CATALOG.apps
  var list = p.apps || []
  var dnt = fact("Do Not Track signal", net && net.doNotTrack ? "Sent to tools that honour it" : "Not set",
    owner(false, net && net.doNotTrackKeepwell, "session"))
  var dntAction = net && net.doNotTrack ? [] : [{ label: "Turn on Do Not Track…", elevated: true, act: "privacy" }]
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
  if (p.error) return check(b, { kind: "off", status: "Couldn't read PipeWire", meta: "Refresh in a moment", note: note })
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
    actions: [{ label: "Choose what to clear…", primary: true, trash: true, trashSet: "traces" }] })
}

function permissions(p) {
  var b = CATALOG.perms
  if (!p.flatpak) return check(b, { kind: "good", status: "No Flatpak apps on this computer",
    meta: "Nothing to review", facts: [fact("Flatpak", "Not installed")],
    note: "Flatpak is another way to install apps, each in its own sandbox. If you start using it, Flatseal shows what each app may reach.",
    actions: [{ label: "Install Flatpak and Flatseal", elevated: true, act: "install-flatseal" }] })
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
  var removed = p.pkgUninstalled ? p.pkgUninstalled.bytes || 0 : 0
  var orphans = p.orphans || { count: 0, bytes: 0 }
  var home = p.homeCache || { bytes: 0, complete: true }
  var total = safe + extraPkgs + removed + (orphans.bytes || 0) + (home.bytes || 0)
  return check(b, { kind: "info",
    status: total > 0 ? "Up to " + bytes(total) + " can be freed" : "Nothing to clean up",
    meta: "App cache " + bytes(home.bytes) + " · package cache " + bytes(safe + extraPkgs + removed) + " · logs " + bytes(p.journalBytes),
    facts: [
      fact("Old package versions", bytes(safe), "Safe · keeps 3"),
      fact("Removed packages' downloads", bytes(removed), "Safe"),
      fact("All but newest", bytes(extraPkgs), "Advanced · keeps 1"),
      fact("Unused packages", orphans.count ? plural(orphans.count, "package", "packages") + " · " + bytes(orphans.bytes) : "None", "Advanced"),
      fact("App cache", bytes(home.bytes) + (home.complete ? "" : "+"), "Review each"),
      fact("System logs", bytes(p.journalBytes), "journal")
    ],
    actions: [{ label: "Review cleanup…", primary: true, elevated: true, act: "cleanup" },
              { label: "Review app cache…", trash: true, trashSet: "cache" }] })
}

var AGE_WORDS = { 90: "3 months", 180: "6 months", 365: "1 year", 730: "2 years" }
function ageWords(days) { return AGE_WORDS[days] || plural(days, "day", "days") }

function unclaimed(p) {
  var b = CATALOG.unclaimed
  if (typeof p.count !== "number") return check(b, { kind: "off", status: "Couldn't look this time", meta: "Try Refresh" })
  var review = { label: "Review…", primary: p.count > 0, trash: true, trashSet: "unclaimed" }
  var facts = [
    fact("Looked at", plural(p.looked, "app folder", "app folders") + " nothing installed claims", "~, ~/.config, ~/.local/share"),
    fact("Untouched for", ageWords(p.days) + " or more", "adjustable")
  ]
  if (p.ignored) facts.push(fact("Ignored", plural(p.ignored, "folder", "folders"), "never suggested"))
  var actions = [review]
  if (p.ignored) actions.push({ label: "Stop ignoring " + plural(p.ignored, "folder", "folders"), unignore: "unclaimed" })
  return check(b, {
    kind: p.count ? "info" : "good",
    status: p.count ? plural(p.count, "app folder", "app folders") + " nothing uses any more" : "Nothing left behind",
    meta: p.count ? bytes(p.bytes) + " · untouched for " + ageWords(p.days) + " or more · verify before removing"
      : "No unclaimed folder untouched for " + ageWords(p.days),
    facts: facts,
    note: "A folder is suggested only when no installed package, program, app or Omarchy default uses its name and nothing in it has changed for that long. Check each one: it may hold something you want. Removing moves it to the Trash.",
    actions: actions })
}

function snapshots(p, now) {
  var b = CATALOG.snap
  if (!p.snapper || !p.rootConfig) return check(b, { kind: "attn", status: "Snapshots aren't set up",
    meta: "Omarchy normally sets this up", facts: [fact("Snapper", p.snapper ? "Installed, no root config" : "Not installed")] })
  var sync = p.limineSync === "enabled"
  var last = p.last
  var when = last ? ago(last.at, now) + " · " + stamp(last.at) : ""
  return check(b, { kind: sync ? "good" : "attn",
    status: last ? "Last snapshot " + ago(last.at, now) : sync ? "Set up — boot menu stays in sync" : "Set up, but the boot menu isn't syncing",
    meta: (sync ? "Boot menu in sync" : "Boot menu not syncing") + (p.keep ? " · keeps " + p.keep : ""),
    facts: [
      fact("Last snapshot", last ? "#" + last.number + " · " + when : "None in the recent system log"),
      fact("Boot menu", sync ? "In sync" : "Sync off", "limine-snapper-sync"),
      fact("Kept", p.keep ? "The newest " + p.keep : "Snapper's default", "Snapper")
    ],
    note: "Omarchy takes a snapshot before every update. To roll back, pick a snapshot in the boot menu; it restores the system, not your home folder.",
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

var DAY_NAMES = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" }
var PART_NAMES = { vulns: "Vulnerability check", cleanup: "Cleanup report",
                   "scan-downloads": "Virus scan of Downloads", "scan-home": "Virus scan of your home folder" }

// "Mon, Wed, Fri", "Every day", "Weekdays", "Weekends".
function dayWords(days) {
  var d = (days || []).join(",")
  if (d === "mon,tue,wed,thu,fri,sat,sun") return "Every day"
  if (d === "mon,tue,wed,thu,fri") return "Weekdays"
  if (d === "sat,sun") return "Weekends"
  return (days || []).map(function(x) { return DAY_NAMES[x] || x }).join(", ")
}

// systemd's "Tue 2026-10-20 11:00:00 EDT" as "Tue 20 Oct, 11:00".
function nextWords(s) {
  var m = /^(\w{3}) (\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})/.exec(s)
  if (!m) return s
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  return m[1] + " " + Number(m[4]) + " " + months[Number(m[3]) - 1] + ", " + m[5]
}

// The always-on checks and the deep-scan schedule, for the rail's footer and
// the missed-run strip: settings of Keepwell rather than checks of the system.
function schedules(doc, now) {
  var probe = doc && doc.probes && doc.probes.schedule && typeof doc.probes.schedule === "object" ? doc.probes.schedule : {}
  var p = probe.deep && typeof probe.deep === "object" ? probe.deep : {}
  var out = {
    always: doc ? "Checked " + ago(doc.at, now) : "Checking…",
    deep: {
      enabled: p.enabled === true,
      running: p.running === true,
      when: p.enabled ? dayWords(p.days) + " at " + p.time : "Off",
      next: p.enabled && p.next ? nextWords(p.next) : "",
      last: p.last && typeof p.last.at === "number" ? ago(p.last.at, now) + " · " + p.last.summary : "",
      settings: p
    },
    missed: []
  }
  if (typeof p.missed === "number")
    out.missed.push({ kind: "deep", text: "The last scheduled deep scan (" + stamp(p.missed) + ") was missed"
      + (p.next ? ". Next: " + nextWords(p.next) + "." : ".") })
  return out
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
    leaks: function() { return leaks(p("tools"), now) },
    deps: function() { return deps(p("tools"), now) },
    browser: function() { return browser(p("browser"), p("chromiumPolicy")) },
    netpriv: function() { return networkPrivacy(p("netPrivacy")) },
    apps: function() { return apps(p("apps"), p("netPrivacy")) },
    cam: function() { return media(p("media")) },
    traces: function() { return traces(p("traces")) },
    perms: function() { return permissions(p("permissions")) },
    clean: function() { return cleanup(p("cleanup")) },
    unclaimed: function() { return unclaimed(p("unclaimed")) },
    snap: function() { return snapshots(p("snapshots"), now) },
    disk: function() { return disk(p("disk")) }
  }
  var out = []
  for (var i = 0; i < LAYOUT.length; i++) {
    var s = LAYOUT[i]
    var checks = s.checks.map(function(id) {
      if (!probes) return loading(id)
      var probeName = { audit: "audit", av: "antivirus", upd: "updates", fw: "firewall", leaks: "tools",
        deps: "tools", browser: "browser", netpriv: "netPrivacy", apps: "apps", cam: "media", traces: "traces", perms: "permissions",
        clean: "cleanup", unclaimed: "unclaimed", snap: "snapshots", disk: "disk" }[id]
      var probe = probeName ? probes[probeName] : null
      if (probe && (probe.error === true && id !== "audit" && id !== "cam" || probe.skipped))
        return check(CATALOG[id], { kind: "off", status: "Couldn't check this time", meta: "Try Refresh" })
      try { return makers[id]() } catch (e) { return check(CATALOG[id], { kind: "off", status: "Couldn't check this time" }) }
    })
    out.push({ id: s.id, name: s.name, checks: checks, hero: probes ? hero(s, checks) : {
      crit: ["", ""], attn: ["", ""], good: ["Checking…", "Reading your system's state. Nothing is changed."] } })
  }
  return out
}

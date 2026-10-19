import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "core"
import "model/Present.js" as Present
import "model/Status.js" as Status

// The plugin's always-on half. It owns the check results, the window, the
// actions and the IPC route that opens the window, so everything works with
// or without the bar icon: `omarchy-shell keepwell toggle` from a keybinding
// reaches it either way.
//
// When checks run:
//   - once when the shell starts, so the bar icon means something;
//   - when the window opens, if the last result is over a minute old;
//   - when you press "Check again", and after an action's terminal closes.
// All of these are local and read-only. arch-audit, which downloads the Arch
// security tracker data, runs only when you ask for it. Nothing repeats on a
// timer.
//
// Actions that change the system go through bin/keepwell-run: its plan is
// shown in the confirm sheet, then it runs in a visible terminal while the
// window steps aside, and the window comes back when that terminal closes.
Scope {
  id: root

  property string omarchyPath: ""
  property var shell: null
  property var manifest: null

  // Where this plugin's files are, from this file's URL: the shell strips
  // __sourceDir from a third-party manifest.
  readonly property string sourceDir: {
    var url = String(Qt.resolvedUrl("."))
    if (url.indexOf("file://") !== 0) return ""
    try { url = decodeURIComponent(url.substring(7)) } catch (e) { return "" }
    return url.replace(/\/$/, "")
  }
  readonly property var python: ["/usr/bin/python3", "-I", "-S"]

  // ---------------- results ----------------
  property var doc: null
  property bool failed: false
  property real now: Date.now() / 1000

  readonly property bool checking: checker.running
  readonly property var sections: Present.build(doc, now)
  readonly property string checkedAt: checking ? "Checking…"
    : failed ? "Last check failed"
    : doc ? "Checked " + Present.ago(doc.at, now) : ""

  readonly property var allChecks: {
    var all = []
    for (var i = 0; i < sections.length; i++) all = all.concat(sections[i].checks)
    return all
  }
  readonly property string worst: doc ? Status.worst(allChecks) : "good"
  readonly property string summary: Status.summary(allChecks)

  function findCheck(id) {
    for (var i = 0; i < allChecks.length; i++) if (allChecks[i].id === id) return allChecks[i]
    return null
  }

  // ---------------- running the checks ----------------
  property bool queued: false
  property bool queuedNetwork: false
  // Said in the footer once the next check lands: { checkId, prefix }.
  property var reportAfterCheck: null

  function check(network) {
    if (sourceDir === "") return
    if (checker.running) {
      // One run at a time; a request made meanwhile runs right after.
      queued = true
      queuedNetwork = queuedNetwork || network
      return
    }
    var argv = python.concat([sourceDir + "/bin/keepwell-check"])
    if (network) argv.push("--network")
    checker.start(argv)
  }

  function accept(text) {
    var parsed
    try { parsed = JSON.parse(text) } catch (e) { return false }
    if (!parsed || parsed.v !== 1 || typeof parsed.at !== "number" || !parsed.probes
        || typeof parsed.probes !== "object") return false
    // A local re-check keeps the last arch-audit result rather than forgetting
    // it: the tracker was only asked when you asked.
    if (!parsed.network && doc && doc.network && doc.probes && doc.probes.audit
        && parsed.probes.audit && parsed.probes.audit.installed) {
      parsed.probes.audit = doc.probes.audit
      parsed.network = true
    }
    doc = parsed
    now = Date.now() / 1000
    return true
  }

  BoundedProcess {
    id: checker
    maxBytes: 128 * 1024
    timeoutMs: 40000
    onFinished: function(ok, text) {
      root.failed = !ok || !root.accept(text)
      if (root.reportAfterCheck && !root.queued) {
        var c = root.findCheck(root.reportAfterCheck.checkId)
        root.say(root.reportAfterCheck.prefix + (c ? c.title + ": " + c.status + "." : ""))
        root.reportAfterCheck = null
      }
      if (root.queued) {
        var net = root.queuedNetwork
        root.queued = false
        root.queuedNetwork = false
        root.check(net)
      }
    }
  }

  Timer {
    interval: 30000
    repeat: true
    running: root.opened
    onTriggered: root.now = Date.now() / 1000
  }

  // The check the window should show when it next opens (after a terminal).
  property string focusCheckId: ""

  Component.onCompleted: {
    check(false)
    pendingReader.start(python.concat([sourceDir + "/bin/keepwell-run", "pending", "get"]))
  }

  // ---------------- actions ----------------
  // The confirm sheet's state, bound into the window.
  property bool confirmOpen: false
  property var confirmPlan: null
  property bool confirmFailed: false
  property bool confirmSnapshot: false
  property string confirmContext: ""
  property var confirmChosen: null    // option ids; null until the first plan
  property var pendingAct: null       // { act, checkId }
  property bool planDirty: false

  function say(text) { if (windowLoader.item) windowLoader.item.notice = text }

  function requestAction(action, checkId, context) {
    if (!action || action.disabled) return
    if (terminal) { say("Finish the open Keepwell terminal first."); return }
    if (action.run === "network") { say(""); check(true); return }
    if (action.launch) { launch(action.launch); return }
    if (action.act) { openConfirm(action.act, checkId, context); return }
    if (action.scan === "downloads" || action.scan === "home") {
      startJob(["scan", action.scan], "Scanning " + (action.scan === "home" ? "your home folder" : "Downloads")
               + " in the background — you'll get a notification when it's done.")
      return
    }
    if (action.stop === "clamscan" || action.stop === "gitleaks") { startJob(["stop", action.stop], "Scan stopped."); return }
    if (action.rescan === "leaks" && typeof action.folder === "string") {
      startJob(["leaks", action.folder], "Scanning for secrets in the background — you'll get a notification when it's done.")
      return
    }
    if (action.pick === "leaks") {
      if (picker.running) return
      picking = true
      hide()
      picker.start(python.concat([sourceDir + "/bin/keepwell-run", "pick-folder"]))
      return
    }
    if (typeof action.url === "string"
        && /^https:\/\/security\.archlinux\.org\/(package\/[A-Za-z0-9@._+-]{1,128})?$/.test(action.url)) {
      Quickshell.execDetached(["/usr/bin/uwsm-app", "--", "/usr/bin/xdg-open", action.url])
      hide()
      return
    }
    if (action.trashSet) { openTrash(action.trashSet, action.label, context); return }
    if (action.unignore === "unclaimed") {
      startJob(["unclaimed", "unignore"], "Ignored folders will be suggested again.")
      return
    }
    say("“" + action.label + "” arrives in the next build.")
  }

  function launch(desktopId) {
    // A fixed vocabulary from Present.js; checked anyway before it reaches argv.
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.desktop$/.test(desktopId)) return
    Quickshell.execDetached(["/usr/bin/uwsm-app", "--", desktopId])
    hide()
  }

  function openConfirm(act, checkId, context) {
    pendingAct = { act: act, checkId: checkId }
    confirmContext = context
    confirmSnapshot = false
    confirmChosen = null
    confirmOpen = true
    fetchPlan()
  }

  function fetchPlan() {
    if (!pendingAct) return
    confirmPlan = null
    confirmFailed = false
    if (planner.running) { planDirty = true; return }
    planner.start(python.concat([sourceDir + "/bin/keepwell-run", "plan", pendingAct.act], runFlags()))
  }

  // The same flags for the plan and for the terminal, so they agree.
  function runFlags() {
    var flags = []
    if (confirmSnapshot) flags.push("--snapshot")
    if (confirmChosen !== null) flags.push("--with", confirmChosen.join(","))
    return flags
  }

  function toggleAllOptions() {
    if (!confirmPlan || confirmChosen === null) return
    var all = confirmPlan.options.map(function(o) { return o.id })
    confirmChosen = confirmChosen.length === all.length ? [] : all
    fetchPlan()
  }

  function toggleOption(id) {
    if (!confirmPlan || confirmChosen === null) return
    var next = confirmChosen.slice()
    var at = next.indexOf(id)
    if (at === -1) next.push(id)
    else next.splice(at, 1)
    confirmChosen = next
    fetchPlan()
  }

  function validPlan(p) {
    if (!p || !pendingAct || p.id !== pendingAct.act || typeof p.title !== "string"
        || typeof p.summary !== "string" || !Array.isArray(p.steps) || p.steps.length > 20
        || !Array.isArray(p.options) || p.options.length > 20) return false
    if (p.steps.length === 0 && p.options.length === 0) return false
    for (var j = 0; j < p.options.length; j++) {
      var o = p.options[j]
      if (!o || !/^[a-z0-9]{1,24}$/.test(o.id) || typeof o.label !== "string"
          || typeof o.hint !== "string" || typeof o.checked !== "boolean") return false
    }
    for (var i = 0; i < p.steps.length; i++) {
      var s = p.steps[i]
      if (!s || typeof s.say !== "string" || typeof s.cmd !== "string" || s.cmd.length > 2000
          || (s.content !== undefined && (typeof s.content !== "string" || s.content.length > 8000))
          || (s.diff !== undefined && (typeof s.diff !== "string" || s.diff.length > 8000))) return false
    }
    return true
  }

  BoundedProcess {
    id: planner
    maxBytes: 64 * 1024
    timeoutMs: 15000
    onFinished: function(ok, text) {
      if (root.planDirty) { root.planDirty = false; root.fetchPlan(); return }
      var p = null
      if (ok) { try { p = JSON.parse(text) } catch (e) { p = null } }
      if (root.validPlan(p)) {
        // The first plan says which options start ticked.
        if (root.confirmChosen === null)
          root.confirmChosen = p.options.filter(function(o) { return o.checked }).map(function(o) { return o.id })
        root.confirmPlan = p
      } else root.confirmFailed = true
    }
  }

  function toggleSnapshot() {
    if (!confirmPlan || !confirmPlan.snapshotOffered) return
    confirmSnapshot = !confirmSnapshot
    fetchPlan()
  }

  function cancelConfirm() {
    confirmOpen = false
    pendingAct = null
  }

  // ---------------- moving things to Trash ----------------
  // No root and no terminal: the sheet lists every item with its size, and
  // what you tick goes to Trash, where it can be restored.
  property bool trashOpen: false
  property string trashSet: ""
  property string trashTitle: ""
  property string trashContext: ""
  property var trashItems: null
  property bool trashFailed: false
  property var trashChecked: ({})
  // The unclaimed finder's age setting, from its listing.
  property int trashDays: 0
  property var trashDayChoices: []

  function openTrash(set, label, context) {
    if (lister.running || trasher.running) return
    trashSet = set
    trashTitle = set === "cache" ? "Clear app caches" : set === "unclaimed" ? "Unclaimed app folders" : "Clear activity traces"
    trashContext = context
    trashItems = null
    trashFailed = false
    trashChecked = ({})
    trashDays = 0
    trashDayChoices = []
    trashOpen = true
    lister.start(python.concat([sourceDir + "/bin/keepwell-run", "list", set]))
  }

  function toggleTrashItem(id) {
    var next = {}
    for (var k in trashChecked) next[k] = trashChecked[k]
    next[id] = !next[id]
    trashChecked = next
  }

  function toggleAllTrash() {
    var items = trashItems || []
    var all = items.length > 0 && items.every(function(i) { return root.trashChecked[i.id] === true })
    var next = {}
    if (!all) items.forEach(function(i) { next[i.id] = true })
    trashChecked = next
  }

  function confirmTrash() {
    var ids = (trashItems || []).filter(function(i) { return root.trashChecked[i.id] === true })
                                .map(function(i) { return i.id })
    if (ids.length === 0 || trasher.running) return
    trasher.start(python.concat([sourceDir + "/bin/keepwell-run", "trash", trashSet], ids))
  }

  function cancelTrash() { if (!trasher.running) trashOpen = false }

  // Unclaimed: a new age or an ignored folder is saved, then listed again.
  function relistAfter(args) {
    if (settingsWriter.running || lister.running) return
    settingsWriter.start(python.concat([sourceDir + "/bin/keepwell-run", "unclaimed"], args))
  }
  function chooseDays(days) {
    if ([90, 180, 365, 730].indexOf(days) === -1 || days === trashDays) return
    trashDays = days
    relistAfter(["days", String(days)])
  }
  function ignoreItem(id) {
    if (!/^[A-Za-z0-9._@+ \/-]{1,200}$/.test(id)) return
    trashItems = (trashItems || []).filter(function(i) { return i.id !== id })
    relistAfter(["ignore", id])
  }
  BoundedProcess {
    id: settingsWriter
    maxBytes: 4096
    timeoutMs: 10000
    onFinished: {
      root.trashItems = null
      root.trashChecked = ({})
      lister.start(root.python.concat([root.sourceDir + "/bin/keepwell-run", "list", "unclaimed"]))
      root.check(false)
    }
  }

  BoundedProcess {
    id: lister
    maxBytes: 64 * 1024
    timeoutMs: 15000
    onFinished: function(ok, text) {
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      var valid = d && d.set === root.trashSet && Array.isArray(d.items) && d.items.length <= 60
        && d.items.every(function(i) {
          return i && typeof i.id === "string" && i.id.length <= 128 && typeof i.label === "string"
            && typeof i.path === "string" && typeof i.bytes === "number" && isFinite(i.bytes)
        })
      if (valid) {
        root.trashItems = d.items
        if (root.trashSet === "unclaimed" && [90, 180, 365, 730].indexOf(d.days) !== -1) {
          root.trashDays = d.days
          root.trashDayChoices = [90, 180, 365, 730]
        }
      } else root.trashFailed = true
    }
  }

  BoundedProcess {
    id: trasher
    maxBytes: 64 * 1024
    timeoutMs: 120000
    onFinished: function(ok, text) {
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      root.trashOpen = false
      if (!d || !Array.isArray(d.trashed) || !Array.isArray(d.failed)) {
        root.say("Something went wrong; check the Trash to see what moved.")
      } else {
        var bytes = (root.trashItems || []).filter(function(i) { return d.trashed.indexOf(i.id) !== -1 })
                                           .reduce(function(n, i) { return n + i.bytes }, 0)
        root.say(d.trashed.length ? "Moved " + d.trashed.length + " to Trash (" + Present.bytes(bytes)
                   + "). Empty the Trash to free the space." + (d.failed.length ? " " + d.failed.length + " couldn't be moved." : "")
                 : "Nothing could be moved.")
      }
      root.check(false)
    }
  }

  // ---------------- background checks ----------------
  // The sheet edits a copy; Save writes it through keepwell-run, which
  // writes the timer and enables it (no root, no terminal).
  property bool schedOpen: false
  property bool schedLoading: true
  property bool schedEnabled: false
  property var schedDays: []
  property string schedTime: "10:00"
  property var schedParts: []

  function openSchedule() {
    if (schedReader.running) return
    schedLoading = true
    schedOpen = true
    schedReader.start(python.concat([sourceDir + "/bin/keepwell-run", "schedule", "get"]))
  }

  BoundedProcess {
    id: schedReader
    maxBytes: 8192
    timeoutMs: 10000
    onFinished: function(ok, text) {
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      if (!d || !Array.isArray(d.days) || typeof d.time !== "string" || !Array.isArray(d.parts)) {
        root.schedOpen = false
        root.say("Couldn't read the background check settings.")
        return
      }
      root.schedEnabled = d.enabled === true
      root.schedDays = d.days.filter(function(x) { return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].indexOf(x) !== -1 })
      root.schedTime = /^([01]\d|2[0-3]):[0-5]\d$/.test(d.time) ? d.time : "10:00"
      root.schedParts = d.parts.filter(function(x) { return ["vulns", "cleanup", "scan-downloads", "scan-home"].indexOf(x) !== -1 })
      root.schedLoading = false
    }
  }

  function toggleSchedDay(day) {
    var all = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    var next = schedDays.indexOf(day) === -1 ? schedDays.concat([day]) : schedDays.filter(function(x) { return x !== day })
    schedDays = all.filter(function(x) { return next.indexOf(x) !== -1 })
  }
  function everySchedDay() {
    schedDays = schedDays.length === 7 ? [] : ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
  }
  function stepSchedTime(minutes) {
    var hm = schedTime.split(":")
    var total = (Number(hm[0]) * 60 + Number(hm[1]) + minutes + 1440) % 1440
    var pad = function(n) { return (n < 10 ? "0" : "") + n }
    schedTime = pad(Math.floor(total / 60)) + ":" + pad(total % 60)
  }
  function toggleSchedPart(part) {
    var next = schedParts.indexOf(part) === -1 ? schedParts.concat([part]) : schedParts.filter(function(x) { return x !== part })
    // One virus scan target at a time.
    if (part === "scan-home" && next.indexOf("scan-home") !== -1) next = next.filter(function(x) { return x !== "scan-downloads" })
    if (part === "scan-downloads" && next.indexOf("scan-downloads") !== -1) next = next.filter(function(x) { return x !== "scan-home" })
    schedParts = next
  }
  function chooseScanTarget(target) {
    var on = schedParts.indexOf("scan-downloads") !== -1 || schedParts.indexOf("scan-home") !== -1
    if (!on) return
    schedParts = schedParts.filter(function(x) { return x.indexOf("scan-") !== 0 }).concat(["scan-" + target])
  }
  function saveSchedule() {
    if (!schedDays.length || !schedParts.length) return
    scheduleRun(["set", schedDays.join(","), schedTime, schedParts.join(",")], "")
  }
  function scheduleRun(args, message) {
    if (schedWriter.running) return
    schedMessage = message
    schedWriter.start(python.concat([sourceDir + "/bin/keepwell-run", "schedule"], args))
  }
  property string schedMessage: ""

  BoundedProcess {
    id: schedWriter
    maxBytes: 8192
    timeoutMs: 30000
    onFinished: function(ok, text) {
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      if (d && d.saved === true) {
        root.schedOpen = false
        root.say(root.schedMessage || ("Background checks saved." + (typeof d.next === "string" ? " Next: " + d.next.replace(/:00 [A-Z]{2,5}$/, "") + "." : "")))
      } else {
        root.say(d && d.reason === "exists" ? "A keepwell-report unit that Keepwell didn't write is in the way; nothing was changed."
                 : "Couldn't save the background checks.")
      }
      root.check(false)
    }
  }

  // ---------------- the terminal round trip ----------------
  // { title, act, checkId, address, network }
  //
  // The terminal is found by its title once, then followed by its Hyprland
  // window address, which nothing inside it can change. That address and
  // the check it belongs to are written to Keepwell's state, so a shell
  // that restarts meanwhile (omarchy update does) picks the round trip up
  // again and still comes back to the right place.
  property var terminal: null
  readonly property var networkActs: ["install-arch-audit", "update"]

  function acceptConfirm() {
    if (!confirmPlan || !pendingAct || terminal || confirmPlan.steps.length === 0) return
    var title = "Keepwell · " + confirmPlan.title
    var argv = ["/usr/bin/uwsm-app", "--", "/usr/bin/xdg-terminal-exec",
                "--app-id=org.omarchy.terminal", "--title=" + title, "-e"]
      .concat(python, [sourceDir + "/bin/keepwell-run", "apply", pendingAct.act], runFlags())
    terminal = { title: title, act: pendingAct.act, checkId: pendingAct.checkId, address: "",
                 network: networkActs.indexOf(pendingAct.act) !== -1 }
    resumed = false
    savePending("-")
    confirmOpen = false
    pendingAct = null
    say("")
    hide()
    Quickshell.execDetached(argv)
    neverOpened.interval = 20000
    neverOpened.restart()
  }

  // Writes to the pending note run one at a time, in order; the last one
  // asked for always lands (a busy writer would otherwise drop it).
  property var pendingQueue: []
  function writePending(args) {
    pendingQueue = pendingQueue.concat([python.concat([sourceDir + "/bin/keepwell-run", "pending"], args)])
    if (!pendingWriter.running) pendingWriter.start(pendingQueue.shift())
  }

  function savePending(address) {
    if (!terminal) return
    writePending(["set", address, terminal.checkId, terminal.act])
  }

  function addressOf(t) {
    var a = String(t && t.address || "").toLowerCase()
    if (a.indexOf("0x") !== 0) a = "0x" + a
    return /^0x[0-9a-f]{1,16}$/.test(a) ? a : ""
  }

  function trackTerminal() {
    if (!terminal) return
    var list = Hyprland.toplevels.values
    if (terminal.address === "") {
      for (var i = 0; i < list.length; i++) {
        var a = addressOf(list[i])
        if (list[i] && list[i].title === terminal.title && a !== "") {
          terminal.address = a
          neverOpened.stop()
          savePending(a)
          return
        }
      }
      return
    }
    for (var j = 0; j < list.length; j++) if (addressOf(list[j]) === terminal.address) return
    // Just after a restart the list may not have arrived yet.
    if (settling) return
    finishTerminal(true)
  }
  property bool settling: false

  function finishTerminal(opened) {
    var t = terminal
    terminal = null
    neverOpened.stop()
    writePending(["clear"])
    focusCheckId = t.checkId
    show(true)
    if (!opened) { say("The terminal didn't open, so nothing was run."); return }
    say("Back from the terminal — checking the result…")
    reportAfterCheck = { checkId: t.checkId, prefix: "Back from the terminal. " }
    check(t.network)
  }

  // After a shell restart: was Keepwell waiting on a terminal?
  function resumePending(text) {
    var d = null
    try { d = JSON.parse(text) } catch (e) { d = null }
    if (!d || typeof d.checkId !== "string" || typeof d.act !== "string" || typeof d.title !== "string") return
    resumed = true
    settling = true
    terminal = { title: d.title, act: d.act, checkId: d.checkId,
                 address: /^0x[0-9a-f]{1,16}$/.test(d.address) ? d.address : "",
                 network: networkActs.indexOf(d.act) !== -1 }
    // A shell that has just started doesn't know the windows that were
    // already open (or their titles) until it asks Hyprland; ask, and give
    // the answer a few seconds before deciding the terminal is gone.
    Hyprland.refreshToplevels()
    neverOpened.interval = 8000
    neverOpened.restart()
    resumeTimer.start()
  }

  BoundedProcess {
    id: pendingWriter
    maxBytes: 4096
    timeoutMs: 5000
    onFinished: if (root.pendingQueue.length > 0) {
      var next = root.pendingQueue.slice()
      var argv = next.shift()
      root.pendingQueue = next
      start(argv)
    }
  }
  BoundedProcess {
    id: pendingReader
    maxBytes: 4096
    timeoutMs: 5000
    onFinished: function(ok, text) { if (ok) root.resumePending(text) }
  }
  Timer {
    id: resumeTimer
    interval: 1500
    repeat: true
    property int tries: 0
    onTriggered: {
      tries++
      if (root.terminal && root.terminal.address === "" && tries < 5) Hyprland.refreshToplevels()
      root.trackTerminal()
      if (tries >= 2) root.settling = false
      if (!root.terminal || tries >= 5) { stop(); tries = 0; root.settling = false; root.trackTerminal() }
    }
  }

  Connections {
    target: Hyprland.toplevels
    function onValuesChanged() { root.trackTerminal() }
  }
  // Belt and braces for a missed change signal.
  Timer {
    interval: 1000
    repeat: true
    running: root.terminal !== null
    onTriggered: root.trackTerminal()
  }
  Timer {
    id: neverOpened
    interval: 20000
    // A resumed round trip whose terminal closed while the shell was down
    // ends here as finished; a fresh one that never opened says so.
    onTriggered: if (root.terminal && root.terminal.address === "") root.finishTerminal(root.resumed)
  }
  property bool resumed: false

  // ---------------- background jobs ----------------
  // Scans run as user services (see keepwell-run); these start and stop
  // them, and the folder picker steps aside like a terminal does.
  property bool picking: false

  function startJob(args, started) {
    if (jobber.running) return
    jobMessage = started
    jobber.start(python.concat([sourceDir + "/bin/keepwell-run"], args))
  }
  property string jobMessage: ""

  BoundedProcess {
    id: jobber
    maxBytes: 4096
    timeoutMs: 30000
    onFinished: function(ok, text) {
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      if (d && d.started === false)
        root.say(d.reason === "running" ? "A scan is already running." : d.reason === "folder"
                 ? "That folder can't be scanned." : "Couldn't start the scan.")
      else if (!d) root.say("Something went wrong starting that.")
      else root.say(root.jobMessage)
      root.check(false)
    }
  }

  BoundedProcess {
    id: picker
    maxBytes: 8192
    timeoutMs: 600000
    onFinished: function(ok, text) {
      root.picking = false
      var d = null
      if (ok) { try { d = JSON.parse(text) } catch (e) { d = null } }
      root.show(true)
      if (d && typeof d.folder === "string" && d.folder.indexOf("/") === 0 && d.folder.length < 4096)
        root.startJob(["leaks", d.folder], "Scanning for secrets in the background — you'll get a notification when it's done.")
      else root.say("No folder chosen.")
    }
  }

  // While a scan runs and the window is open, its state is re-read every
  // 15 seconds so the window shows it ending; nothing polls otherwise.
  readonly property bool scanning: !!(doc && doc.probes && ((doc.probes.antivirus && doc.probes.antivirus.scanning)
                                     || (doc.probes.tools && doc.probes.tools.leaksScanning)))
  Timer {
    interval: 15000
    repeat: true
    running: root.opened && root.scanning
    onTriggered: if (!checker.running) root.check(false)
  }

  // ---------------- window lifecycle ----------------
  // Loaded on first open, so a window nobody has opened costs the shell
  // nothing.
  readonly property bool opened: windowLoader.item ? windowLoader.item.shown : false

  function show(skipStaleCheck) {
    now = Date.now() / 1000
    // Stale, or showing a scan that may have ended since: look again.
    if (!skipStaleCheck && !checker.running && (!doc || now - doc.at > 60 || scanning)) check(false)
    windowLoader.active = true
    if (windowLoader.item) {
      if (focusCheckId !== "") { windowLoader.item.focusCheck(focusCheckId); focusCheckId = "" }
      windowLoader.item.show()
    }
  }
  function hide() { if (windowLoader.item) windowLoader.item.hide() }
  function open() { show() }
  function close() { hide() }
  function toggle() { if (opened) hide(); else show() }

  // Parameterless on purpose: IPC can open and close the window, and ask
  // for a read-only re-check (a finished scan does, so its result is
  // already showing when you open Keepwell). Nothing more.
  IpcHandler {
    target: "keepwell"
    function refresh(): void { root.check(false) }
    function show(): void { root.show() }
    function hide(): void { root.hide() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
  }

  Loader {
    id: windowLoader
    active: false
    asynchronous: true
    source: Qt.resolvedUrl("Window.qml")
    onLoaded: {
      item.sections = Qt.binding(function() { return root.sections })
      item.checkedAt = Qt.binding(function() { return root.checkedAt })
      item.checking = Qt.binding(function() { return root.checking })
      item.schedule = Qt.binding(function() { return Present.schedule(root.doc, root.now) })
      item.scheduleRequested.connect(root.openSchedule)
      item.scheduleOffRequested.connect(function() { root.scheduleRun(["off"], "Background checks are off.") })
      item.confirmOpen = Qt.binding(function() { return root.confirmOpen })
      item.confirmPlan = Qt.binding(function() { return root.confirmPlan })
      item.confirmFailed = Qt.binding(function() { return root.confirmFailed })
      item.confirmSnapshot = Qt.binding(function() { return root.confirmSnapshot })
      item.confirmContext = Qt.binding(function() { return root.confirmContext })
      item.checkRequested.connect(function(network) { root.check(network) })
      item.actionRequested.connect(function(action, checkId, context) { root.requestAction(action, checkId, context) })
      item.confirmAccepted.connect(root.acceptConfirm)
      item.confirmCanceled.connect(root.cancelConfirm)
      item.confirmSnapshotToggled.connect(root.toggleSnapshot)
      item.confirmOptionToggled.connect(root.toggleOption)
      item.confirmAllToggled.connect(root.toggleAllOptions)
      item.trashAllToggled.connect(root.toggleAllTrash)
      item.trashOpen = Qt.binding(function() { return root.trashOpen })
      item.trashTitle = Qt.binding(function() { return root.trashTitle })
      item.trashContext = Qt.binding(function() { return root.trashContext })
      item.trashItems = Qt.binding(function() { return root.trashItems })
      item.trashFailed = Qt.binding(function() { return root.trashFailed })
      item.trashBusy = Qt.binding(function() { return trasher.running })
      item.trashChecked = Qt.binding(function() { return root.trashChecked })
      item.trashDays = Qt.binding(function() { return root.trashDays })
      item.trashDayChoices = Qt.binding(function() { return root.trashDayChoices })
      item.trashDaysChosen.connect(root.chooseDays)
      item.trashIgnored.connect(root.ignoreItem)
      item.schedOpen = Qt.binding(function() { return root.schedOpen })
      item.schedLoading = Qt.binding(function() { return root.schedLoading })
      item.schedBusy = Qt.binding(function() { return schedWriter.running })
      item.schedEnabled = Qt.binding(function() { return root.schedEnabled })
      item.schedDays = Qt.binding(function() { return root.schedDays })
      item.schedTime = Qt.binding(function() { return root.schedTime })
      item.schedParts = Qt.binding(function() { return root.schedParts })
      item.schedDayToggled.connect(root.toggleSchedDay)
      item.schedEveryDay.connect(root.everySchedDay)
      item.schedTimeStepped.connect(root.stepSchedTime)
      item.schedPartToggled.connect(root.toggleSchedPart)
      item.schedScanTargetChosen.connect(root.chooseScanTarget)
      item.schedSaved.connect(root.saveSchedule)
      item.schedTurnedOff.connect(function() { root.scheduleRun(["off"], "Background checks are off.") })
      item.schedCanceled.connect(function() { root.schedOpen = false })
      item.trashToggled.connect(root.toggleTrashItem)
      item.trashAccepted.connect(root.confirmTrash)
      item.trashCanceled.connect(root.cancelTrash)
      if (root.focusCheckId !== "") { item.focusCheck(root.focusCheckId); root.focusCheckId = "" }
      item.show()
    }
  }
}

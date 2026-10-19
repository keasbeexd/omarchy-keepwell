import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
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

  Component.onCompleted: check(false)

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
    if (action.trashSet) { openTrash(action.trashSet, action.label, context); return }
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

  function openTrash(set, label, context) {
    if (lister.running || trasher.running) return
    trashSet = set
    trashTitle = set === "cache" ? "Clear app caches" : "Clear activity traces"
    trashContext = context
    trashItems = null
    trashFailed = false
    trashChecked = ({})
    trashOpen = true
    lister.start(python.concat([sourceDir + "/bin/keepwell-run", "list", set]))
  }

  function toggleTrashItem(id) {
    var next = {}
    for (var k in trashChecked) next[k] = trashChecked[k]
    next[id] = !next[id]
    trashChecked = next
  }

  function confirmTrash() {
    var ids = (trashItems || []).filter(function(i) { return root.trashChecked[i.id] === true })
                                .map(function(i) { return i.id })
    if (ids.length === 0 || trasher.running) return
    trasher.start(python.concat([sourceDir + "/bin/keepwell-run", "trash", trashSet], ids))
  }

  function cancelTrash() { if (!trasher.running) trashOpen = false }

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
      if (valid) root.trashItems = d.items
      else root.trashFailed = true
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

  // ---------------- the terminal round trip ----------------
  // { title, act, checkId, toplevel, network }
  property var terminal: null

  function acceptConfirm() {
    if (!confirmPlan || !pendingAct || terminal || confirmPlan.steps.length === 0) return
    var title = "Keepwell · " + confirmPlan.title
    var argv = ["/usr/bin/uwsm-app", "--", "/usr/bin/xdg-terminal-exec",
                "--app-id=org.omarchy.terminal", "--title=" + title, "-e"]
      .concat(python, [sourceDir + "/bin/keepwell-run", "apply", pendingAct.act], runFlags())
    terminal = { title: title, act: pendingAct.act, checkId: pendingAct.checkId, toplevel: null,
                 network: pendingAct.act === "install-arch-audit" || pendingAct.act === "update" }
    confirmOpen = false
    pendingAct = null
    say("")
    hide()
    Quickshell.execDetached(argv)
    neverOpened.restart()
  }

  // The window is matched by its title once, then followed as an object, so
  // a program that renames its terminal can't make it look closed.
  function trackTerminal() {
    if (!terminal) return
    var list = ToplevelManager.toplevels.values
    if (!terminal.toplevel) {
      for (var i = 0; i < list.length; i++) {
        if (list[i] && list[i].title === terminal.title) {
          terminal.toplevel = list[i]
          neverOpened.stop()
          return
        }
      }
      return
    }
    if (list.indexOf(terminal.toplevel) === -1) finishTerminal(true)
  }

  function finishTerminal(opened) {
    var t = terminal
    terminal = null
    neverOpened.stop()
    show(true)
    if (!opened) { say("The terminal didn't open, so nothing was run."); return }
    say("Back from the terminal — checking the result…")
    reportAfterCheck = { checkId: t.checkId, prefix: "Back from the terminal. " }
    check(t.network)
  }

  Connections {
    target: ToplevelManager.toplevels
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
    onTriggered: if (root.terminal && !root.terminal.toplevel) root.finishTerminal(false)
  }

  // ---------------- window lifecycle ----------------
  // Loaded on first open, so a window nobody has opened costs the shell
  // nothing.
  readonly property bool opened: windowLoader.item ? windowLoader.item.shown : false

  function show(skipStaleCheck) {
    now = Date.now() / 1000
    if (!skipStaleCheck && !checker.running && (!doc || now - doc.at > 60)) check(false)
    windowLoader.active = true
    if (windowLoader.item) windowLoader.item.show()
  }
  function hide() { if (windowLoader.item) windowLoader.item.hide() }
  function open() { show() }
  function close() { hide() }
  function toggle() { if (opened) hide(); else show() }

  // Parameterless on purpose: IPC can open and close the window, nothing
  // more.
  IpcHandler {
    target: "keepwell"
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
      item.trashOpen = Qt.binding(function() { return root.trashOpen })
      item.trashTitle = Qt.binding(function() { return root.trashTitle })
      item.trashContext = Qt.binding(function() { return root.trashContext })
      item.trashItems = Qt.binding(function() { return root.trashItems })
      item.trashFailed = Qt.binding(function() { return root.trashFailed })
      item.trashBusy = Qt.binding(function() { return trasher.running })
      item.trashChecked = Qt.binding(function() { return root.trashChecked })
      item.trashToggled.connect(root.toggleTrashItem)
      item.trashAccepted.connect(root.confirmTrash)
      item.trashCanceled.connect(root.cancelTrash)
      item.show()
    }
  }
}

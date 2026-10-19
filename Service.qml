import QtQuick
import Quickshell
import Quickshell.Io
import "model/Present.js" as Present
import "model/Status.js" as Status

// The plugin's always-on half. It owns the check results, the window and the
// IPC route that opens it, so the window works with or without the bar icon:
// `omarchy-shell keepwell toggle` from a keybinding reaches it either way.
//
// When checks run:
//   - once when the shell starts, so the bar icon means something;
//   - when the window opens, if the last result is over a minute old;
//   - when you press "Check again".
// All of these are local and read-only. arch-audit, which downloads the Arch
// security tracker data, runs only when you ask for it ("Check now" on that
// check, or "Check again"). Nothing repeats on a timer.
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

  // ---------------- results ----------------
  property var doc: null
  property bool checking: proc.running
  property bool failed: false
  // Re-reads the clock for "checked 2 min ago" while the window is open.
  property real now: Date.now() / 1000

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

  // ---------------- running the helper ----------------
  readonly property int maxBytes: 128 * 1024
  property string buf: ""
  property bool overflow: false
  property bool queuedNetwork: false
  property bool queued: false
  property bool runningNetwork: false

  function check(network) {
    if (sourceDir === "") return
    if (proc.running) {
      // One run at a time; a request made meanwhile runs right after.
      queued = true
      queuedNetwork = queuedNetwork || network
      return
    }
    buf = ""
    overflow = false
    runningNetwork = network
    var argv = ["/usr/bin/python3", "-I", "-S", sourceDir + "/bin/keepwell-check"]
    if (network) argv.push("--network")
    proc.command = argv
    proc.running = true
    deadline.restart()
  }

  function accept(text) {
    var parsed
    try { parsed = JSON.parse(text) } catch (e) { return false }
    if (!parsed || parsed.v !== 1 || typeof parsed.at !== "number" || !parsed.probes
        || typeof parsed.probes !== "object") return false
    // A local re-check keeps the last arch-audit result rather than forgetting
    // it: the tracker was only asked when you asked.
    if (!parsed.network && doc && doc.network && doc.probes && doc.probes.audit) {
      parsed.probes.audit = doc.probes.audit
      parsed.network = true
    }
    doc = parsed
    now = Date.now() / 1000
    return true
  }

  Process {
    id: proc
    stdout: SplitParser {
      // Raw chunks with a byte budget, so nothing is buffered past the cap
      // waiting for a newline. The helper caps itself at 64 KiB as well.
      splitMarker: ""
      onRead: function(chunk) {
        if (root.overflow) return
        root.buf += chunk
        if (root.buf.length > root.maxBytes) {
          root.overflow = true
          root.buf = ""
          proc.signal(15)
          killTimer.restart()
        }
      }
    }
    onExited: function(code, status) {
      deadline.stop()
      killTimer.stop()
      root.failed = root.overflow || code !== 0 || !root.accept(root.buf)
      root.buf = ""
      if (root.queued) {
        var net = root.queuedNetwork
        root.queued = false
        root.queuedNetwork = false
        root.check(net)
      }
    }
  }

  // The helper keeps its own 25 s budget; this is the backstop.
  Timer {
    id: deadline
    interval: 40000
    onTriggered: if (proc.running) { proc.signal(15); killTimer.restart() }
  }
  Timer {
    id: killTimer
    interval: 2000
    onTriggered: if (proc.running) proc.signal(9)
  }

  Timer {
    interval: 30000
    repeat: true
    running: root.opened
    onTriggered: root.now = Date.now() / 1000
  }

  Component.onCompleted: check(false)
  Component.onDestruction: if (proc.running) proc.signal(15)

  // ---------------- window lifecycle ----------------
  // Loaded on first open, so a window nobody has opened costs the shell
  // nothing.
  readonly property bool opened: windowLoader.item ? windowLoader.item.shown : false

  function show() {
    now = Date.now() / 1000
    if (!proc.running && (!doc || now - doc.at > 60)) check(false)
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
      item.checkRequested.connect(function(network) { root.check(network) })
      item.show()
    }
  }
}

import QtQuick
import Quickshell.Io

// Runs one command (an argv array, never a shell string) and hands back its
// stdout, with a byte ceiling and a deadline. Overflow or overrun sends TERM,
// then KILL two seconds later, and reports failure. One run at a time.
Item {
  id: root

  property int maxBytes: 128 * 1024
  property int timeoutMs: 40000
  readonly property bool running: proc.running

  // ok: exited 0 within the limits. text: stdout ("" when not ok).
  signal finished(bool ok, string text)

  property string _buf: ""
  property bool _overflow: false

  function start(argv) {
    if (proc.running) return false
    _buf = ""
    _overflow = false
    proc.command = argv
    proc.running = true
    deadline.restart()
    return true
  }

  function stop() {
    if (!proc.running) return
    proc.signal(15)
    killTimer.restart()
  }

  Process {
    id: proc
    stdout: SplitParser {
      // Raw chunks with a byte budget: nothing is buffered past the cap
      // waiting for a newline.
      splitMarker: ""
      onRead: function(chunk) {
        if (root._overflow) return
        root._buf += chunk
        if (root._buf.length > root.maxBytes) {
          root._overflow = true
          root._buf = ""
          root.stop()
        }
      }
    }
    onExited: function(code, status) {
      deadline.stop()
      killTimer.stop()
      var ok = !root._overflow && code === 0
      var out = ok ? root._buf : ""
      root._buf = ""
      root.finished(ok, out)
    }
  }

  Timer {
    id: deadline
    interval: root.timeoutMs
    onTriggered: { root._overflow = true; root.stop() }
  }
  Timer {
    id: killTimer
    interval: 2000
    onTriggered: if (proc.running) proc.signal(9)
  }

  Component.onDestruction: if (proc.running) proc.signal(15)
}

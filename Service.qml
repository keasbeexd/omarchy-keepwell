import QtQuick
import Quickshell
import Quickshell.Io
import "model/SampleData.js" as SampleData
import "model/Status.js" as Status

// The plugin's always-on half. It owns the check results, the window and the
// IPC route that opens it, so the window works with or without the bar icon:
// `omarchy-shell keepwell toggle` from a keybinding reaches it either way.
//
// Nothing runs on load. In this preview build the results are SampleData;
// the real checks will be bounded helpers started on open or on "Check
// again", never in the background unless the user turns a timer on.
Scope {
  id: root

  property string omarchyPath: ""
  property var shell: null
  property var manifest: null

  readonly property bool preview: true
  readonly property var sections: SampleData.sections
  readonly property string checkedAt: "Sample data"

  // What the bar icon shows: the worst state across every section.
  readonly property var allChecks: {
    var all = []
    for (var i = 0; i < sections.length; i++) all = all.concat(sections[i].checks)
    return all
  }
  readonly property string worst: Status.worst(allChecks)
  readonly property string summary: Status.summary(allChecks)

  // ---------------- window lifecycle ----------------
  // Loaded on first open, so a window nobody has opened costs the shell
  // nothing.
  readonly property bool opened: windowLoader.item ? windowLoader.item.shown : false

  function show() {
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
      item.preview = Qt.binding(function() { return root.preview })
      item.show()
    }
  }
}

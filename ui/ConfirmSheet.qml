import QtQuick
import QtQuick.Layouts

// The confirm step before anything runs in a terminal: what it does, the
// exact commands (from keepwell-run's own plan, so they are the commands that
// run), an optional snapshot first, and where the password is typed.
Item {
  id: root

  property bool opened: false
  property var plan: null          // keepwell-run plan JSON, or null while loading
  property bool failed: false      // the plan couldn't be built
  property string context: ""      // "Security · Firewall"
  property bool snapshot: false

  signal confirmed()
  signal canceled()
  signal snapshotToggled()
  signal optionToggled(string id)

  readonly property bool ready: plan !== null && !failed
  readonly property var options: plan && Array.isArray(plan.options) ? plan.options : []
  readonly property bool hasSteps: ready && plan.steps.length > 0
  // Keyboard cursor over one flat list: each option, the snapshot box,
  // Cancel, Open terminal.
  readonly property int boxIndex: options.length
  readonly property int cancelIndex: options.length + 1
  readonly property int confirmIndex: options.length + 2
  property int cursor: confirmIndex
  readonly property bool anyRoot: {
    if (!plan) return false
    for (var i = 0; i < plan.steps.length; i++) if (plan.steps[i].root) return true
    return false
  }

  visible: opened
  // The cursor starts on "Open terminal" once the first plan (and so the
  // number of options) is known; later plans keep it where it is.
  property bool _placed: false
  onOpenedChanged: if (opened) _placed = false
  onPlanChanged: {
    if (!plan) return
    // From the plan itself: the bindings that count options may not have
    // caught up yet when this handler runs.
    var last = (Array.isArray(plan.options) ? plan.options.length : 0) + 2
    if (!_placed) { cursor = last; _placed = true }
    else if (cursor > last) cursor = last
  }

  Rectangle {
    anchors.fill: parent
    color: Tokens.scrim
    // Clicks outside the sheet cancel; clicks on it stay on it.
    MouseArea { anchors.fill: parent; onClicked: root.canceled() }
  }

  Rectangle {
    id: sheet
    anchors.centerIn: parent
    width: Math.min(Tokens.sp(620), parent.width - Tokens.sp(48))
    height: Math.min(layout.implicitHeight + Tokens.sp(48), parent.height - Tokens.sp(48))
    color: Tokens.bg
    radius: Tokens.radius
    border.width: Tokens.border
    border.color: Tokens.accent

    MouseArea { anchors.fill: parent }

    // The content scrolls if it must; the buttons stay put.
    ColumnLayout {
      id: layout
      anchors.fill: parent
      anchors.margins: Tokens.sp(24)
      spacing: Tokens.sp(14)

      Flickable {
        id: flick
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: body.implicitHeight
        Layout.minimumHeight: Math.min(body.implicitHeight, Tokens.sp(120))
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollHint { flick: flick }

        ColumnLayout {
          id: body
          width: flick.width - Tokens.sp(8)
          spacing: Tokens.sp(14)

          ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.sp(4)
            KText {
              text: root.context.toUpperCase()
              font.pixelSize: Tokens.caption
              font.letterSpacing: 0.6
              color: Tokens.fg3
            }
            KText {
              Layout.fillWidth: true
              text: root.plan ? root.plan.title + "?" : root.failed ? "Couldn't prepare this action" : "Preparing…"
              font.pixelSize: Tokens.heading
              font.bold: true
              wrapMode: Text.WordWrap
            }
            KText {
              Layout.fillWidth: true
              visible: text !== ""
              text: root.plan ? root.plan.summary : root.failed ? "Nothing was run. Try again in a moment." : ""
              color: Tokens.fg2
              wrapMode: Text.WordWrap
            }
          }

          ColumnLayout {
            visible: root.options.length > 0
            Layout.fillWidth: true
            spacing: Tokens.sp(10)
            Repeater {
              model: root.options
              delegate: ColumnLayout {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: Tokens.sp(2)
                CheckBox {
                  Layout.fillWidth: true
                  label: modelData.label
                  checked: modelData.checked
                  hasCursor: root.cursor === index
                  onToggled: root.optionToggled(modelData.id)
                }
                KText {
                  Layout.fillWidth: true
                  Layout.leftMargin: Tokens.sp(26)
                  text: modelData.hint
                  font.pixelSize: Tokens.small
                  color: Tokens.fg3
                  wrapMode: Text.WordWrap
                }
              }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }
          }

          CheckBox {
            visible: root.ready && root.plan.snapshotOffered
            Layout.fillWidth: true
            label: "Take a snapshot first"
            hint: "(a restore point you can boot into)"
            checked: root.snapshot
            hasCursor: root.cursor === root.boxIndex
            onToggled: root.snapshotToggled()
          }

          KText {
            visible: root.ready && !root.hasSteps
            Layout.fillWidth: true
            text: root.options.length > 0 ? "Tick something above to see the commands." : "There is nothing to do right now."
            color: Tokens.fg2
            wrapMode: Text.WordWrap
          }

          ColumnLayout {
            visible: root.hasSteps
            Layout.fillWidth: true
            spacing: Tokens.sp(6)
            KText {
              text: "These exact commands will run in a terminal:"
              font.pixelSize: Tokens.small
              color: Tokens.fg2
            }
            Rectangle {
              Layout.fillWidth: true
              implicitHeight: cmds.implicitHeight + Tokens.sp(24)
              radius: Tokens.radius
              color: Tokens.fill2
              border.width: 1
              border.color: Tokens.line
              Column {
                id: cmds
                x: Tokens.sp(14)
                y: Tokens.sp(12)
                width: parent.width - Tokens.sp(28)
                spacing: Tokens.sp(8)
                Repeater {
                  model: root.plan ? root.plan.steps : []
                  delegate: Column {
                    required property var modelData
                    required property int index
                    width: cmds.width
                    spacing: Tokens.sp(2)
                    KText {
                      width: parent.width
                      text: (index + 1) + ". " + modelData.say
                      font.pixelSize: Tokens.small
                      color: Tokens.fg3
                      wrapMode: Text.WordWrap
                    }
                    KText {
                      width: parent.width
                      text: "$ " + modelData.cmd
                      font.pixelSize: Tokens.small
                      wrapMode: Text.WrapAnywhere
                    }
                  }
                }
              }
            }
            KText {
              Layout.fillWidth: true
              visible: root.anyRoot
              text: "You type your password in the terminal. Keepwell never sees it."
              font.pixelSize: Tokens.small
              color: Tokens.fg3
              wrapMode: Text.WordWrap
            }
            KText {
              Layout.fillWidth: true
              text: "Keepwell steps aside while the terminal is open and comes back when you close it."
              font.pixelSize: Tokens.small
              color: Tokens.fg3
              wrapMode: Text.WordWrap
            }
          }

        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        Item { Layout.fillWidth: true }
        ActionButton {
          label: "Cancel"
          hasCursor: root.cursor === root.cancelIndex
          onActivated: root.canceled()
        }
        ActionButton {
          label: "Open terminal"
          primary: true
          elevated: true
          enabledAction: root.hasSteps
          hasCursor: root.cursor === root.confirmIndex
          onActivated: root.confirmed()
        }
      }
    }
  }

  // Keys while open, forwarded from the window's key handler.
  function activate(i) {
    if (i < root.options.length) root.optionToggled(root.options[i].id)
    else if (i === root.boxIndex) root.snapshotToggled()
    else if (i === root.cancelIndex) root.canceled()
    else if (root.hasSteps) root.confirmed()
  }

  function handleKey(event) {
    // The snapshot box is skipped when this action doesn't offer one.
    function step(d) {
      var next = root.cursor + d
      if (next === root.boxIndex && !(root.ready && root.plan.snapshotOffered)) next += d
      return Math.max(0, Math.min(root.confirmIndex, next))
    }
    if (event.key === Qt.Key_Escape) root.canceled()
    else if (event.key === Qt.Key_Up || event.key === Qt.Key_Left || event.key === Qt.Key_Backtab
             || event.key === Qt.Key_K || event.key === Qt.Key_H) root.cursor = step(-1)
    else if (event.key === Qt.Key_Down || event.key === Qt.Key_Right || event.key === Qt.Key_Tab
             || event.key === Qt.Key_J || event.key === Qt.Key_L) root.cursor = step(1)
    else if (event.key === Qt.Key_Space && root.cursor <= root.boxIndex) root.activate(root.cursor)
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) root.activate(root.cursor)
    else return false
    return true
  }
}

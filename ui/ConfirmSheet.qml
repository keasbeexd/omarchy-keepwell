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
  // Keyboard cursor: 0 snapshot box, 1 Cancel, 2 Open terminal.
  property int cursor: 2

  signal confirmed()
  signal canceled()
  signal snapshotToggled()

  readonly property bool ready: plan !== null && !failed
  readonly property bool anyRoot: {
    if (!plan) return false
    for (var i = 0; i < plan.steps.length; i++) if (plan.steps[i].root) return true
    return false
  }

  visible: opened
  onOpenedChanged: if (opened) cursor = 2

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
    height: Math.min(body.implicitHeight + Tokens.sp(48), parent.height - Tokens.sp(48))
    color: Tokens.bg
    radius: Tokens.radius
    border.width: Tokens.border
    border.color: Tokens.accent

    MouseArea { anchors.fill: parent }

    Flickable {
      id: flick
      anchors.fill: parent
      anchors.margins: Tokens.sp(24)
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

        CheckBox {
          visible: root.ready && root.plan.snapshotOffered
          Layout.fillWidth: true
          label: "Take a snapshot first"
          hint: "(a restore point you can boot into)"
          checked: root.snapshot
          hasCursor: root.cursor === 0
          onToggled: root.snapshotToggled()
        }

        ColumnLayout {
          visible: root.ready
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

        RowLayout {
          Layout.fillWidth: true
          Layout.topMargin: Tokens.sp(4)
          spacing: Tokens.sp(8)
          Item { Layout.fillWidth: true }
          ActionButton {
            label: "Cancel"
            hasCursor: root.cursor === 1
            onActivated: root.canceled()
          }
          ActionButton {
            label: "Open terminal"
            primary: true
            elevated: true
            enabledAction: root.ready
            hasCursor: root.cursor === 2
            onActivated: root.confirmed()
          }
        }
      }
    }
  }

  // Keys while open, forwarded from the window's key handler.
  function handleKey(event) {
    var hasBox = root.ready && root.plan.snapshotOffered
    var first = hasBox ? 0 : 1
    if (event.key === Qt.Key_Escape) root.canceled()
    else if (event.key === Qt.Key_Left || event.key === Qt.Key_Up || event.key === Qt.Key_Backtab)
      root.cursor = Math.max(first, root.cursor - 1)
    else if (event.key === Qt.Key_Right || event.key === Qt.Key_Down || event.key === Qt.Key_Tab)
      root.cursor = Math.min(2, root.cursor + 1)
    else if (event.key === Qt.Key_Space && root.cursor === 0) root.snapshotToggled()
    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      if (root.cursor === 0) root.snapshotToggled()
      else if (root.cursor === 1) root.canceled()
      else if (root.ready) root.confirmed()
    } else return false
    return true
  }
}

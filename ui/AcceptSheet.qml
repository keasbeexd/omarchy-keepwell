import QtQuick
import QtQuick.Layouts

// Choose which of a check's findings you accept: ones you've looked at and
// decided to live with. Each row is ticked when it is accepted now; Save
// applies the ticks you changed. An accepted finding stays on the check,
// greyed out, and no longer raises it or sends a notification
// (bin/keepwell_accept.py); if it changes, it comes back.
//
// The same shape as the Trash sheet: heading and buttons stay put, only the
// list scrolls, and it follows the keyboard cursor.
Item {
  id: root

  property bool opened: false
  property string title: ""
  property string context: ""
  property var items: []            // [{ key, label, detail, sub, on }]
  property var checked: ({})        // key -> true while ticked
  property bool busy: false

  signal toggled(string key)
  signal allToggled()
  signal confirmed()
  signal canceled()

  readonly property var list: items || []
  readonly property var chosen: list.filter(function(i) { return root.checked[i.key] === true })
  readonly property bool allChecked: list.length > 0 && chosen.length === list.length
  readonly property int changes: list.filter(function(i) { return (root.checked[i.key] === true) !== (i.on === true) }).length

  // Keyboard cursor over one flat list: "Select all", each row, Cancel, Save.
  readonly property int allIndex: 0
  readonly property int firstRow: 1
  readonly property int cancelIndex: firstRow + list.length
  readonly property int confirmIndex: cancelIndex + 1
  property int cursor: 0
  // Where the list starts for the cursor: "Select all" when it shows.
  readonly property int topIndex: list.length > 1 ? allIndex : firstRow

  visible: opened
  onOpenedChanged: if (opened) { cursor = topIndex; flick.contentY = 0 }
  onCursorChanged: follow()

  function follow() {
    if (cursor < firstRow) { flick.contentY = 0; return }
    var row = rows.itemAt(cursor - firstRow)
    if (!row) return
    var top = row.y, bottom = row.y + row.height
    if (top < flick.contentY) flick.contentY = top
    else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height
  }

  // The next cursor stop, skipping "Select all" while it is hidden.
  function step(d) {
    var next = Math.max(0, Math.min(confirmIndex, cursor + d))
    if (next === allIndex && list.length <= 1) next = Math.max(0, Math.min(confirmIndex, next + d))
    return next
  }

  Rectangle {
    anchors.fill: parent
    color: Tokens.scrim
    MouseArea { anchors.fill: parent; onClicked: if (!root.busy) root.canceled() }
  }

  Rectangle {
    anchors.centerIn: parent
    width: Math.min(Tokens.sp(680), parent.width - Tokens.sp(48))
    height: Math.min(layout.implicitHeight + Tokens.sp(48), parent.height - Tokens.sp(48))
    color: Tokens.bg
    radius: Tokens.radius
    border.width: Tokens.border
    border.color: Tokens.accent

    MouseArea { anchors.fill: parent }

    ColumnLayout {
      id: layout
      anchors.fill: parent
      anchors.margins: Tokens.sp(24)
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
          text: root.title
          font.pixelSize: Tokens.heading
          font.bold: true
          wrapMode: Text.WordWrap
        }
        KText {
          Layout.fillWidth: true
          text: root.list.length === 0 ? "Nothing left to review."
            : "Tick the findings you've looked at and decided to live with. They stay on the check, greyed out, and no longer raise it or send a notification. Untick one to bring it back."
          color: Tokens.fg2
          wrapMode: Text.WordWrap
        }
      }

      CheckBox {
        visible: root.list.length > 1
        Layout.fillWidth: true
        label: "Select all"
        hint: "(" + root.list.length + ")"
        checked: root.allChecked
        hasCursor: root.cursor === root.allIndex
        onToggled: { root.cursor = root.allIndex; root.allToggled() }
      }

      Flickable {
        id: flick
        visible: root.list.length > 0
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: rowsCol.implicitHeight
        Layout.minimumHeight: Math.min(rowsCol.implicitHeight, Tokens.sp(120))
        contentHeight: rowsCol.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollHint { flick: flick }

        Column {
          id: rowsCol
          width: flick.width - (flick.contentHeight > flick.height + 1 ? Tokens.sp(8) : 0)
          Rectangle { width: parent.width; height: 1; color: Tokens.line }
          Repeater {
            id: rows
            model: root.list
            delegate: Item {
              required property var modelData
              required property int index
              width: rowsCol.width
              height: Math.max(box.implicitHeight, textCol.implicitHeight) + Tokens.sp(14)
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.cursor = root.firstRow + index; root.toggled(modelData.key) }
              }
              CheckBox {
                id: box
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                checked: root.checked[modelData.key] === true
                hasCursor: root.cursor === root.firstRow + index
                onToggled: { root.cursor = root.firstRow + index; root.toggled(modelData.key) }
              }
              Column {
                id: textCol
                anchors.left: box.right
                anchors.right: parent.right
                anchors.leftMargin: Tokens.sp(4)
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.sp(1)
                KText {
                  width: parent.width
                  text: modelData.label + (modelData.detail ? " · " + modelData.detail : "")
                  wrapMode: Text.WordWrap
                }
                KText {
                  visible: !!modelData.sub
                  width: parent.width
                  text: modelData.sub || ""
                  font.pixelSize: Tokens.small
                  color: Tokens.fg3
                  elide: Text.ElideMiddle
                }
              }
              Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Tokens.line }
            }
          }
        }
      }

      KText {
        Layout.fillWidth: true
        visible: root.list.length > 0
        text: "A finding comes back on its own when it changes: a new CVE or a released fix, a new advisory or version, the same secret in another commit."
        font.pixelSize: Tokens.small
        color: Tokens.fg3
        wrapMode: Text.WordWrap
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        KText {
          Layout.fillWidth: true
          text: root.list.length ? root.chosen.length + " of " + root.list.length + " accepted"
            + (root.changes ? " · " + root.changes + (root.changes === 1 ? " change" : " changes") : "") : ""
          color: Tokens.fg2
        }
        ActionButton {
          label: "Cancel"
          enabledAction: !root.busy
          hasCursor: root.cursor === root.cancelIndex
          onActivated: root.canceled()
        }
        ActionButton {
          label: root.busy ? "Saving…" : "Save"
          primary: true
          enabledAction: root.changes > 0 && !root.busy
          hasCursor: root.cursor === root.confirmIndex
          onActivated: root.confirmed()
        }
      }
    }
  }

  // Up/Down walk "Select all", the rows and then the buttons; Tab jumps to
  // the buttons and back; Space or Enter ticks a row or presses a button.
  function handleKey(event) {
    if (root.busy) return true
    var k = event.key
    var onRow = root.cursor >= root.firstRow && root.cursor < root.cancelIndex
    if (k === Qt.Key_Escape) root.canceled()
    else if (k === Qt.Key_Up || k === Qt.Key_K || k === Qt.Key_Left || k === Qt.Key_H) root.cursor = root.step(-1)
    else if (k === Qt.Key_Down || k === Qt.Key_J || k === Qt.Key_Right || k === Qt.Key_L) root.cursor = root.step(1)
    else if (k === Qt.Key_Tab) root.cursor = root.cursor < root.cancelIndex ? root.confirmIndex : root.topIndex
    else if (k === Qt.Key_Backtab) root.cursor = root.cursor < root.cancelIndex ? root.cancelIndex : root.topIndex
    else if (k === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) root.allToggled()
    else if (k === Qt.Key_Space || k === Qt.Key_Return || k === Qt.Key_Enter) {
      if (root.cursor === root.allIndex) root.allToggled()
      else if (onRow) root.toggled(root.list[root.cursor - root.firstRow].key)
      else if (root.cursor === root.cancelIndex) root.canceled()
      else if (root.cursor === root.confirmIndex && root.changes > 0) root.confirmed()
    } else return false
    return true
  }
}

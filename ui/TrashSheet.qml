import QtQuick
import QtQuick.Layouts
import "../model/Present.js" as Present

// Pick what goes to Trash: every item with its path and size, nothing ticked
// to begin with. Moving to Trash needs no password and can be undone from
// the Trash, so this sheet is the confirm step itself.
//
// The heading and the buttons stay put; only the list scrolls, and it
// follows the keyboard cursor.
Item {
  id: root

  property bool opened: false
  property string title: ""
  property string context: ""
  property var items: null          // [{ id, label, path, bytes, complete }] or null while loading
  property bool failed: false
  property bool busy: false
  property var checked: ({})        // id -> true

  signal toggled(string id)
  signal allToggled()
  signal confirmed()
  signal canceled()

  readonly property var list: items || []
  readonly property var chosen: list.filter(function(i) { return root.checked[i.id] === true })
  readonly property real chosenBytes: chosen.reduce(function(n, i) { return n + (i.bytes || 0) }, 0)
  readonly property bool allChecked: list.length > 0 && chosen.length === list.length
  // Keyboard cursor: 0 is "Select all", rows are 1…n, then the buttons.
  readonly property int cancelIndex: list.length + 1
  readonly property int confirmIndex: list.length + 2
  property int cursor: 0

  visible: opened
  onOpenedChanged: if (opened) { cursor = 0; flick.contentY = 0 }
  onCursorChanged: follow()

  function follow() {
    if (cursor === 0) { flick.contentY = 0; return }
    var row = rows.itemAt(cursor - 1)
    if (!row) return
    var top = row.y, bottom = row.y + row.height
    if (top < flick.contentY) flick.contentY = top
    else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height
  }

  Rectangle {
    anchors.fill: parent
    color: Tokens.scrim
    MouseArea { anchors.fill: parent; onClicked: if (!root.busy) root.canceled() }
  }

  Rectangle {
    anchors.centerIn: parent
    width: Math.min(Tokens.sp(640), parent.width - Tokens.sp(48))
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
          text: root.failed ? "Couldn't list these right now. Nothing was moved."
            : root.items === null ? "Measuring…"
            : root.list.length === 0 ? "There is nothing here to clear."
            : "Tick what to move to Trash. Apps rebuild their caches when they need them, which can make them a little slower the first time."
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
        hasCursor: root.cursor === 0
        onToggled: { root.cursor = 0; root.allToggled() }
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
              height: Math.max(box.implicitHeight, pathText.implicitHeight + labelText.implicitHeight) + Tokens.sp(14)
              CheckBox {
                id: box
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                checked: root.checked[modelData.id] === true
                hasCursor: root.cursor === index + 1
                onToggled: root.toggled(modelData.id)
              }
              Column {
                anchors.left: box.right
                anchors.right: size.left
                anchors.leftMargin: Tokens.sp(4)
                anchors.rightMargin: Tokens.sp(12)
                anchors.verticalCenter: parent.verticalCenter
                KText { id: labelText; width: parent.width; text: modelData.label; elide: Text.ElideRight }
                KText {
                  id: pathText
                  width: parent.width
                  text: modelData.path
                  font.pixelSize: Tokens.small
                  color: Tokens.fg3
                  elide: Text.ElideMiddle
                }
              }
              KText {
                id: size
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                text: Present.bytes(modelData.bytes) + (modelData.complete ? "" : "+")
                color: Tokens.fg2
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.cursor = index + 1; root.toggled(modelData.id) }
              }
              Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Tokens.line }
            }
          }
        }
      }

      KText {
        Layout.fillWidth: true
        visible: root.list.length > 0
        text: "Moved items stay in the Trash, where you can restore them. Their space is freed when you empty the Trash."
        font.pixelSize: Tokens.small
        color: Tokens.fg3
        wrapMode: Text.WordWrap
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        KText {
          Layout.fillWidth: true
          text: root.chosen.length > 0 ? root.chosen.length + " selected · " + Present.bytes(root.chosenBytes) : ""
          color: Tokens.fg2
        }
        ActionButton {
          label: "Cancel"
          enabledAction: !root.busy
          hasCursor: root.cursor === root.cancelIndex
          onActivated: root.canceled()
        }
        ActionButton {
          label: root.busy ? "Moving…" : "Move " + (root.chosen.length || "") + " to Trash"
          primary: true
          trash: true
          enabledAction: root.chosen.length > 0 && !root.busy
          hasCursor: root.cursor === root.confirmIndex
          onActivated: root.confirmed()
        }
      }
    }
  }

  // Up/Down walk the rows and then the buttons; Tab jumps straight to the
  // buttons and back, so a long list doesn't have to be walked to reach them.
  function handleKey(event) {
    if (root.busy) return true
    var k = event.key
    if (k === Qt.Key_Escape) root.canceled()
    else if (k === Qt.Key_Up || k === Qt.Key_K || k === Qt.Key_Left || k === Qt.Key_H)
      root.cursor = Math.max(0, root.cursor - 1)
    else if (k === Qt.Key_Down || k === Qt.Key_J || k === Qt.Key_Right || k === Qt.Key_L)
      root.cursor = Math.min(root.confirmIndex, root.cursor + 1)
    else if (k === Qt.Key_Tab) root.cursor = root.cursor < root.cancelIndex ? root.confirmIndex : 0
    else if (k === Qt.Key_Backtab) root.cursor = root.cursor < root.cancelIndex ? root.cancelIndex : 0
    else if (k === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) root.allToggled()
    else if (k === Qt.Key_Space || k === Qt.Key_Return || k === Qt.Key_Enter) {
      if (root.cursor === 0) root.allToggled()
      else if (root.cursor <= root.list.length) root.toggled(root.list[root.cursor - 1].id)
      else if (root.cursor === root.cancelIndex) root.canceled()
      else if (root.chosen.length > 0) root.confirmed()
    } else return false
    return true
  }
}

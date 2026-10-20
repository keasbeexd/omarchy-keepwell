import QtQuick
import QtQuick.Layouts
import "../model/Present.js" as Present

// Pick what goes to Trash: every item with its path and size, nothing ticked
// to begin with. Moving to Trash needs no password and can be undone from
// the Trash, so this sheet is the confirm step itself.
//
// The heading and the buttons stay put; only the list scrolls, and it
// follows the keyboard cursor. For unclaimed folders the sheet also shows
// how long each has been untouched, an age choice, and "Ignore" per row; for
// files the virus scan flagged, "Not a threat" per row.
Item {
  id: root

  property bool opened: false
  property string title: ""
  property string set: ""
  property string context: ""
  property var items: null          // [{ id, label, path, bytes, complete, days? }] or null while loading
  property bool failed: false
  property bool busy: false
  property var checked: ({})        // id -> true
  property int days: 0              // unclaimed: the age chosen
  property var dayChoices: []       // unclaimed: the ages offered

  signal toggled(string id)
  signal allToggled()
  signal confirmed()
  signal canceled()
  signal daysChosen(int days)
  signal ignored(string id)

  readonly property var list: items || []
  readonly property bool unclaimed: dayChoices.length > 0
  readonly property bool virus: set === "virus"
  readonly property bool canIgnore: unclaimed || virus
  readonly property var chosen: list.filter(function(i) { return root.checked[i.id] === true })
  readonly property real chosenBytes: chosen.reduce(function(n, i) { return n + (i.bytes || 0) }, 0)
  readonly property bool allChecked: list.length > 0 && chosen.length === list.length

  // Keyboard cursor over one flat list: the age choice (unclaimed only),
  // "Select all", each row, Cancel, Move.
  readonly property int ageIndex: unclaimed ? 0 : -1
  readonly property int allIndex: unclaimed ? 1 : 0
  readonly property int firstRow: allIndex + 1
  readonly property int cancelIndex: firstRow + list.length
  readonly property int confirmIndex: cancelIndex + 1
  property int cursor: 0

  visible: opened
  onOpenedChanged: if (opened) { cursor = 0; flick.contentY = 0 }
  onCursorChanged: follow()

  function follow() {
    if (cursor < firstRow) { flick.contentY = 0; return }
    var row = rows.itemAt(cursor - firstRow)
    if (!row) return
    var top = row.y, bottom = row.y + row.height
    if (top < flick.contentY) flick.contentY = top
    else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height
  }

  function ageText(d) {
    if (d >= 730) return Math.floor(d / 365) + " years"
    if (d >= 365) return "over a year"
    return Math.round(d / 30) + " months"
  }

  // The next cursor stop, skipping "Select all" while it is hidden.
  function step(d) {
    var next = Math.max(0, Math.min(confirmIndex, cursor + d))
    if (next === allIndex && list.length <= 1) next = Math.max(0, Math.min(confirmIndex, next + d))
    return next
  }

  function stepDays(delta) {
    var at = dayChoices.indexOf(days) + delta
    if (at >= 0 && at < dayChoices.length) daysChosen(dayChoices[at])
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
          text: root.failed ? "Couldn't list these right now. Nothing was moved."
            : root.items === null ? "Looking…"
            : root.list.length === 0 ? (root.unclaimed ? "No unclaimed folder has been untouched that long."
              : root.virus ? "Nothing left to review." : "There is nothing here to clear.")
            : root.unclaimed ? "Nothing installed uses these, and nothing in them has changed for a long time. Check each one before ticking it — a folder can still hold something you want."
            : root.virus ? "ClamAV matched these against known malware. Tick what you don't recognise to move it to the Trash. If you know where a file came from (a game's DLL, a Wine or Proton file), it may be a false alarm."
            : "Tick what to move to Trash. Apps rebuild their caches when they need them, which can make them a little slower the first time."
          color: Tokens.fg2
          wrapMode: Text.WordWrap
        }
      }

      // Unclaimed: how long a folder must be untouched to be suggested.
      Rectangle {
        visible: root.unclaimed
        Layout.fillWidth: true
        implicitHeight: ageRow.implicitHeight + Tokens.sp(12)
        radius: Tokens.radius
        color: "transparent"
        border.width: root.cursor === root.ageIndex ? Tokens.border : 0
        border.color: Tokens.fg
        RowLayout {
          id: ageRow
          anchors.verticalCenter: parent.verticalCenter
          x: Tokens.sp(6)
          width: parent.width - Tokens.sp(12)
          spacing: Tokens.sp(6)
          KText { text: "Untouched for at least"; color: Tokens.fg2 }
          Repeater {
            model: root.dayChoices
            delegate: ActionButton {
              required property var modelData
              label: Present.ageWords(modelData)
              primary: modelData === root.days
              enabledAction: !root.busy
              onActivated: root.daysChosen(modelData)
            }
          }
          Item { Layout.fillWidth: true }
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
              height: Math.max(box.implicitHeight, pathText.implicitHeight + labelText.implicitHeight) + Tokens.sp(14)
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: { root.cursor = root.firstRow + index; root.toggled(modelData.id) }
              }
              CheckBox {
                id: box
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                checked: root.checked[modelData.id] === true
                hasCursor: root.cursor === root.firstRow + index
                onToggled: root.toggled(modelData.id)
              }
              Column {
                anchors.left: box.right
                anchors.right: rightSide.left
                anchors.leftMargin: Tokens.sp(4)
                anchors.rightMargin: Tokens.sp(12)
                anchors.verticalCenter: parent.verticalCenter
                KText { id: labelText; width: parent.width; text: modelData.label; elide: Text.ElideRight }
                KText {
                  id: pathText
                  width: parent.width
                  text: modelData.path + (typeof modelData.days === "number" ? " · untouched for " + root.ageText(modelData.days) : "")
                  font.pixelSize: Tokens.small
                  color: Tokens.fg3
                  elide: Text.ElideMiddle
                }
              }
              Row {
                id: rightSide
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Tokens.sp(10)
                KText {
                  anchors.verticalCenter: parent.verticalCenter
                  text: Present.bytes(modelData.bytes) + (modelData.complete ? "" : "+")
                  color: Tokens.fg2
                }
                ActionButton {
                  visible: root.canIgnore
                  anchors.verticalCenter: parent.verticalCenter
                  label: root.virus ? "Not a threat" : "Ignore"
                  enabledAction: !root.busy
                  onActivated: root.ignored(modelData.id)
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
        text: root.unclaimed
          ? "Ignore never suggests a folder again (undo on the check). Moved items stay in the Trash, where you can restore them; their space is freed when you empty it."
          : root.virus
          ? "Not a threat hides the file until its contents change (undo on the check). The Trash isn't scanned; files moved there can be restored."
          : "Moved items stay in the Trash, where you can restore them. Their space is freed when you empty the Trash."
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
          label: root.busy ? "Moving…" : root.chosen.length ? "Move " + root.chosen.length + " to Trash" : "Move to Trash"
          primary: true
          trash: true
          enabledAction: root.chosen.length > 0 && !root.busy
          hasCursor: root.cursor === root.confirmIndex
          onActivated: root.confirmed()
        }
      }
    }
  }

  // Up/Down walk the age choice, "Select all", the rows and then the
  // buttons; Left/Right change the age while it has the cursor; Tab jumps
  // to the buttons and back; I ignores the row under the cursor (marks it as
  // not a threat, for the virus scan's files).
  function handleKey(event) {
    if (root.busy) return true
    var k = event.key
    var onRow = root.cursor >= root.firstRow && root.cursor < root.cancelIndex
    if (k === Qt.Key_Escape) root.canceled()
    else if (root.cursor === root.ageIndex && (k === Qt.Key_Left || k === Qt.Key_H)) root.stepDays(-1)
    else if (root.cursor === root.ageIndex && (k === Qt.Key_Right || k === Qt.Key_L)) root.stepDays(1)
    else if (k === Qt.Key_Up || k === Qt.Key_K || k === Qt.Key_Left || k === Qt.Key_H) root.cursor = root.step(-1)
    else if (k === Qt.Key_Down || k === Qt.Key_J || k === Qt.Key_Right || k === Qt.Key_L) root.cursor = root.step(1)
    else if (k === Qt.Key_Tab) root.cursor = root.cursor < root.cancelIndex ? root.confirmIndex : 0
    else if (k === Qt.Key_Backtab) root.cursor = root.cursor < root.cancelIndex ? root.cancelIndex : 0
    else if (k === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) root.allToggled()
    else if (k === Qt.Key_I && root.canIgnore && onRow) root.ignored(root.list[root.cursor - root.firstRow].id)
    else if (k === Qt.Key_Space || k === Qt.Key_Return || k === Qt.Key_Enter) {
      if (root.cursor === root.allIndex) root.allToggled()
      else if (onRow) root.toggled(root.list[root.cursor - root.firstRow].id)
      else if (root.cursor === root.cancelIndex) root.canceled()
      else if (root.cursor === root.confirmIndex && root.chosen.length > 0) root.confirmed()
    } else return false
    return true
  }
}

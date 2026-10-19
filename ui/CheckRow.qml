import QtQuick
import "../model/Status.js" as Status

// One check in the list: state glyph, title and state word, status line, and
// a quieter line of context underneath.
Rectangle {
  id: root

  property var check: ({})
  property bool selected: false

  signal picked()

  readonly property string kind: check.kind || "off"

  implicitHeight: body.implicitHeight + Tokens.sp(20)
  radius: Tokens.radius
  color: selected ? Tokens.accentFill : mouse.containsMouse ? Tokens.fill2 : Tokens.fill
  border.width: 1
  border.color: selected ? Tokens.accent : Tokens.line

  Accessible.role: Accessible.ListItem
  Accessible.name: (check.title || "") + ", " + Status.label(kind) + ", " + (check.status || "")

  Glyph {
    id: glyph
    x: Tokens.sp(12)
    y: Tokens.sp(12)
    name: root.kind
    color: Tokens.kindColor(root.kind)
  }

  Column {
    id: body
    anchors.left: glyph.right
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.leftMargin: Tokens.sp(10)
    anchors.rightMargin: Tokens.sp(12)
    anchors.topMargin: Tokens.sp(10)
    spacing: Tokens.sp(2)

    Item {
      width: parent.width
      height: titleText.implicitHeight
      KText {
        id: titleText
        anchors.left: parent.left
        anchors.right: word.left
        anchors.rightMargin: Tokens.sp(8)
        text: root.check.title || ""
        font.bold: true
        elide: Text.ElideRight
      }
      KText {
        id: word
        anchors.right: parent.right
        anchors.verticalCenter: titleText.verticalCenter
        text: Status.label(root.kind).toUpperCase()
        font.pixelSize: Tokens.caption
        font.letterSpacing: 0.5
        color: Tokens.kindColor(root.kind)
      }
    }
    KText {
      width: parent.width
      text: root.check.status || ""
      color: Tokens.fg2
      elide: Text.ElideRight
    }
    KText {
      width: parent.width
      text: root.check.meta || ""
      font.pixelSize: Tokens.small
      color: Tokens.fg3
      elide: Text.ElideRight
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.picked()
  }
}

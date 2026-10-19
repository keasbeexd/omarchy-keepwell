import QtQuick
import "../model/Status.js" as Status

// The one sentence at the top of a section: how it is, and the way to the
// check that matters most.
Rectangle {
  id: root

  property var section: ({ checks: [], hero: {} })
  signal go()

  readonly property string worst: Status.worst(section.checks || [])
  readonly property var copy: (section.hero && section.hero[worst]) || ["", ""]

  implicitHeight: Math.max(textCol.implicitHeight, button.implicitHeight) + Tokens.sp(28)
  radius: Tokens.radius
  color: Tokens.kindFill(worst)
  border.width: 1
  border.color: Tokens.kindBorder(worst)

  Glyph {
    id: glyph
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Tokens.sp(16)
    name: root.worst
    size: Tokens.sp(28)
    strokeWidth: 1.3
    color: root.worst === "good" ? Tokens.fg2 : Tokens.kindColor(root.worst)
  }

  Column {
    id: textCol
    anchors.left: glyph.right
    anchors.right: button.left
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Tokens.sp(14)
    anchors.rightMargin: Tokens.sp(14)
    spacing: Tokens.sp(2)
    KText {
      width: parent.width
      text: root.copy[0]
      font.pixelSize: Tokens.title
      font.bold: true
      elide: Text.ElideRight
    }
    KText {
      width: parent.width
      text: root.copy[1]
      color: Tokens.fg2
      wrapMode: Text.WordWrap
    }
  }

  // Only when there is something to show.
  ActionButton {
    id: button
    visible: root.worst !== "good"
    width: visible ? implicitWidth : 0
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.rightMargin: visible ? Tokens.sp(16) : 0
    primary: true
    label: "Show me"
    onActivated: root.go()
  }
}

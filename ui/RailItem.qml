import QtQuick
import "../model/Status.js" as Status

// One section in the left rail: its name, and underneath, what it needs.
Rectangle {
  id: root

  property string name: ""
  property string icon: "shield"
  property var checks: []
  property bool selected: false

  signal picked()

  readonly property string worst: Status.worst(checks)

  implicitHeight: col.implicitHeight + Tokens.sp(20)
  radius: Tokens.radius
  color: selected ? Tokens.fill2 : mouse.containsMouse ? Tokens.fill : "transparent"
  border.width: 1
  border.color: selected ? Tokens.line2 : "transparent"

  Accessible.role: Accessible.PageTab
  Accessible.name: name + ", " + Status.summary(checks)

  Column {
    id: col
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Tokens.sp(12)
    anchors.rightMargin: Tokens.sp(12)
    spacing: Tokens.sp(3)

    Row {
      spacing: Tokens.sp(10)
      Glyph {
        anchors.verticalCenter: parent.verticalCenter
        name: root.icon
        color: Tokens.fg
      }
      KText {
        anchors.verticalCenter: parent.verticalCenter
        text: root.name
        font.bold: true
      }
    }

    Row {
      leftPadding: Tokens.sp(26)
      spacing: Tokens.sp(6)
      Glyph {
        visible: root.worst !== "good"
        anchors.verticalCenter: parent.verticalCenter
        name: root.worst
        size: Tokens.sp(12)
        strokeWidth: 1.6
        color: Tokens.kindColor(root.worst)
      }
      KText {
        anchors.verticalCenter: parent.verticalCenter
        text: Status.summary(root.checks)
        font.pixelSize: Tokens.small
        color: root.worst === "good" ? Tokens.fg3 : Tokens.kindColor(root.worst)
      }
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

import QtQuick

// A labelled checkbox drawn from theme tokens.
Item {
  id: root

  property string label: ""
  property string hint: ""
  property bool checked: false
  property bool hasCursor: false

  signal toggled()

  implicitHeight: Math.max(box.height, labelText.implicitHeight)
  implicitWidth: box.width + Tokens.sp(10) + labelText.implicitWidth

  Accessible.role: Accessible.CheckBox
  Accessible.name: label
  Accessible.checked: checked

  Rectangle {
    id: box
    anchors.verticalCenter: parent.verticalCenter
    width: Tokens.sp(16)
    height: width
    radius: Math.min(Tokens.radius, 3)
    color: root.checked ? Tokens.accentFill : "transparent"
    border.width: root.hasCursor ? Tokens.border : 1
    border.color: root.hasCursor ? Tokens.fg : root.checked ? Tokens.accent : Tokens.line2
    Glyph {
      visible: root.checked
      anchors.centerIn: parent
      name: "tick"
      size: parent.width * 0.85
      strokeWidth: 2
      color: Tokens.fg
    }
  }

  Row {
    anchors.left: box.right
    anchors.leftMargin: Tokens.sp(10)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Tokens.sp(6)
    KText { id: labelText; text: root.label }
    KText { text: root.hint; color: Tokens.fg3; visible: root.hint !== "" }
  }

  MouseArea {
    anchors.fill: parent
    cursorShape: Qt.PointingHandCursor
    onClicked: root.toggled()
  }
}

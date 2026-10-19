import QtQuick

// A labelled action. `elevated` marks one that opens a terminal showing the
// exact command (the >_ tag); `trash` one that moves files to Trash. Both
// marks are the promise the button keeps, so they are drawn from the action's
// own data, never added for decoration.
Rectangle {
  id: root

  property string label: ""
  property bool primary: false
  property bool elevated: false
  property bool trash: false
  property bool enabledAction: true
  property bool hasCursor: false

  signal activated()

  implicitHeight: Tokens.controlHeight + Tokens.sp(4)
  implicitWidth: row.implicitWidth + Tokens.sp(28)
  radius: Tokens.radius
  color: !enabledAction ? "transparent"
    : primary ? Tokens.accentFill
    : (mouse.containsMouse || hasCursor) ? Tokens.fill2 : Tokens.fill
  // The keyboard cursor is a heavier border in the text colour, so it shows
  // on a primary button too, whose fill already marks it.
  border.width: hasCursor ? Tokens.border : 1
  border.color: hasCursor ? Tokens.fg : !enabledAction ? Tokens.line2 : primary ? Tokens.accent : Tokens.line2
  opacity: enabledAction ? 1 : 0.7

  Accessible.role: Accessible.Button
  Accessible.name: label

  Row {
    id: row
    anchors.centerIn: parent
    spacing: Tokens.sp(8)

    Rectangle {
      visible: root.elevated
      anchors.verticalCenter: parent.verticalCenter
      width: tag.implicitWidth + Tokens.sp(8)
      height: tag.implicitHeight
      color: "transparent"
      radius: Math.min(Tokens.radius, 2)
      border.width: 1
      border.color: Tokens.fg2
      KText {
        id: tag
        anchors.centerIn: parent
        text: ">_"
        font.pixelSize: Tokens.caption
        font.bold: true
        color: Tokens.fg2
      }
    }

    Glyph {
      visible: root.trash
      anchors.verticalCenter: parent.verticalCenter
      name: "trash"
      size: Tokens.sp(14)
      color: Tokens.fg
    }

    KText {
      anchors.verticalCenter: parent.verticalCenter
      text: root.label
      color: root.enabledAction ? Tokens.fg : Tokens.fg3
      font.weight: root.primary ? Font.Medium : Font.Normal
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: root.enabledAction ? Qt.PointingHandCursor : Qt.ForbiddenCursor
    onClicked: if (root.enabledAction) root.activated()
  }
}

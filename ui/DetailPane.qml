import QtQuick
import QtQuick.Layouts

// Everything about one check, in reading order: what state it is in, what the
// tool does in plain words, the facts (with who owns each setting), a note
// where honesty needs one, and only then the actions.
Rectangle {
  id: root

  property var check: ({ facts: [], actions: [] })
  property int cursorAction: -1

  signal actionActivated(int index)
  signal linkActivated(string url)

  readonly property string kind: check.kind || "off"
  readonly property var actions: check.actions || []
  readonly property bool anyElevated: {
    for (var i = 0; i < actions.length; i++) if (actions[i].elevated) return true
    return false
  }

  radius: Tokens.radius
  color: "transparent"
  border.width: 1
  border.color: Tokens.line

  Flickable {
    id: flick
    anchors.fill: parent
    anchors.margins: Tokens.sp(18)
    contentHeight: content.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ScrollHint { flick: flick }

    ColumnLayout {
      id: content
      width: flick.width - Tokens.sp(8)
      spacing: Tokens.sp(14)

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(10)
        Glyph {
          Layout.alignment: Qt.AlignTop
          Layout.topMargin: Tokens.sp(2)
          name: root.kind
          size: Tokens.sp(20)
          strokeWidth: 1.4
          color: Tokens.kindColor(root.kind)
        }
        // preferredWidth 0: a wrapping title would otherwise ask for its full
        // unwrapped width and push the tool chip on top of itself.
        KText {
          Layout.fillWidth: true
          Layout.preferredWidth: 0
          text: root.check.title || ""
          font.pixelSize: Tokens.heading
          font.bold: true
          wrapMode: Text.WordWrap
        }
        Rectangle {
          Layout.alignment: Qt.AlignTop
          Layout.maximumWidth: Math.round(content.width * 0.45)
          implicitWidth: toolText.implicitWidth + Tokens.sp(16)
          implicitHeight: toolText.implicitHeight + Tokens.sp(4)
          radius: Tokens.radius
          color: "transparent"
          border.width: 1
          border.color: Tokens.line2
          KText {
            id: toolText
            anchors.verticalCenter: parent.verticalCenter
            x: Tokens.sp(8)
            width: parent.width - Tokens.sp(16)
            text: root.check.tool || ""
            font.pixelSize: Tokens.small
            color: Tokens.fg2
            elide: Text.ElideRight
          }
        }
      }

      KText {
        Layout.fillWidth: true
        text: root.check.status || ""
        font.pixelSize: Tokens.title
        font.weight: Font.Medium
        wrapMode: Text.WordWrap
      }

      // A running scan's progress. While the total is still being counted
      // the bar shows a short segment sliding back and forth.
      ColumnLayout {
        visible: !!root.check.progress
        Layout.fillWidth: true
        spacing: Tokens.sp(6)
        Rectangle {
          id: track
          readonly property real fraction: root.check.progress ? root.check.progress.fraction : 0
          Layout.fillWidth: true
          implicitHeight: Tokens.sp(6)
          radius: height / 2
          color: Tokens.fill2
          clip: true
          Rectangle {
            id: bar
            height: parent.height
            radius: parent.radius
            color: Tokens.accent
            width: track.fraction < 0 ? parent.width * 0.25 : parent.width * track.fraction
            Behavior on width { enabled: track.fraction >= 0; NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            SequentialAnimation on x {
              running: track.visible && track.fraction < 0
              loops: Animation.Infinite
              NumberAnimation { from: 0; to: track.width * 0.75; duration: 1200; easing.type: Easing.InOutSine }
              NumberAnimation { from: track.width * 0.75; to: 0; duration: 1200; easing.type: Easing.InOutSine }
              onRunningChanged: if (!running) bar.x = 0
            }
          }
        }
        KText {
          Layout.fillWidth: true
          text: root.check.progress ? root.check.progress.text : ""
          font.pixelSize: Tokens.small
          color: Tokens.fg2
          wrapMode: Text.WordWrap
        }
      }

      KText {
        Layout.fillWidth: true
        Layout.maximumWidth: Tokens.sp(560)
        text: root.check.what || ""
        color: Tokens.fg2
        wrapMode: Text.WordWrap
        lineHeight: 1.15
      }

      // Facts: label · value · who owns it.
      Column {
        Layout.fillWidth: true
        Rectangle { width: parent.width; height: 1; color: Tokens.line }
        Repeater {
          model: root.check.facts || []
          // Label column, then the value and its owner stacked: in a narrow
          // pane a long value wraps instead of losing its end.
          delegate: Item {
            required property var modelData
            width: parent.width
            height: Math.max(k.implicitHeight, valueCol.implicitHeight) + Tokens.sp(16)
            KText {
              id: k
              anchors.left: parent.left
              anchors.top: parent.top
              anchors.topMargin: Tokens.sp(8)
              width: Tokens.sp(140)
              text: modelData.k
              color: Tokens.fg3
              wrapMode: Text.WordWrap
            }
            Column {
              id: valueCol
              anchors.left: k.right
              anchors.right: parent.right
              anchors.leftMargin: Tokens.sp(12)
              anchors.top: parent.top
              anchors.topMargin: Tokens.sp(8)
              spacing: Tokens.sp(1)
              KText {
                width: parent.width
                text: modelData.v
                wrapMode: Text.WordWrap
                font.underline: !!modelData.url && rowMouse.containsMouse
              }
              KText {
                visible: !!modelData.owner || !!modelData.url
                width: parent.width
                text: (modelData.owner || "") + (modelData.url ? (modelData.owner ? " · " : "") + "details ↗" : "")
                font.pixelSize: Tokens.caption
                color: Tokens.fg3
                wrapMode: Text.WordWrap
              }
            }
            Rectangle {
              anchors.bottom: parent.bottom
              width: parent.width
              height: 1
              color: Tokens.line
            }
            MouseArea {
              id: rowMouse
              anchors.fill: parent
              enabled: !!modelData.url
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.linkActivated(modelData.url)
            }
          }
        }
      }

      Rectangle {
        visible: !!root.check.note
        Layout.fillWidth: true
        implicitHeight: noteText.implicitHeight + Tokens.sp(20)
        radius: Tokens.radius
        color: Tokens.fill
        KText {
          id: noteText
          anchors.fill: parent
          anchors.margins: Tokens.sp(10)
          anchors.leftMargin: Tokens.sp(12)
          text: root.check.note || ""
          font.pixelSize: Tokens.small
          color: Tokens.fg2
          wrapMode: Text.WordWrap
        }
      }

      Flow {
        visible: root.actions.length > 0
        Layout.fillWidth: true
        Layout.topMargin: Tokens.sp(6)
        spacing: Tokens.sp(8)
        Repeater {
          model: root.actions
          delegate: ActionButton {
            required property var modelData
            required property int index
            label: modelData.label
            primary: !!modelData.primary
            elevated: !!modelData.elevated
            trash: !!modelData.trash
            enabledAction: !modelData.disabled
            hasCursor: index === root.cursorAction
            onActivated: root.actionActivated(index)
          }
        }
      }

      KText {
        visible: root.anyElevated
        Layout.fillWidth: true
        text: ">_ opens a terminal that shows the exact command before anything runs."
        font.pixelSize: Tokens.caption
        color: Tokens.fg3
        wrapMode: Text.WordWrap
      }
    }
  }
}

import QtQuick
import QtQuick.Layouts

// Background checks: what to check, which days, what time. Saving writes
// the timer (no root, no terminal); each run notifies and changes nothing.
Item {
  id: root

  property bool opened: false
  property bool loading: true
  property bool busy: false
  property bool enabled: false          // a schedule is on now
  property var days: []                 // ["mon", "wed"]
  property string time: "10:00"
  property var parts: []                // vulns, cleanup, scan-downloads, scan-home

  signal dayToggled(string day)
  signal everyDay()
  signal timeStepped(int minutes)
  signal partToggled(string part)
  signal scanTargetChosen(string target)
  signal saved()
  signal turnedOff()
  signal canceled()

  readonly property var allDays: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
  readonly property var dayLabels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
  readonly property bool scanOn: parts.indexOf("scan-downloads") !== -1 || parts.indexOf("scan-home") !== -1
  readonly property string scanTarget: parts.indexOf("scan-home") !== -1 ? "home" : "downloads"
  readonly property bool valid: days.length > 0 && parts.length > 0

  // Keyboard stops, in order. Left/Right work inside the chip and time rows.
  readonly property var stops: ["vulns", "cleanup", "scan", "target", "days", "time"]
    .concat(enabled ? ["off"] : []).concat(["cancel", "save"])
  property int cursor: 0
  property int dayFocus: 0              // 0–6 a day, 7 "Every day"
  readonly property string at: stops[cursor] || ""

  visible: opened
  onOpenedChanged: if (opened) { cursor = 0; dayFocus = 0 }

  function summary() {
    if (!days.length) return "Pick at least one day."
    if (!parts.length) return "Pick at least one check."
    var names = days.map(function(d) { return root.dayLabels[root.allDays.indexOf(d)] })
    return "Runs " + names.join(", ") + " at " + time + ". Each run sends one notification and changes nothing."
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
        KText { text: "SYSTEM CARE · BACKGROUND CHECKS"; font.pixelSize: Tokens.caption; font.letterSpacing: 0.6; color: Tokens.fg3 }
        KText { text: "Background checks"; font.pixelSize: Tokens.heading; font.bold: true }
        KText {
          Layout.fillWidth: true
          text: root.loading ? "Loading…" : "Choose what to check and when. Keepwell sends one notification with what it found; it never removes, installs or changes anything."
          color: Tokens.fg2
          wrapMode: Text.WordWrap
        }
      }

      KText { text: "What to check"; font.bold: true }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        CheckBox {
          label: "Vulnerabilities"
          hint: "uses the network: security.archlinux.org"
          checked: root.parts.indexOf("vulns") !== -1
          hasCursor: root.at === "vulns"
          onToggled: root.partToggled("vulns")
        }
        CheckBox {
          label: "Cleanup report"
          hint: "how much space could be freed"
          checked: root.parts.indexOf("cleanup") !== -1
          hasCursor: root.at === "cleanup"
          onToggled: root.partToggled("cleanup")
        }
        CheckBox {
          label: "Virus scan"
          hint: "reads only; runs in the background"
          checked: root.scanOn
          hasCursor: root.at === "scan"
          onToggled: root.partToggled("scan-" + root.scanTarget)
        }
        Row {
          Layout.leftMargin: Tokens.sp(26)
          spacing: Tokens.sp(6)
          opacity: root.scanOn ? 1 : 0.5
          Repeater {
            model: [["downloads", "Downloads"], ["home", "Home folder"]]
            delegate: ActionButton {
              required property var modelData
              label: modelData[1]
              primary: root.scanTarget === modelData[0]
              enabledAction: root.scanOn
              hasCursor: root.at === "target" && root.scanTarget === modelData[0]
              onActivated: root.scanTargetChosen(modelData[0])
            }
          }
        }
      }

      KText { text: "Days"; font.bold: true }
      Flow {
        Layout.fillWidth: true
        spacing: Tokens.sp(6)
        Repeater {
          model: 7
          delegate: ActionButton {
            required property int index
            label: root.dayLabels[index]
            primary: root.days.indexOf(root.allDays[index]) !== -1
            hasCursor: root.at === "days" && root.dayFocus === index
            onActivated: root.dayToggled(root.allDays[index])
          }
        }
        ActionButton {
          label: "Every day"
          primary: root.days.length === 7
          hasCursor: root.at === "days" && root.dayFocus === 7
          onActivated: root.everyDay()
        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        KText { text: "Time"; font.bold: true }
        ActionButton { label: "−"; onActivated: root.timeStepped(-30) }
        Rectangle {
          implicitWidth: timeText.implicitWidth + Tokens.sp(24)
          implicitHeight: Tokens.controlHeight + Tokens.sp(4)
          radius: Tokens.radius
          color: Tokens.fill
          border.width: root.at === "time" ? Tokens.border : 1
          border.color: root.at === "time" ? Tokens.fg : Tokens.line2
          KText { id: timeText; anchors.centerIn: parent; text: root.time; font.bold: true }
        }
        ActionButton { label: "+"; onActivated: root.timeStepped(30) }
        KText { text: "30-minute steps"; color: Tokens.fg3; font.pixelSize: Tokens.small }
        Item { Layout.fillWidth: true }
      }

      KText {
        Layout.fillWidth: true
        text: root.summary()
        color: root.valid ? Tokens.fg2 : Tokens.accent
        wrapMode: Text.WordWrap
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        ActionButton {
          visible: root.enabled
          label: "Turn off"
          enabledAction: !root.busy
          hasCursor: root.at === "off"
          onActivated: root.turnedOff()
        }
        Item { Layout.fillWidth: true }
        ActionButton {
          label: "Cancel"
          enabledAction: !root.busy
          hasCursor: root.at === "cancel"
          onActivated: root.canceled()
        }
        ActionButton {
          label: root.busy ? "Saving…" : root.enabled ? "Save" : "Turn on"
          primary: true
          enabledAction: root.valid && !root.busy && !root.loading
          hasCursor: root.at === "save"
          onActivated: root.saved()
        }
      }
    }
  }

  function handleKey(event) {
    if (root.busy) return true
    var k = event.key
    var left = k === Qt.Key_Left || k === Qt.Key_H
    var right = k === Qt.Key_Right || k === Qt.Key_L
    if (k === Qt.Key_Escape) root.canceled()
    else if (root.at === "target" && (left || right)) root.scanTargetChosen(left ? "downloads" : "home")
    else if (root.at === "days" && (left || right)) root.dayFocus = Math.max(0, Math.min(7, root.dayFocus + (left ? -1 : 1)))
    else if (root.at === "time" && (left || right)) root.timeStepped(left ? -30 : 30)
    else if (k === Qt.Key_Up || k === Qt.Key_K || k === Qt.Key_Backtab || left) root.cursor = Math.max(0, root.cursor - 1)
    else if (k === Qt.Key_Down || k === Qt.Key_J || k === Qt.Key_Tab || right) root.cursor = Math.min(root.stops.length - 1, root.cursor + 1)
    else if (k === Qt.Key_Space || k === Qt.Key_Return || k === Qt.Key_Enter) {
      if (root.at === "vulns" || root.at === "cleanup") root.partToggled(root.at)
      else if (root.at === "scan") root.partToggled("scan-" + root.scanTarget)
      else if (root.at === "days") { if (root.dayFocus === 7) root.everyDay(); else root.dayToggled(root.allDays[root.dayFocus]) }
      else if (root.at === "off") root.turnedOff()
      else if (root.at === "cancel") root.canceled()
      else if (root.at === "save" && root.valid) root.saved()
    } else return false
    return true
  }
}

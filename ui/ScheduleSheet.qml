import QtQuick
import QtQuick.Layouts

// What Keepwell checks by itself, and the deep scans you can schedule.
// Always-on checks need no setup and are listed with how they work. Deep
// scans are opt-in, on the days and at the time you choose; a run the
// computer was off or asleep for is reported as missed, never run late.
Item {
  id: root

  property bool opened: false
  property bool busy: false
  property var schedules: ({})          // Present.schedules: .deep with .enabled and .settings
  property var tools: ({})              // the check's tools probe: gitleaks, osvScanner

  signal saved(var deep)
  signal canceled()

  readonly property var allDays: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
  readonly property var dayLabels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
  readonly property var alwaysOn: [
    ["Firewall", "on, and blocking incoming connections"],
    ["Known vulnerabilities", "arch-audit; downloads Arch's security list (about 900 KB) — skipped on a metered connection"],
    ["System updates", "how long since the last one"],
    ["Antivirus", "how old the virus definitions are, and the last scan's result"],
    ["Snapshots", "set up, and the boot menu in sync"],
    ["Disk space", "how full the system disk is"],
    ["Cleanup", "what could be freed"],
    ["Unclaimed folders", "app folders nothing uses any more"],
    ["Privacy settings", "browser, network and app telemetry"],
    ["Camera and microphone", "whether anything is using them"]
  ]

  // An editable copy, taken when the sheet opens.
  property var d: ({ enabled: false, days: [], time: "13:00", parts: ["scan-downloads"], battery: true })

  readonly property bool hasLeaks: tools.gitleaks === true
  readonly property bool hasOsv: tools.osvScanner === true
  readonly property bool scanOn: d.parts.indexOf("scan-downloads") !== -1 || d.parts.indexOf("scan-home") !== -1
  readonly property string scanTarget: d.parts.indexOf("scan-home") !== -1 ? "home" : "downloads"
  readonly property bool valid: !d.enabled || (d.days.length > 0 && d.parts.length > 0)

  // Keyboard stops, in order. Left/Right work inside chip and time rows.
  readonly property var stops: ["on", "virus", "target"].concat(hasLeaks ? ["leaks"] : [])
    .concat(hasOsv ? ["osv"] : []).concat(["battery", "days", "time", "cancel", "save"])
  property int cursor: 0
  property int dayFocus: 0              // 0–6 a day, 7 "Every day"
  readonly property string at: stops[cursor] || ""

  visible: opened
  onOpenedChanged: if (opened) load()
  onCursorChanged: follow()

  function load() {
    var ds = (schedules.deep && schedules.deep.settings) || {}
    d = { enabled: !!(schedules.deep && schedules.deep.enabled), days: (ds.days || ["sat"]).slice(),
          time: ds.time || "13:00", parts: (ds.parts || ["scan-downloads"]).slice(), battery: ds.battery !== false }
    cursor = 0
    dayFocus = 0
    flick.contentY = 0
  }

  function setD(field, value) { var n = Object.assign({}, d); n[field] = value; d = n }

  function toggleDay(day) {
    var days = d.days.indexOf(day) === -1 ? d.days.concat([day]) : d.days.filter(function(x) { return x !== day })
    setD("days", allDays.filter(function(x) { return days.indexOf(x) !== -1 }))
  }
  function everyDay() { setD("days", d.days.length === 7 ? [] : allDays.slice()) }
  function stepTime(minutes) {
    var hm = d.time.split(":")
    var total = (Number(hm[0]) * 60 + Number(hm[1]) + minutes + 1440) % 1440
    var pad = function(n) { return (n < 10 ? "0" : "") + n }
    setD("time", pad(Math.floor(total / 60)) + ":" + pad(total % 60))
  }
  function togglePart(part) {
    var parts = d.parts.indexOf(part) === -1 ? d.parts.concat([part]) : d.parts.filter(function(x) { return x !== part })
    if (part.indexOf("scan-") === 0 && parts.indexOf(part) !== -1)
      parts = parts.filter(function(x) { return x.indexOf("scan-") !== 0 || x === part })
    setD("parts", parts)
  }
  function chooseTarget(target) {
    if (!scanOn) return
    setD("parts", d.parts.filter(function(x) { return x.indexOf("scan-") !== 0 }).concat(["scan-" + target]))
  }

  function describe() {
    if (!d.enabled) return "Not scheduled — scans run only when you start them."
    if (!d.days.length) return "Pick at least one day."
    if (!d.parts.length) return "Pick at least one scan."
    var names = d.days.length === 7 ? "Every day" : d.days.map(function(x) { return root.dayLabels[root.allDays.indexOf(x)] }).join(", ")
    return names + " at " + d.time + "."
  }

  function follow() {
    var item = { "on": deepHead, "virus": dVirus, "target": dTarget, "leaks": dLeaks, "osv": dOsv,
                 "battery": dBattery, "days": dDays, "time": dTime }[at]
    if (!item) return
    var top = item.mapToItem(body, 0, 0).y
    var bottom = top + item.height
    if (top < flick.contentY) flick.contentY = Math.max(0, top - Tokens.sp(8))
    else if (bottom > flick.contentY + flick.height) flick.contentY = bottom - flick.height + Tokens.sp(8)
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
        KText { text: "KEEPWELL · CHECKS"; font.pixelSize: Tokens.caption; font.letterSpacing: 0.6; color: Tokens.fg3 }
        KText { text: "How Keepwell checks"; font.pixelSize: Tokens.heading; font.bold: true }
      }

      Flickable {
        id: flick
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: body.implicitHeight
        Layout.minimumHeight: Math.min(body.implicitHeight, Tokens.sp(160))
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollHint { flick: flick }

        ColumnLayout {
          id: body
          width: flick.width - Tokens.sp(8)
          spacing: Tokens.sp(10)

          // ---------------- always on ----------------
          Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }
          RowLayout {
            Layout.fillWidth: true
            KText { Layout.fillWidth: true; text: "Always on"; font.pixelSize: Tokens.title; font.bold: true }
            KText { text: "NO SETUP"; font.pixelSize: Tokens.caption; font.bold: true; color: Tokens.fg2 }
          }
          KText {
            Layout.fillWidth: true
            text: "Keepwell runs these by itself when you log in and every hour while you're logged in; opening Keepwell also refreshes the local ones if the last check is over a minute old. They take about a second, read only, and change nothing. When one newly needs attention, the shield changes and you get one notification."
            color: Tokens.fg2
            font.pixelSize: Tokens.small
            wrapMode: Text.WordWrap
          }
          Column {
            Layout.fillWidth: true
            spacing: Tokens.sp(3)
            Repeater {
              model: root.alwaysOn
              delegate: Row {
                required property var modelData
                width: parent.width
                spacing: Tokens.sp(8)
                Glyph { name: "good"; size: Tokens.sp(12); color: Tokens.fg2; anchors.verticalCenter: name.verticalCenter }
                KText { id: name; text: modelData[0]; font.pixelSize: Tokens.small; font.bold: true }
                KText {
                  width: parent.width - x
                  text: modelData[1]
                  font.pixelSize: Tokens.small
                  color: Tokens.fg3
                  wrapMode: Text.WordWrap
                }
              }
            }
          }

          // ---------------- deep scans ----------------
          Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }
          RowLayout {
            id: deepHead
            Layout.fillWidth: true
            KText { Layout.fillWidth: true; text: "Deep scans"; font.pixelSize: Tokens.title; font.bold: true }
            CheckBox { label: "On a schedule"; checked: root.d.enabled; hasCursor: root.at === "on"; onToggled: root.setD("enabled", !root.d.enabled) }
          }
          KText {
            Layout.fillWidth: true
            text: "The long scans you pick, one after another at low priority — minutes to hours. Each run sends one notification with what it found. If the computer is off or asleep at the time, the run is reported as missed, not run late, so you choose when."
            color: Tokens.fg2
            font.pixelSize: Tokens.small
            wrapMode: Text.WordWrap
          }
          ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.sp(8)
            opacity: root.d.enabled ? 1 : 0.5
            CheckBox {
              id: dVirus
              label: "Virus scan"
              hint: "ClamAV; reads only"
              checked: root.scanOn
              hasCursor: root.at === "virus"
              onToggled: root.togglePart("scan-" + root.scanTarget)
            }
            Row {
              id: dTarget
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
                  onActivated: root.chooseTarget(modelData[0])
                }
              }
            }
            CheckBox {
              id: dLeaks
              visible: root.hasLeaks
              label: "Secrets scan"
              hint: "gitleaks; your home folder, or the last folder you chose"
              checked: root.d.parts.indexOf("leaks") !== -1
              hasCursor: root.at === "leaks"
              onToggled: root.togglePart("leaks")
            }
            CheckBox {
              id: dOsv
              visible: root.hasOsv
              label: "Dependency scan"
              hint: "osv-scanner; sends dependency names and versions to OSV.dev"
              checked: root.d.parts.indexOf("osv") !== -1
              hasCursor: root.at === "osv"
              onToggled: root.togglePart("osv")
            }
            CheckBox {
              id: dBattery
              label: "Skip on battery"
              hint: "say so in the notification instead"
              checked: root.d.battery
              hasCursor: root.at === "battery"
              onToggled: root.setD("battery", !root.d.battery)
            }
            Flow {
              id: dDays
              Layout.fillWidth: true
              spacing: Tokens.sp(6)
              Repeater {
                model: 7
                delegate: ActionButton {
                  required property int index
                  label: root.dayLabels[index]
                  primary: root.d.days.indexOf(root.allDays[index]) !== -1
                  hasCursor: root.at === "days" && root.dayFocus === index
                  onActivated: root.toggleDay(root.allDays[index])
                }
              }
              ActionButton {
                label: "Every day"
                primary: root.d.days.length === 7
                hasCursor: root.at === "days" && root.dayFocus === 7
                onActivated: root.everyDay()
              }
            }
            RowLayout {
              id: dTime
              Layout.fillWidth: true
              spacing: Tokens.sp(8)
              KText { text: "Time"; color: Tokens.fg2 }
              ActionButton { label: "−"; onActivated: root.stepTime(-30) }
              Rectangle {
                implicitWidth: tText.implicitWidth + Tokens.sp(24)
                implicitHeight: Tokens.controlHeight + Tokens.sp(4)
                radius: Tokens.radius
                color: Tokens.fill
                border.width: root.at === "time" ? Tokens.border : 1
                border.color: root.at === "time" ? Tokens.fg : Tokens.line2
                KText { id: tText; anchors.centerIn: parent; text: root.d.time; font.bold: true }
              }
              ActionButton { label: "+"; onActivated: root.stepTime(30) }
              KText { text: "30-minute steps"; color: Tokens.fg3; font.pixelSize: Tokens.small }
              Item { Layout.fillWidth: true }
            }
          }
          KText { Layout.fillWidth: true; text: root.describe(); color: root.valid ? Tokens.fg3 : Tokens.accent; font.pixelSize: Tokens.small; wrapMode: Text.WordWrap }
        }
      }

      RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.sp(8)
        Item { Layout.fillWidth: true }
        ActionButton {
          label: "Cancel"
          enabledAction: !root.busy
          hasCursor: root.at === "cancel"
          onActivated: root.canceled()
        }
        ActionButton {
          label: root.busy ? "Saving…" : "Save"
          primary: true
          enabledAction: root.valid && !root.busy
          hasCursor: root.at === "save"
          onActivated: root.saved(root.d)
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
    else if (at === "target" && (left || right)) chooseTarget(left ? "downloads" : "home")
    else if (at === "days" && (left || right)) dayFocus = Math.max(0, Math.min(7, dayFocus + (left ? -1 : 1)))
    else if (at === "time" && (left || right)) stepTime(left ? -30 : 30)
    else if (k === Qt.Key_Up || k === Qt.Key_K || k === Qt.Key_Backtab || left) cursor = Math.max(0, cursor - 1)
    else if (k === Qt.Key_Down || k === Qt.Key_J || k === Qt.Key_Tab || right) cursor = Math.min(stops.length - 1, cursor + 1)
    else if (k === Qt.Key_Space || k === Qt.Key_Return || k === Qt.Key_Enter) {
      if (at === "on") setD("enabled", !d.enabled)
      else if (at === "virus") togglePart("scan-" + scanTarget)
      else if (at === "leaks") togglePart("leaks")
      else if (at === "osv") togglePart("osv")
      else if (at === "battery") setD("battery", !d.battery)
      else if (at === "days") { if (dayFocus === 7) everyDay(); else toggleDay(allDays[dayFocus]) }
      else if (at === "cancel") root.canceled()
      else if (at === "save" && valid) root.saved(d)
    } else return false
    return true
  }
}

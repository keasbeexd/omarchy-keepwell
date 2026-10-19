import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "ui"
import "model/Status.js" as Status

// The Keepwell window: a rail of three sections, a banner saying how the
// section is, the list of checks, and the selected check in detail.
//
// A layer surface on the overlay layer, like the Omarchy menu: it opens above
// whatever is focused on the screen you are looking at, with nothing for the
// user to configure in Hyprland.
Item {
  id: root

  property var sections: []
  property string checkedAt: ""
  property bool checking: false
  // The background-check schedule (Present.schedule), shown in the rail.
  property var schedule: ({ enabled: false, when: "Off", next: "", checks: "", last: "" })
  signal scheduleRequested()
  signal scheduleOffRequested()

  // network: also ask the Arch security tracker (arch-audit).
  signal checkRequested(bool network)
  // action: a check's action object; context: "Security · Firewall".
  signal actionRequested(var action, string checkId, string context)

  // The confirm sheet, driven by the service.
  property bool confirmOpen: false
  property var confirmPlan: null
  property bool confirmFailed: false
  property bool confirmSnapshot: false
  property string confirmContext: ""
  signal confirmAccepted()
  signal confirmCanceled()
  signal confirmSnapshotToggled()
  signal confirmOptionToggled(string id)
  signal confirmAllToggled()

  // The Trash sheet, driven by the service.
  property bool trashOpen: false
  property string trashTitle: ""
  property string trashContext: ""
  property var trashItems: null
  property bool trashFailed: false
  property bool trashBusy: false
  property var trashChecked: ({})
  signal trashToggled(string id)
  signal trashAllToggled()
  property int trashDays: 0
  property var trashDayChoices: []
  signal trashDaysChosen(int days)
  signal trashIgnored(string id)

  // The background-checks sheet, driven by the service.
  property bool schedOpen: false
  property bool schedLoading: true
  property bool schedBusy: false
  property bool schedEnabled: false
  property var schedDays: []
  property string schedTime: "10:00"
  property var schedParts: []
  signal schedDayToggled(string day)
  signal schedEveryDay()
  signal schedTimeStepped(int minutes)
  signal schedPartToggled(string part)
  signal schedScanTargetChosen(string target)
  signal schedSaved()
  signal schedTurnedOff()
  signal schedCanceled()
  signal trashAccepted()
  signal trashCanceled()

  readonly property bool shown: window.visible

  property int sectionIndex: 0
  // Selected check per section, so switching away and back keeps your place.
  property var selection: [0, 0, 0]
  // Keyboard cursor over the detail pane's actions; -1 while it is on the list.
  property int actionCursor: -1
  property string notice: ""

  readonly property var section: sections.length > 0 ? sections[sectionIndex] : ({ checks: [], hero: {} })
  readonly property var checks: section.checks || []
  readonly property int checkIndex: Math.min(selection[sectionIndex] || 0, Math.max(0, checks.length - 1))
  readonly property var check: checks.length > 0 ? checks[checkIndex] : ({ facts: [], actions: [] })

  property var openedOn: null

  function focusedScreen() {
    var monitor = Hyprland.focusedMonitor
    var name = monitor ? String(monitor.name || "") : ""
    if (name === "") return null
    var screens = Quickshell.screens
    for (var i = 0; i < screens.length; i++)
      if (String(screens[i].name) === name) return screens[i]
    return null
  }

  function show() {
    openedOn = focusedScreen()
    window.visible = true
    keys.forceActiveFocus()
  }
  function hide() { window.visible = false; notice = "" }

  function selectSection(i) {
    if (sections.length === 0) return
    sectionIndex = (i + sections.length) % sections.length
    actionCursor = -1
    notice = ""
  }

  function selectCheck(i) {
    if (checks.length === 0) return
    var next = selection.slice()
    next[sectionIndex] = Math.max(0, Math.min(checks.length - 1, i))
    selection = next
    actionCursor = -1
    notice = ""
  }

  function activateAction(i) {
    var actions = check.actions || []
    if (i < 0 || i >= actions.length || actions[i].disabled) return
    actionRequested(actions[i], check.id || "", (section.name || "") + " · " + (check.title || ""))
  }

  // Show one check by id: its section, and it selected.
  function focusCheck(id) {
    for (var s = 0; s < sections.length; s++) {
      var list = sections[s].checks || []
      for (var c = 0; c < list.length; c++) {
        if (list[c].id !== id) continue
        sectionIndex = s
        var next = selection.slice()
        next[s] = c
        selection = next
        actionCursor = -1
        return
      }
    }
  }

  function primaryIndex() {
    var actions = check.actions || []
    for (var i = 0; i < actions.length; i++)
      if (actions[i].primary && !actions[i].disabled) return i
    return -1
  }

  PanelWindow {
    id: window
    visible: false
    screen: root.openedOn !== null ? root.openedOn : null
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "keepwell"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: Tokens.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.hide()
    }

    Rectangle {
      id: card
      anchors.centerIn: parent
      width: Math.round(Math.min(Tokens.sp(1240), window.width * 0.9))
      height: Math.round(Math.min(Tokens.sp(760), window.height * 0.9))
      color: Tokens.bg
      radius: Tokens.radius
      border.width: Tokens.border
      border.color: Tokens.accent
      clip: true

      // Clicks on the card stay on the card.
      MouseArea { anchors.fill: parent }

      FocusScope {
        id: keys
        anchors.fill: parent
        focus: true

        Keys.onPressed: function(event) {
          if (root.confirmOpen) {
            if (confirmSheet.handleKey(event)) event.accepted = true
            return
          }
          if (root.trashOpen) {
            if (trashSheet.handleKey(event)) event.accepted = true
            return
          }
          if (root.schedOpen) {
            if (schedSheet.handleKey(event)) event.accepted = true
            return
          }
          var actions = root.check.actions || []
          if (event.key === Qt.Key_Escape) {
            if (root.actionCursor >= 0) root.actionCursor = -1
            else root.hide()
          } else if (event.key === Qt.Key_Tab) {
            root.selectSection(root.sectionIndex + 1)
          } else if (event.key === Qt.Key_Backtab) {
            root.selectSection(root.sectionIndex - 1)
          } else if (event.key === Qt.Key_Down || event.key === Qt.Key_J) {
            root.selectCheck(root.checkIndex + 1)
          } else if (event.key === Qt.Key_Up || event.key === Qt.Key_K) {
            root.selectCheck(root.checkIndex - 1)
          } else if (event.key === Qt.Key_Right || event.key === Qt.Key_L) {
            if (actions.length > 0) root.actionCursor = Math.min(actions.length - 1, root.actionCursor + 1)
          } else if (event.key === Qt.Key_Left || event.key === Qt.Key_H) {
            root.actionCursor = Math.max(-1, root.actionCursor - 1)
          } else if (event.key === Qt.Key_S) {
            root.scheduleRequested()
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.activateAction(root.actionCursor >= 0 ? root.actionCursor : root.primaryIndex())
          } else {
            return
          }
          event.accepted = true
        }

        ColumnLayout {
          anchors.fill: parent
          spacing: 0

          // ---------------- header ----------------
          RowLayout {
            Layout.fillWidth: true
            Layout.margins: Tokens.sp(14)
            Layout.leftMargin: Tokens.sp(18)
            Layout.rightMargin: Tokens.sp(18)
            spacing: Tokens.sp(12)

            Glyph { name: "shield"; size: Tokens.sp(20); strokeWidth: 1.4 }
            KText {
              text: "Keepwell"
              font.pixelSize: Tokens.heading
              font.bold: true
            }
            KText {
              Layout.fillWidth: true
              text: "Keep your system well."
              color: Tokens.fg3
              elide: Text.ElideRight
            }
            KText {
              text: root.checkedAt
              font.pixelSize: Tokens.small
              color: Tokens.fg3
            }
            ActionButton {
              label: "Refresh"
              enabledAction: !root.checking
              onActivated: { root.notice = ""; root.checkRequested(true) }
            }
            ActionButton {
              label: "Close"
              onActivated: root.hide()
            }
          }
          Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }

          RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ---------------- rail ----------------
            ColumnLayout {
              // A nested layout fills by default; the rail must not, or it
              // takes the width the detail pane needs.
              Layout.fillWidth: false
              Layout.preferredWidth: Tokens.sp(220)
              Layout.fillHeight: true
              Layout.margins: Tokens.sp(10)
              Layout.topMargin: Tokens.sp(14)
              spacing: Tokens.sp(4)

              Repeater {
                model: root.sections
                delegate: RailItem {
                  required property var modelData
                  required property int index
                  Layout.fillWidth: true
                  name: modelData.name
                  icon: modelData.id === "privacy" ? "eye" : modelData.id === "care" ? "wrench" : "shield"
                  checks: modelData.checks
                  selected: index === root.sectionIndex
                  onPicked: root.selectSection(index)
                }
              }

              Item { Layout.fillHeight: true }

              Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }

              // Background checks: a setting of Keepwell, so it lives here
              // rather than among the checks. S opens it from anywhere.
              ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: Tokens.sp(4)
                spacing: Tokens.sp(4)
                RowLayout {
                  Layout.fillWidth: true
                  KText {
                    Layout.fillWidth: true
                    text: "BACKGROUND CHECKS"
                    font.pixelSize: Tokens.caption
                    font.letterSpacing: 0.6
                    color: Tokens.fg3
                  }
                  KText {
                    text: root.schedule.enabled ? "ON" : "OFF"
                    font.pixelSize: Tokens.caption
                    font.bold: true
                    color: root.schedule.enabled ? Tokens.fg : Tokens.fg3
                  }
                }
                KText {
                  Layout.fillWidth: true
                  text: root.schedule.enabled ? root.schedule.when : "Nothing runs unless you turn it on."
                  font.pixelSize: Tokens.small
                  font.bold: root.schedule.enabled
                  color: root.schedule.enabled ? Tokens.fg : Tokens.fg2
                  wrapMode: Text.WordWrap
                }
                KText {
                  Layout.fillWidth: true
                  visible: text !== ""
                  text: root.schedule.enabled ? root.schedule.next : ""
                  font.pixelSize: Tokens.small
                  color: Tokens.fg2
                  wrapMode: Text.WordWrap
                }
                KText {
                  Layout.fillWidth: true
                  visible: text !== ""
                  text: root.schedule.last ? "Last: " + root.schedule.last : ""
                  font.pixelSize: Tokens.caption
                  color: Tokens.fg3
                  wrapMode: Text.WordWrap
                  maximumLineCount: 3
                  elide: Text.ElideRight
                }
                Flow {
                  Layout.fillWidth: true
                  Layout.topMargin: Tokens.sp(4)
                  spacing: Tokens.sp(6)
                  ActionButton {
                    label: root.schedule.enabled ? "Change…" : "Set up…"
                    onActivated: root.scheduleRequested()
                  }
                  ActionButton {
                    visible: root.schedule.enabled
                    label: "Turn off"
                    onActivated: root.scheduleOffRequested()
                  }
                }
              }
            }
            Rectangle { Layout.fillHeight: true; width: 1; color: Tokens.line }

            // ---------------- main ----------------
            ColumnLayout {
              Layout.fillWidth: true
              Layout.fillHeight: true
              Layout.margins: Tokens.sp(18)
              Layout.topMargin: Tokens.sp(16)
              Layout.bottomMargin: Tokens.sp(14)
              spacing: Tokens.sp(14)

              SectionBanner {
                Layout.fillWidth: true
                section: root.section
                onGo: root.selectCheck(Status.focusCheck(root.checks))
              }

              RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Tokens.sp(16)

                Flickable {
                  id: listFlick
                  Layout.preferredWidth: Tokens.sp(310)
                  Layout.fillHeight: true
                  contentHeight: list.implicitHeight
                  clip: true
                  boundsBehavior: Flickable.StopAtBounds

                  ScrollHint { flick: listFlick }

                  // Rows keep a fixed height whatever their width, so room for
                  // the scroll hint is only taken when the list overflows.
                  Column {
                    id: list
                    width: listFlick.width - (listFlick.contentHeight > listFlick.height + 1 ? Tokens.sp(8) : 0)
                    spacing: Tokens.sp(6)
                    Repeater {
                      model: root.checks
                      delegate: CheckRow {
                        required property var modelData
                        required property int index
                        width: list.width
                        check: modelData
                        selected: index === root.checkIndex
                        onPicked: root.selectCheck(index)
                      }
                    }
                  }
                }

                DetailPane {
                  Layout.fillWidth: true
                  Layout.fillHeight: true
                  check: root.check
                  cursorAction: root.actionCursor
                  onActionActivated: function(index) { root.activateAction(index) }
                  onLinkActivated: function(url) { root.actionRequested({ url: url }, root.check.id || "", "") }
                }
              }
            }
          }

          // ---------------- footer ----------------
          Rectangle { Layout.fillWidth: true; height: 1; color: Tokens.line }
          RowLayout {
            Layout.fillWidth: true
            Layout.margins: Tokens.sp(8)
            Layout.leftMargin: Tokens.sp(18)
            Layout.rightMargin: Tokens.sp(18)
            spacing: Tokens.sp(18)

            Repeater {
              model: [["↑↓", "move"], ["←→", "actions"], ["Tab", "next section"], ["Enter", "do it"], ["S", "schedule"], ["Esc", "close"]]
              delegate: Row {
                required property var modelData
                spacing: Tokens.sp(6)
                KText { text: modelData[0]; font.pixelSize: Tokens.caption; font.bold: true; color: Tokens.fg2 }
                KText { text: modelData[1]; font.pixelSize: Tokens.caption; color: Tokens.fg3 }
              }
            }
            Item { Layout.fillWidth: true }
            KText {
              text: root.notice
              font.pixelSize: Tokens.caption
              color: root.notice !== "" ? Tokens.fg2 : Tokens.fg3
            }
          }
        }

        ConfirmSheet {
          id: confirmSheet
          anchors.fill: parent
          z: 10
          opened: root.confirmOpen
          plan: root.confirmPlan
          failed: root.confirmFailed
          snapshot: root.confirmSnapshot
          context: root.confirmContext
          onConfirmed: root.confirmAccepted()
          onCanceled: root.confirmCanceled()
          onSnapshotToggled: root.confirmSnapshotToggled()
          onOptionToggled: function(id) { root.confirmOptionToggled(id) }
          onAllToggled: root.confirmAllToggled()
        }

        ScheduleSheet {
          id: schedSheet
          anchors.fill: parent
          z: 10
          opened: root.schedOpen
          loading: root.schedLoading
          busy: root.schedBusy
          enabled: root.schedEnabled
          days: root.schedDays
          time: root.schedTime
          parts: root.schedParts
          onDayToggled: function(day) { root.schedDayToggled(day) }
          onEveryDay: root.schedEveryDay()
          onTimeStepped: function(m) { root.schedTimeStepped(m) }
          onPartToggled: function(part) { root.schedPartToggled(part) }
          onScanTargetChosen: function(t) { root.schedScanTargetChosen(t) }
          onSaved: root.schedSaved()
          onTurnedOff: root.schedTurnedOff()
          onCanceled: root.schedCanceled()
        }

        TrashSheet {
          id: trashSheet
          anchors.fill: parent
          z: 10
          opened: root.trashOpen
          title: root.trashTitle
          context: root.trashContext
          items: root.trashItems
          failed: root.trashFailed
          busy: root.trashBusy
          checked: root.trashChecked
          onToggled: function(id) { root.trashToggled(id) }
          onAllToggled: root.trashAllToggled()
          days: root.trashDays
          dayChoices: root.trashDayChoices
          onDaysChosen: function(d) { root.trashDaysChosen(d) }
          onIgnored: function(id) { root.trashIgnored(id) }
          onConfirmed: root.trashAccepted()
          onCanceled: root.trashCanceled()
        }
      }
    }
  }
}

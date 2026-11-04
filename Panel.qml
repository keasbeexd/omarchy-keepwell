import QtQuick
import Quickshell
import qs.Commons
import qs.Ui
import "ui" as K

// The bar's way into Keepwell: a shield that says, at a glance, whether
// anything needs you.
//
//   calm      outline shield in the bar's text colour
//   review    the same shield with a dot
//   act now   shield with "!" in the bar's alert colour
//
// The shape changes with the state, not just the colour, so it reads the
// same under a theme whose "urgent" is near-black or green. Colours are the
// bar's own roles: a bar may have its own ground (Turbo Pascal's is grey), and
// the window's accent and urgent are chosen against a different one.
//
// The window and the IPC route belong to the service (Service.qml); this is
// only the button.
BarWidget {
  id: root
  moduleName: "keasbeexd.keepwell"

  readonly property var service: bar && bar.shell && typeof bar.shell.serviceFor === "function"
    ? bar.shell.serviceFor(moduleName) : null

  // Shape contract for shell summon/hide/toggle routing.
  readonly property bool opened: service ? service.opened : false
  readonly property string worst: service ? service.worst : "good"
  readonly property string summary: service ? service.summary : ""

  // A replacement bar hands widgets a facade where serviceFor() answers null;
  // the service's own IPC target still works there.
  readonly property string shellBin: {
    var base = Quickshell.env("OMARCHY_PATH")
    return (base && base.length > 0 ? base : "/usr/share/omarchy") + "/bin/omarchy-shell"
  }
  function ipc(method) { Quickshell.execDetached([shellBin, "keepwell", method]) }

  function show() { if (service) service.show(); else ipc("show") }
  function hide() { if (service) service.hide(); else ipc("hide") }
  function open() { show() }
  function close() { hide() }
  function toggle() { if (service) service.toggle(); else ipc("toggle") }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    active: root.opened
    // A fixed vocabulary, so nothing variable reaches the host's tooltip.
    tooltipText: root.worst === "crit" ? "Keepwell — " + root.summary
      : root.worst === "attn" ? "Keepwell — " + root.summary
      : "Keepwell — all good"
    // Omarchy 4.5 measures what this draws and scales it to the bar's icon
    // size. It does not see a later change to the Glyph's internal scale, so
    // the size is fixed: taken from parent.width it starts at zero, the shield
    // measures as nothing, and the dot alone gets scaled up to fill the slot.
    iconComponent: Component {
      Item {
        K.Glyph {
          id: shield
          anchors.centerIn: parent
          size: 14
          strokeWidth: root.worst === "crit" ? 1.6 : 1.4
          name: root.worst === "crit" ? "shieldAlert" : "shield"
          color: root.worst === "crit" ? Color.bar.active : button.foreground

          // Held to the shield's top right corner rather than past it: every
          // measured part counts, so a dot outside would shrink the shield.
          Rectangle {
            visible: root.worst === "attn"
            width: 5
            height: width
            radius: width / 2
            x: shield.size * 13.5 / 16 - width
            y: shield.size * 1.5 / 16
            color: button.foreground
            border.width: 1
            border.color: Color.bar.background
          }
        }
      }
    }
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
    }
  }
}

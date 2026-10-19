pragma Singleton
import QtQuick
import qs.Commons

// Every colour, size and gap the window uses, derived from the active theme.
// Nothing here is a hex value: the palette is the shell's five roles, and the
// rest is those roles at fixed opacities, so any theme — light, dark,
// monochrome — renders the same hierarchy.
QtObject {
  id: root

  // ---------------- colour ----------------
  // The theme's own foreground/background pair, not a surface role: a theme
  // may give popups a different ground (Turbo Pascal's is a grey DOS dialog)
  // while accent and urgent are only chosen to read against `background`.
  readonly property color fg: Color.foreground
  readonly property color bg: Color.background
  readonly property color accent: Color.accent
  readonly property color urgent: Color.urgent

  // Secondary and tertiary text. Never the theme's `muted`: in several themes
  // it is a border shade that is unreadable as text (matte-black's is #333).
  readonly property color fg2: Util.alpha(fg, 0.74)
  readonly property color fg3: Util.alpha(fg, 0.56)

  readonly property color line: Util.alpha(fg, 0.12)
  readonly property color line2: Util.alpha(fg, 0.26)
  readonly property color fill: Util.alpha(fg, 0.04)
  readonly property color fill2: Util.alpha(fg, 0.08)
  readonly property color accentFill: Util.alpha(accent, 0.16)
  readonly property color urgentFill: Util.alpha(urgent, 0.12)
  readonly property color scrim: Qt.rgba(0, 0, 0, 0.45)

  function kindColor(kind) {
    if (kind === "crit") return urgent
    if (kind === "attn") return accent
    if (kind === "off") return fg3
    return fg2
  }

  function kindFill(kind) {
    if (kind === "crit") return urgentFill
    if (kind === "attn") return accentFill
    return fill
  }

  function kindBorder(kind) {
    if (kind === "crit") return urgent
    if (kind === "attn") return accent
    return line
  }

  // ---------------- type ----------------
  readonly property string font: Style.font.family
  readonly property int caption: Style.font.caption
  readonly property int small: Style.font.bodySmall
  readonly property int body: Style.font.body
  readonly property int subtitle: Style.font.subtitle
  readonly property int title: Style.font.title
  readonly property int heading: Style.font.heading

  // ---------------- shape and space ----------------
  readonly property int radius: Style.cornerRadius
  readonly property int hairline: Style.spacing.hairline
  readonly property int border: Math.max(1, Style.space(2))
  readonly property int controlHeight: Style.spacing.controlHeight
  readonly property int padX: Style.spacing.rowPaddingX
  readonly property int gap: Style.spacing.rowGap

  function sp(px) { return Style.space(px) }
}

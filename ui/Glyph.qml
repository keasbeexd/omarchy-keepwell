import QtQuick
import QtQuick.Shapes

// Stroke icons drawn from SVG paths on a 16-unit grid, so they follow the
// theme's colour and scale with the font without shipping image files or
// depending on which Nerd Font glyphs are installed.
Item {
  id: root

  property string name: "good"
  property color color: Tokens.fg
  property real size: Tokens.sp(16)
  property real strokeWidth: 1.5

  implicitWidth: size
  implicitHeight: size

  readonly property var paths: ({
    crit: "M5.3 1.5h5.4l3.8 3.8v5.4l-3.8 3.8H5.3l-3.8-3.8V5.3Z M5.8 5.8l4.4 4.4 M10.2 5.8l-4.4 4.4",
    attn: "M8 1.8L14.6 13.5H1.4Z M8 6v3.4 M8 11.4v.1",
    good: "M8 1.5a6.5 6.5 0 1 0 0.001 0Z M5 8.2l2 2 4-4.4",
    info: "M8 1.5a6.5 6.5 0 1 0 0.001 0Z M8 7.3v3.9 M8 4.9v.1",
    off: "M8 1.5a6.5 6.5 0 1 0 0.001 0Z",
    shield: "M8 1.5l5.5 2v4.2c0 3.3-2.3 5.7-5.5 6.8-3.2-1.1-5.5-3.5-5.5-6.8V3.5Z",
    shieldAlert: "M8 1.5l5.5 2v4.2c0 3.3-2.3 5.7-5.5 6.8-3.2-1.1-5.5-3.5-5.5-6.8V3.5Z M8 5v3.6 M8 10.8v.1",
    eye: "M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8Z M10 8a2 2 0 1 1-4 0a2 2 0 1 1 4 0Z",
    wrench: "M2 14l6.2-6.2 M9.5 2.3a3.2 3.2 0 0 0 4.2 4.2l-1.7 1.7-4.2-4.2Z",
    trash: "M2.5 4h11 M6 4V2.5h4V4 M3.8 4l.8 9.5h6.8l.8-9.5",
    back: "M10 3L5 8l5 5",
    tick: "M3.5 8.3l3 3 6-6.6",
    close: "M4 4l8 8 M12 4l-8 8"
  })

  Shape {
    width: 16
    height: 16
    preferredRendererType: Shape.CurveRenderer
    transform: Scale { xScale: root.size / 16; yScale: root.size / 16 }

    ShapePath {
      strokeColor: root.color
      strokeWidth: root.strokeWidth
      fillColor: "transparent"
      capStyle: ShapePath.RoundCap
      joinStyle: ShapePath.RoundJoin
      strokeStyle: root.name === "off" ? ShapePath.DashLine : ShapePath.SolidLine
      dashPattern: [1.6, 1.5]
      PathSvg { path: root.paths[root.name] || "" }
    }
  }
}

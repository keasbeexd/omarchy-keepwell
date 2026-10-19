import QtQuick

// A thin bar on the right edge of a Flickable that shows there is more below
// (and how much), drawn only when the content overflows. Declare it inside
// the Flickable; it re-parents itself out of the scrolling content, so leave
// Tokens.sp(8) of the content's width free for it.
Rectangle {
  id: root

  required property Flickable flick

  parent: flick
  visible: flick.contentHeight > flick.height + 1
  anchors.right: parent.right
  y: flick.visibleArea.yPosition * flick.height
  width: Math.max(2, Tokens.sp(3))
  height: Math.max(Tokens.sp(24), flick.visibleArea.heightRatio * flick.height)
  radius: width / 2
  color: Tokens.line2
}

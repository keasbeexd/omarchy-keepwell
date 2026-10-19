import QtQuick

// The one text element in the plugin. PlainText is fixed here so that no
// string — sample data now, tool output later — is ever read as markup.
Text {
  textFormat: Text.PlainText
  font.family: Tokens.font
  font.pixelSize: Tokens.body
  color: Tokens.fg
  wrapMode: Text.NoWrap
}

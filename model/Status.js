.pragma library

// The five states a check can be in, and how a list of them rolls up.
//
// Meaning travels in the shape and the word, never in hue alone: the shell
// gives a plugin only foreground, background, accent, urgent and muted, and
// some themes' "urgent" is near-black (white) or green (hackerman). So:
//   crit  octagon + "Act now"  — urgent colour
//   attn  triangle + "Review"  — accent colour
//   good  check circle + "OK"  — quiet
//   info  i circle + "Info"    — quiet
//   off   dashed circle + "Off" — dimmer still

var kinds = ["crit", "attn", "good", "info", "off"]

var labels = { crit: "Act now", attn: "Review", good: "OK", info: "Info", off: "Off" }

function label(kind) {
  return labels[kind] || ""
}

function isKind(kind) {
  return kinds.indexOf(kind) !== -1
}

// Healthy, informational and switched-off checks all roll up as "good": only
// a problem may raise the section's or the bar's state.
function worst(checks) {
  var w = "good"
  for (var i = 0; i < checks.length; i++) {
    if (checks[i].kind === "crit") return "crit"
    if (checks[i].kind === "attn") w = "attn"
  }
  return w
}

function counts(checks) {
  var c = { crit: 0, attn: 0 }
  for (var i = 0; i < checks.length; i++) {
    if (checks[i].kind === "crit") c.crit++
    else if (checks[i].kind === "attn") c.attn++
  }
  return c
}

function summary(checks) {
  var c = counts(checks)
  if (c.crit && c.attn) return c.crit + " to act on · " + c.attn + " to review"
  if (c.crit) return c.crit + " to act on"
  if (c.attn) return c.attn + " to review"
  return "All good"
}

// The check the section banner's button jumps to: the first one in the worst
// state, or for a healthy section the first informational one (cleanup).
function focusCheck(checks) {
  var w = worst(checks)
  var want = w === "good" ? "info" : w
  for (var i = 0; i < checks.length; i++)
    if (checks[i].kind === want) return i
  return 0
}

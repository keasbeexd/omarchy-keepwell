# Keepwell

*Keep your system well.*

An Omarchy shell plugin that brings security, privacy and system care into one
window, for people new to Linux. Keepwell is a frontend and a coordinator, not
a toolkit: wherever a maintained tool already does the job (ClamAV, UFW,
arch-audit, Flatseal, Snapper…), Keepwell shows its state in plain language and
hands you to it. The full design is in [docs/keepwell-spec.md](docs/keepwell-spec.md).

> **Status: preview build (0.1.0).** The window, bar icon and layout are
> complete, but every check shows **sample data** and no action does anything
> yet. Nothing is read from or written to your system. The footer says
> "Preview build · sample data" while this is true.

## What it looks like

- A shield in the bar: a plain outline when all is well, a dot when something
  wants a look, an exclamation mark when something needs action.
- Click it (or run `omarchy-shell keepwell toggle`) to open the window:
  Security, Privacy and System Care in a rail on the left, a one-line summary
  of the section, the list of checks, and the selected check explained.

Status is shown by shape and word, never by colour alone, so it reads the same
under every theme:

| State   | Shape          | Word    |
|---------|----------------|---------|
| Act now | octagon ✕      | ACT NOW |
| Review  | triangle !     | REVIEW  |
| OK      | circle ✓       | OK      |
| Info    | circle i       | INFO    |
| Off     | dashed circle  | OFF     |

All colours, fonts, spacing and corner rounding come from the active Omarchy
theme.

### Keyboard

| Key           | Does                          |
|---------------|-------------------------------|
| ↑ ↓ / j k     | move through checks           |
| ← → / h l     | move through a check's actions|
| Tab / Shift+Tab | next / previous section     |
| Enter         | run the selected (or primary) action |
| Esc           | leave the actions, then close |

## Installing

```bash
omarchy plugin add https://github.com/keasbeexd/keepwell.git --enable
```

The bar icon lands on the right of the bar; move it with
`omarchy bar move keasbeexd.keepwell --section <left|center|right>`.

## IPC

The plugin registers one IPC target, `keepwell`, with parameterless methods
only: `show`, `hide`, `open`, `close`, `toggle`. They open and close the window
and do nothing else.

```bash
omarchy-shell keepwell toggle
```

## What it touches

In this preview build: nothing outside its own directory. It runs no
commands, reads no files beyond its own QML, writes no files and makes no
network requests.

## Removing

```bash
omarchy plugin remove keasbeexd.keepwell
```

This removes the plugin directory and its bar entry. The preview build creates
no other files, so nothing is left behind.

## Licence

MIT — see [LICENSE](LICENSE).

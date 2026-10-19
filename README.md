# Keepwell

*Keep your system well.*

An Omarchy shell plugin that brings security, privacy and system care into one
window, for people new to Linux. Keepwell is a frontend and a coordinator, not
a toolkit: wherever a maintained tool already does the job (ClamAV, UFW,
arch-audit, Flatseal, Snapper…), Keepwell shows its state in plain language and
hands you to it. The full design is in [docs/keepwell-spec.md](docs/keepwell-spec.md).

> **Status: 0.2.0 — read-only.** Every check reads your real system, but
> Keepwell does not change anything yet: install, terminal and cleanup
> actions are shown and arrive in the next build (pressing one says so).

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

## When checks run

- Once when the shell starts, so the bar icon is meaningful.
- When you open the window, if the last result is more than a minute old.
- When you press **Check again**.

Nothing repeats on a timer. Every check is read-only.

## What it reads and runs

All of it happens in one helper, `bin/keepwell-check` (Python, standard
library only), run as `/usr/bin/python3 -I -S`. Each command runs from an
absolute path with a fixed environment, in its own process group, under a
deadline and an output cap; the helper prints one JSON document of at most
64 KiB.

| Check | Reads | Runs |
|---|---|---|
| Firewall | `/etc/ufw/ufw.conf`, `/etc/default/ufw`, `/etc/ufw/user*.rules` | `systemctl is-enabled/is-active ufw` |
| Known vulnerabilities | — | `arch-audit` (only when you ask — see Network) |
| Antivirus | modification times in `/var/lib/clamav`, `~/.clamtk/history` | `systemctl is-enabled/is-active clamav-freshclam`, `crontab -l` (ClamTK keeps its schedule there) |
| System updates | the last 1 MiB of `/var/log/pacman.log` | — |
| Camera & microphone | — | `pw-dump` |
| Browser telemetry | `~/.config/chromium/Local State`, `~/.config/chromium/Default/Preferences` (three keys); the names (`/proc/<pid>/comm`) of your own processes, to see whether Chromium is running | — |
| Data from your apps | `~/.config/Code/User/settings.json` (one key) | — |
| Activity traces | counts in `~/.local/share/recently-used.xbel`, `~/.bash_history`; size of `~/.cache/thumbnails` | — |
| App permissions | — | `flatpak list --app` |
| Cleanup | size of `~/.cache` | `paccache -d` (dry run), `pacman -Qtdq`, `pacman -Qi`, `journalctl --disk-usage` |
| Snapshots | `/etc/snapper/configs/root` | `systemctl is-enabled limine-snapper-sync` |
| Disk usage | free space on `/` | — |

Files in your home are opened without following symlinks, checked to be
regular files you own, and read only up to a size limit. Directory sizes
never follow symlinks and stop at an entry and time budget.

### Network

Only one check uses the network: **Known vulnerabilities** runs `arch-audit`,
which downloads Arch's public security data from
`https://security.archlinux.org`. It runs only when you press **Check now** on
that check or **Check again** in the header — never at startup or on opening
the window. Nothing else in Keepwell makes a network request.

### What it writes

Nothing. Keepwell creates no files.

## Removing

```bash
omarchy plugin remove keasbeexd.keepwell
```

This removes the plugin directory and its bar entry. Keepwell creates no other
files, so nothing is left behind.

## Licence

MIT — see [LICENSE](LICENSE).

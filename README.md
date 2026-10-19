# Keepwell

*Keep your system well.*

An Omarchy shell plugin that brings security, privacy and system care into one
window, for people new to Linux. Keepwell is a frontend and a coordinator, not
a toolkit: wherever a maintained tool already does the job (ClamAV, UFW,
arch-audit, Flatseal, Snapper…), Keepwell shows its state in plain language and
hands you to it. The full design is in [docs/keepwell-spec.md](docs/keepwell-spec.md).

> **Status: 0.3.0.** Every check reads your real system. Installs, firewall,
> updates, snapshots and cleanup work through a visible terminal, and caches
> and activity traces move to Trash (below). The privacy settings are shown
> and arrive in the next build (pressing one says so).

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
| Browser privacy policy | `/etc/chromium/policies/managed/*.json` | — |
| Network privacy | `/etc/hosts`, `/etc/avahi/avahi-daemon.conf`, whether `/etc/systemd/resolved.conf.d/no-fallback.conf` and `/etc/NetworkManager/conf.d/90-black-ops-*.conf` exist, whether `~/.local/state/omarchy-black-ops` exists | `systemctl is-active systemd-resolved NetworkManager avahi-daemon`, `systemd-analyze cat-config systemd/resolved.conf`, `NetworkManager --print-config`, `systemctl --user show-environment` (only `DO_NOT_TRACK` and `DEBUGINFOD_URLS` are kept) |
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

Keepwell creates no files of its own. Changes happen only through the
actions below: in a terminal after you confirm, or by moving what you tick
to the Trash.

## Actions

Anything that installs software or changes the system goes through one
script, `bin/keepwell-run`, in three steps:

1. **Confirm.** Keepwell shows what the action does and the exact commands,
   taken from `keepwell-run plan <action>` — the same table the terminal
   uses, so the dialog cannot show one thing and the terminal run another.
   Actions that install software offer a snapshot first.
2. **Terminal.** Keepwell steps aside and opens a floating terminal
   (`uwsm-app -- xdg-terminal-exec`, app-id `org.omarchy.terminal`) running
   `keepwell-run apply <action>`. It prints the commands again and waits for
   Enter; close the window to cancel. Each step runs from an absolute path
   after checking the program is a root-owned system file; the first failure
   stops the rest. Steps that need root use `sudo`, or an Omarchy command
   that calls it, so you type your password in the terminal — never in
   Keepwell. Nothing from the plugin's own directory runs as root.
3. **Back.** When that terminal window closes, Keepwell comes back on the
   same check, checks again and says what it found.

| Action | Commands |
|---|---|
| Install arch-audit, gitleaks, GufW, Flatseal, Disk Usage Analyzer | `omarchy pkg add <package>` |
| Install ClamAV | `omarchy pkg add clamav`, `sudo freshclam`, `sudo systemctl enable --now clamav-freshclam.service` |
| Turn on definition updates | `sudo systemctl enable --now clamav-freshclam.service` |
| Scan Downloads | `clamscan --recursive --infected -- ~/Downloads` (reports only) |
| Install UFW / Turn on the firewall | `omarchy pkg add ufw` (install only), `sudo ufw default deny incoming`, `sudo ufw default allow outgoing`, `sudo ufw enable` |
| Deny incoming | `sudo ufw default deny incoming` |
| Turn off the firewall | `sudo ufw disable` |
| Update the system | `omarchy update` |
| Take a snapshot | `omarchy snapshot create` |
| Clean up (you tick which) | `sudo paccache -r -k 3` (old versions, or `-k 1` for all but the newest), `sudo paccache -r -u -k 0` (downloads of removed packages), `sudo pacman -Rns -- <unused packages, listed>`, `sudo journalctl --vacuum-time=2weeks` |

The cleanup sheet measures each option first (`paccache -d`, `pacman -Qtdq`,
`journalctl --disk-usage`) and ticks only the safe ones; the commands update
as you tick, and the terminal runs exactly the ticked set.

### Moving things to Trash

App caches (folders directly inside `~/.cache`) and activity traces (the
recent-files list, `~/.bash_history`, `~/.cache/thumbnails`) are cleared
without root or a terminal. A sheet lists every item with its size, nothing
ticked; what you tick is moved with `gio trash`, one item at a time, so it
can be restored from the Trash. The space is freed when you empty the Trash.
Items are named by id, never by path: a cache item must be a plain name
directly inside `~/.cache` that you own, and traces come from a fixed list.

Opening an app (GufW, Flatseal, Disk Usage Analyzer, VS Code) runs
`uwsm-app -- <app>.desktop` and closes Keepwell.

ClamAV's definition updates download from ClamAV's servers, and package
installs download from your Arch mirrors; both happen only in the terminal,
after you confirm.

## Removing

```bash
omarchy plugin remove keasbeexd.keepwell
```

This removes the plugin directory and its bar entry. Keepwell creates no other
files, so nothing is left behind.

## Credits

The list of telemetry hosts and the set of Chromium privacy policies come from
[omarchy-black-ops](https://github.com/brightwalker25/omarchy-black-ops) by
brightwalker25 (MIT). Where Black Ops has applied a setting, Keepwell shows it
as "managed by Black Ops" and leaves it alone.

## Licence

MIT — see [LICENSE](LICENSE).

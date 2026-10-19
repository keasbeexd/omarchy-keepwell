# Keepwell

*Keep your system well.*

An Omarchy shell plugin that brings security, privacy and system care into one
window, for people new to Linux. Keepwell is a frontend and a coordinator, not
a toolkit: wherever a maintained tool already does the job (ClamAV, UFW,
arch-audit, Flatseal, Snapper…), Keepwell shows its state in plain language and
hands you to it. The full design is in [docs/keepwell-spec.md](docs/keepwell-spec.md).

> **Status: 0.5.0.** Every check reads your real system and every action
> works: installs, firewall, updates, snapshots, cleanup and the privacy
> settings through a visible terminal; virus and secrets scans in the
> background; caches and activity traces by moving them to the Trash.
> Scheduled background checks and the unclaimed-files finder come later.

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
- When you press **Check again**, and after an action's terminal closes.
- Every 15 seconds while a scan you started is running **and** the window is
  open, so you see it end. Nothing polls otherwise.

Every check is read-only.

## What it reads and runs

All of it happens in one helper, `bin/keepwell-check` (Python, standard
library only), run as `/usr/bin/python3 -I -S`. Each command runs from an
absolute path with a fixed environment, in its own process group, under a
deadline and an output cap; the helper prints one JSON document of at most
64 KiB.

| Check | Reads | Runs |
|---|---|---|
| Firewall | `/etc/ufw/ufw.conf`, `/etc/default/ufw`, `/etc/ufw/user*.rules` | `systemctl is-enabled/is-active ufw` |
| Known vulnerabilities | the last result Keepwell saved (`audit.json`, below) | `arch-audit` (only when you ask — see Network) |
| Antivirus | modification times in `/var/lib/clamav`; the newest of Keepwell's scan logs | `systemctl is-enabled/is-active clamav-freshclam`, `systemctl --user is-active keepwell-clamscan`, `crontab -l` |
| Secrets in your code | the last scan summary (`gitleaks.json`) | `systemctl --user is-active keepwell-gitleaks` |
| System updates | the last 1 MiB of `/var/log/pacman.log` | — |
| Camera & microphone | — | `pw-dump` |
| Browser telemetry | `~/.config/chromium/Local State`, `~/.config/chromium/Default/Preferences` (three keys); the names (`/proc/<pid>/comm`) of your own processes, to see whether Chromium is running | — |
| Browser privacy policy | `/etc/chromium/policies/managed/*.json` | — |
| Network privacy | `/etc/hosts`, `/etc/avahi/avahi-daemon.conf`, whether `/etc/systemd/resolved.conf.d/no-fallback.conf` and `/etc/NetworkManager/conf.d/90-black-ops-*.conf` exist, whether `~/.local/state/omarchy-black-ops` exists | `systemctl is-active systemd-resolved NetworkManager avahi-daemon`, `systemd-analyze cat-config systemd/resolved.conf`, `NetworkManager --print-config`, `systemctl --user show-environment` (only `DO_NOT_TRACK` and `DEBUGINFOD_URLS` are kept) |
| Data from your apps | `~/.config/Code/User/settings.json` (one key) | — |
| Activity traces | counts in `~/.local/share/recently-used.xbel`, `~/.bash_history`; size of `~/.cache/thumbnails` | — |
| App permissions | — | `flatpak list --app` |
| Cleanup | size of `~/.cache` | `paccache -d` (dry run), `pacman -Qtdq`, `pacman -Qi`, `journalctl --disk-usage` |
| Snapshots | `/etc/snapper/configs/root` (how many are kept) | `systemctl is-enabled limine-snapper-sync`; `journalctl -u limine-snapper-sync -g CREATE,ISDIR -n 1` — the snapshot list is root-only, but the boot-menu sync service logs each new snapshot's number, and the journal is readable without root |
| Disk usage | free space on `/` | — |

Files in your home are opened without following symlinks, checked to be
regular files you own, and read only up to a size limit. Directory sizes
never follow symlinks and stop at an entry and time budget.

### Network

Keepwell itself makes no network requests. Three things it starts do, only
when you ask:

- **Known vulnerabilities** runs `arch-audit`, which downloads Arch's public
  security data from `https://security.archlinux.org` (on **Check now** or
  **Check again** — never at startup or on opening the window).
- **Arch security tracker ↗** opens `https://security.archlinux.org/` in
  your browser (`xdg-open`).
- Installs download from your Arch mirrors, and ClamAV's definition updates
  from ClamAV's servers, in the terminal after you confirm.

### What it writes

Changes to your system happen only through the actions below: in a
terminal after you confirm, or by moving what you tick to the Trash. The
privacy settings are listed under [Removing](#removing).

Keepwell's own state lives in `~/.local/state/keepwell/`. Every path to it is
opened without following symlinks; the folder is kept at 0700 and its files
at 0600, written through a fresh temporary file and a rename.

| File | Holds |
|---|---|
| `pending.json` | the terminal Keepwell is waiting on (its Hyprland window address, the check and action), so a shell restarted meanwhile — `omarchy update` does that — still brings you back; removed when the terminal closes, ignored after a day |
| `audit.json` | the last arch-audit result you asked for: package names, severities, fix versions |
| `gitleaks.json` | the last secrets scan: the folder, how many repositories, and for each finding only the repository, file, line, rule name and commit — never the secret |
| `clamav/*.log` | ClamAV's scan logs, the newest ten; they list the paths of any infected files |

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
| Install arch-audit, gitleaks, GufW, Flatpak and Flatseal, Disk Usage Analyzer | `omarchy pkg add <package>` |
| Install ClamAV | `omarchy pkg add clamav`, `sudo freshclam`, `sudo systemctl enable --now clamav-freshclam.service` |
| Turn on definition updates | `sudo systemctl enable --now clamav-freshclam.service` |
| Install UFW / Turn on the firewall | `omarchy pkg add ufw` (install only), `sudo ufw default deny incoming`, `sudo ufw default allow outgoing`, `sudo ufw enable` |
| Deny incoming | `sudo ufw default deny incoming` |
| Turn off the firewall | `sudo ufw disable` |
| Update the system | `omarchy update` |
| Take a snapshot | `omarchy snapshot create` |
| Clean up (you tick which) | `sudo paccache -r -k 3` (old versions, or `-k 1` for all but the newest), `sudo paccache -r -u -k 0` (downloads of removed packages), `sudo pacman -Rns -- <unused packages, listed>`, `sudo journalctl --vacuum-time=2weeks` |

The cleanup sheet measures each option first (`paccache -d`, `pacman -Qtdq`,
`journalctl --disk-usage`) and ticks only the safe ones; the commands update
as you tick, and the terminal runs exactly the ticked set.

### Privacy settings

**Network privacy → Choose what to turn on** opens one sheet for seven
settings. Each shows its cost; ticking turns it on, unticking undoes it, and
the commands are exactly the difference. Keepwell only ever adds or removes
its own marked lines and files. A setting Black Ops applied, or one you set
by hand some other way, is not offered.

| Setting | What Keepwell writes | Then runs |
|---|---|---|
| Block telemetry hosts | a block between `# BEGIN keepwell…` and `# END keepwell` in `/etc/hosts` (the 14 hosts to `0.0.0.0` and `::`) | `sudo resolvectl flush-caches` |
| No backup DNS servers | `/etc/systemd/resolved.conf.d/90-keepwell-no-fallback.conf` (`FallbackDNS=`) | `sudo systemctl try-reload-or-restart systemd-resolved` |
| No connection check | `/etc/NetworkManager/conf.d/90-keepwell-connectivity.conf` (`enabled=false`) | `sudo systemctl reload NetworkManager` |
| Private network identity | `/etc/NetworkManager/conf.d/90-keepwell-identity.conf` (stable per-network MAC, no DHCP hostname, IPv6 privacy addresses) | `sudo systemctl reload NetworkManager` |
| Don't announce this computer | in `/etc/avahi/avahi-daemon.conf`'s `[publish]` section: a `# keepwell:` marker line and `disable-publishing=yes` below it (an existing uncommented `disable-publishing` line is kept, commented as `#keepwell-was:`) | `sudo systemctl try-restart avahi-daemon` |
| No debug symbol lookups | `~/.config/uwsm/env.d/90-keepwell-debuginfod` (`export DEBUGINFOD_URLS=`) | `systemctl --user set-environment DEBUGINFOD_URLS=` |
| Send Do Not Track | `~/.config/uwsm/env.d/90-keepwell-do-not-track` (`export DO_NOT_TRACK=1`) | `systemctl --user set-environment DO_NOT_TRACK=1` |

**Browser telemetry → Apply privacy policy** installs
`/etc/chromium/policies/managed/keepwell-privacy.json` with the 14 policies
(it is shown in full first); **Remove privacy policy** deletes it.

Files under `/etc` are written with `sudo install … /dev/stdin <path>`, so
their contents go through standard input, never the command line, and are
shown before you press Enter. `/etc/hosts` and `avahi-daemon.conf`, which
belong to other packages, are rewritten through a fresh sibling file and a
rename; the dialog shows the exact change as a diff, and after the rename
Keepwell reads the file back and puts the original bytes back if it doesn't
match. Undoing removes exactly Keepwell's lines and restores the file as it
was.

### Background scans

Virus and secrets scans can take a long time, change nothing, and need no
root, so they don't use a terminal. Each runs as a transient user service
that is independent of the shell (a restart doesn't stop it), at idle CPU
and disk priority, one of each kind at a time:

```bash
systemd-run --user --quiet --collect --unit=keepwell-clamscan.service \
  --property=Nice=19 --property=IOSchedulingClass=idle \
  --property=ExecStopPost=/usr/bin/notify-send --app-name=Keepwell "Virus scan ended" "…" \
  -- /usr/bin/clamscan --recursive --infected --log=<new log> [--exclude-dir=…] -- <folder>
```

- **Scan Downloads** scans `~/Downloads`; **Scan home folder** scans `~` but
  skips `~/.cache`, `~/.local/share/Trash` and Keepwell's own logs. A home
  scan can take half an hour or more.
- **Choose a folder…** (Secrets in your code) opens a folder picker
  (`zenity --file-selection --directory`, which Omarchy shows through the
  desktop portal). Keepwell steps aside while it is open. In the folder you
  pick it finds git repositories up to four levels down, never through a
  symlink, at most 100, and runs
  `gitleaks git --redact --report-format json --report-path - -- <repo>` on
  each in the `keepwell-gitleaks` service. Only locations are kept (see
  `gitleaks.json` above).
- **Stop scan** runs `systemctl --user stop` on that service.
- When a scan ends (or is stopped), one desktop notification says so.
  Keepwell deletes, moves or changes nothing it finds; infected files are
  listed for you to decide on.

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

This removes the plugin directory and its bar entry. It does not remove
Keepwell's state folder, `~/.local/state/keepwell/` (described under
[What it writes](#what-it-writes)): it holds scan logs that name infected
files, the locations of possible secrets, and the last vulnerability result.
Delete that folder yourself if you don't want to keep them.

A scan that is running carries on until it ends, even after removal; stop it
first with **Stop scan**, or with
`systemctl --user stop keepwell-clamscan.service keepwell-gitleaks.service`.

**Privacy settings you turned on stay in effect after removal.** Untick them
in Keepwell first (Network privacy → Change settings, Browser telemetry →
Remove privacy policy) to undo them cleanly. If the plugin is already gone,
these are everything Keepwell can have written:

| File | Undo by hand |
|---|---|
| `/etc/hosts` block from `# BEGIN keepwell…` to `# END keepwell` | delete those lines with `sudoedit /etc/hosts` |
| `/etc/systemd/resolved.conf.d/90-keepwell-no-fallback.conf` | `sudo rm` it, then `sudo systemctl restart systemd-resolved` |
| `/etc/NetworkManager/conf.d/90-keepwell-connectivity.conf`, `90-keepwell-identity.conf` | `sudo rm` them, then `sudo systemctl reload NetworkManager` |
| `/etc/avahi/avahi-daemon.conf`: each `# keepwell:` line and the line after it; a `#keepwell-was: ` prefix | `sudoedit` the file: delete those pairs, strip the prefix, then `sudo systemctl try-restart avahi-daemon` |
| `/etc/chromium/policies/managed/keepwell-privacy.json` | `sudo rm` it |
| `~/.config/uwsm/env.d/90-keepwell-debuginfod`, `90-keepwell-do-not-track` | `rm` them; they stop applying at the next login |

Packages Keepwell installed for you (arch-audit, ClamAV, gitleaks, GufW,
Flatseal, Disk Usage Analyzer, UFW) are ordinary packages and stay installed;
ClamAV's `clamav-freshclam` service stays enabled if you turned it on. Items
moved to the Trash stay there until you empty it.

## Credits

The list of telemetry hosts, the set of Chromium privacy policies and the
network privacy settings are adapted from
[omarchy-black-ops](https://github.com/brightwalker25/omarchy-black-ops) by
brightwalker25 (MIT). Where Black Ops has applied a setting, Keepwell shows it
as "managed by Black Ops" and never changes it.

## Licence

MIT — see [LICENSE](LICENSE).

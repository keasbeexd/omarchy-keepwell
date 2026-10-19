# Keepwell — Plugin Specification

**Plugin ID:** `omarchy.keepwell`
**Tagline:** *Keep your system well.*
**Status:** Approved plan, not yet implemented.

---

## 1. Purpose & audience

Keepwell is a dashboard plugin for Omarchy (Quattro/Quickshell shell) that helps new Linux users — especially those coming from Windows — handle three things in one place:

1. **Security** — antivirus, firewall, and vulnerability awareness
2. **Privacy** — app permissions, telemetry, camera/mic visibility, activity traces
3. **System Care** — disk cleanup, unclaimed-file review, disk usage, snapshots

It is deliberately **a frontend and coordinator, not a toolkit**. Wherever a maintained, standard tool exists, Keepwell detects it, explains it in plain language, installs it on request (`omarchy pkg add`), and launches it. Keepwell builds exactly one new capability: the cleanup/unclaimed-files previewer, for which no maintained GUI exists.

### Design principles

- **Never reinvent a wheel that exists.** One tile per standard tool; Keepwell orchestrates, the tool does the work.
- **Never leave the platform unnecessarily.** Settings that the counterpart app owns are changed through (or displayed from) that app's own config; only tools with no scheduling/config mechanism use Keepwell's own.
- **Nothing destructive without a preview and explicit consent.** Every removal shows exactly what goes, with sizes, before it happens. Recoverable actions preferred (`gio trash` over `rm`).
- **Nothing runs in the background unless the user turns it on.** All timers off by default.
- **Privileged steps run in a visible terminal** showing the exact commands — never hidden `pkexec`, never code elevated from the checkout (marketplace hard requirements).
- **Honest claims.** README, manifest, and behavior must match exactly; every external endpoint disclosed. No fear-mongering; antivirus on Linux is framed honestly.

---

## 2. Structure

A panel widget with three tabs (Security / Privacy / System Care), each a Windows-Security-style status board: green/amber/red tiles, one-click actions behind them, and a plain-language explanation before any action runs.

| Feature | Does the work | Keepwell does |
|---|---|---|
| Antivirus | ClamAV + ClamTK | detect, guided install, status, scheduling via counterpart adapters, launch |
| Definitions scheduler | `clamav-freshclam.service` | parse/drove via systemd, visible terminal |
| Firewall | UFW + GufW | read-only status tile, guided install, launch |
| CVE advisory | **arch-audit** | run, group by severity, refresh |
| Secrets scan | gitleaks | opt-in repo-folder scan, read-only report |
| Dependency vulns | osv-scanner | opt-in project-dir scan ("for developers" badge) |
| App permissions | Flatseal | launch + explainer templates |
| Camera/mic | PipeWire | read-only indicators |
| Browser telemetry | Chromium/Firefox prefs | posture display + confirmed, validated toggles |
| App telemetry | per-app opt-outs | reporter card + safe toggles / guided links |
| Activity traces | GTK/shell standard files | checkbox cleaner, `gio trash` |
| Package cleanup | paccache / pacman | scan, size preview, execute in visible terminal |
| Unclaimed files | — (no tool exists) | **the one new wheel** — see §5.3 |
| Cache | `~/.cache` breakdown | select-and-trash |
| Snapshots | `omarchy-snapshot` (Snapper+Limine) | safety-net tile, cross-link existing `omarchy-snapshots` plugin |
| Disk usage | Omarchy's default app | launch via detected `.desktop`, fallback baobab |
| Updates | `omarchy update` | status tile only; never scheduled |

---

## 3. Security tab

### 3.1 Antivirus — ClamAV + ClamTK

- Detect `clamav`/`clamtk`; missing → guided `omarchy pkg add clamav clamtk` with an honest framing of what AV on Linux does and doesn't do.
- Status: definitions age, last scan (parsed from ClamTK state), timer enabled/active.
- Launch ClamTK for interactive/deep scans — never reimplement scanning.
- **Scheduling goes through the counterpart:**
  - Definitions: enable/disable `clamav-freshclam` (system unit) → explicit user action, visible terminal.
  - Scheduled scans: **ClamTK's own scheduled-scan store** (`~/.clamtk/nvdata`, flat key-value: frequency/day/hour). Keepwell parses and renders this schedule in its UI. Changes via explicit confirmation dialog only: backup the file, write only known ClamTK keys, validate, roll back on failed write. Ownership styling in the UI: "managed by ClamTK."
- Default scope if user enables a scan timer: `~/Downloads`. Folder picker provided.

### 3.2 Firewall — UFW + GufW

- Read-only status check: on/off, default policy.
- One labeled switch Off→"deny incoming, allow outgoing" default, and vice versa; confirm dialog shows the exact `sudo ufw` command; runs in a visible terminal.
- Rule editing delegated to GufW ("Configure" button).

### 3.3 Vulnerability & secrets (new section)

- **arch-audit tile** ([extra], no AUR): runs `arch-audit`, groups findings by severity, green/amber/red tile. Manual refresh; optional weekly scheduled refresh.
- **gitleaks** ([extra], opt-in): user picks a folder of git repos → secrets-exposure report. Bounded helper: repo count cap, time budget. Read-only.
- **osv-scanner** ([extra], scoped): "Developer extras" badge, hidden by default. Project-directory lockfile scan.
- Rejected for bloat: Trivy, Perplexity's Bumblebee — arch-audit is the lean fit.

### 3.4 Passwords

Dropped by decision. A password keeper is the user's responsibility; no tile.

---

## 4. Privacy tab

### 4.1 App permissions — Flatseal

- Launch Flatseal; explainer with per-template guidance (banking app vs. game vs. browser), plain definitions of each permission.

### 4.2 Camera & microphone — PipeWire

- Read-only indicators for device use; "who's using it" list; hardware kill-switch reminder card. No mutation.

### 4.3 Browser telemetry — adjustable via confirmation

Chromium first (Omarchy default), Firefox second. Design:

- **Display:** privacy posture tile parsed read-only (metrics on/off, crash reporting).
- **Changes:** confirmation dialog lists the exact keys and values before anything is written, e.g. Chromium `metrics.reporting_enabled: false`, safe-browsing opt-down, search suggestions.
- **Hard rails, enforced in code:**
  - Browser-process detection -> refuse to write while running (browser overwrites Preferences on exit; this check is not optional).
  - Backup Preferences/Local State beside the original before each write.
  - JSON schema validation of the edit; atomic same-directory temp + rename; rollback to prior bytes on any failure.
  - Touch **only telemetry keys** — never a generic "hardening" pass; never re-list or refactor user prefs.
- Firefox: same treatment on `prefs.js`, or the offer of policy-file route (root, visible terminal) as the robust alternative.

### 4.4 Data from your apps (new card)

- **Reporter:** identifies installed apps known to phone home or gather identifiers, and shows per-app opt-out state where readable.
- Mechanically safe toggles (Chromium-class) use the §4.3 confirmed-write path. Everything else gets a guided card (explain + deep-link the app's own settings). No invented behavior for apps we don't understand.
- Honest README line: "Arch itself sends nothing; telemetry comes from the apps you install." Keeps claims code-matched.

### 4.5 Activity traces cleaner

- Checkbox list: `~/.recently-used` (GTK recent files), shell history, `~/.thumbnails`, trash.
- Per-item confirmation; deletion via `gio trash` only (recoverable); never automated or bundled into timers.

---

## 5. System Care tab

### 5.1 One-click cleanup (with full preview)

Scan and report exact reclaimable space per item:

- Package cache (`paccache` dry-run data)
- Orphaned packages (`pacman -Qtdq`) → preview → explicit confirm → `sudo pacman -Rns` in visible terminal
- `~/.cache` top-level subdir sizes → select-and-trash; safe exclusions defaulted
- Journal logs (`journalctl --vacuum-time` / `--vacuum-size`) with shown before/after sizes

Tiers: **Safe** (defaults) vs. **Advanced** (opt-in per item). Deletion executes only well-known package-manager commands or bounded trash workflows — no globs, no `rm -rf`, no touching other apps' or plugins' state.

### 5.2 Snapshot safety net

- Tile: Snapper alive + Limine sync state (read-only checks).
- Pre-cleanup button: `omarchy-snapshot create` in a visible terminal; explain restore is via Limine boot menu, root-only (not `/home`).
- Deep management (diffs, pinning, rollback UI) is owned by the existing `omarchy-snapshots` community plugin — **cross-link, don't compete.**

### 5.3 Unclaimed-files finder — the one new wheel

For "files nothing claims anymore" that no existing GUI tool handles well:

- Helper builds the platform-owned path set once from `pacman -Qlq` (bounded, cached in plugin state, invalidated by pacman database mtime).
- Walks `~` shallowly: depth 1–2, no symlink traversal, hard entry budget (~2000) and time budget.
- Candidate rules: **not owned by any package** AND mtime age ≥ threshold AND not matched by the ignore list (plugin state, browser profile internals, `node_modules`, `.local/share/pipx`, etc.).
- **Adjustable:** site-wide age threshold slider (default 180 days) + per-folder overrides. "Suggest + trash + adjustable" policy per user decision.
- **Presentation:** candidates only — "verify before removing" copy, each row shows path / size / last-modified / owning-package ("none"). Nothing is deleted automatically, ever.
- **Deletion:** per-item or multi-select, through `gio trash` only (recoverable). New-appearing config dirs are exactly why nothing runs unattended.

### 5.4 Disk usage

- Launch Omarchy's shipped default (detected from installed `.desktop` files); fallback baobab.
- Short "what's normal vs. worth cleaning" cheat sheet linking back to §5.1.

### 5.5 Maintenance timers

- Same **fallback-scheduler engine** as §3.1, emitting cleanup-scan report or "updates available" notifications — this engine is used **only** for arch-audit refresh and this section; every tool with a native scheduler is driven through that native path instead (§3.1 counterpart adapters).
- Off by default; checkbox grid for day/time; notification says what it found and asks, never acts.

---

## 6. Scheduling philosophy (summary)

Counterpart first, translation second, own engine last:

| Feature | Scheduler owner | Mechanism |
|---|---|---|
| ClamAV definitions | ClamAV/systemd | enable/disable `clamav-freshclam` (visible terminal) |
| ClamAV scans | ClamTK | parse `~/.clamtk/nvdata`; write with backup + rollback, confirmed |
| Updates | user habit / omarchy | no scheduler; status tile only |
| arch-audit, cleanup report | Keepwell (fallback engine) | plugin-owned systemd user timer, off by default |

Display rule: wherever a counterpart schedule exists, the tile says "managed by ClamTK" (etc.) so ownership is visible. Never two schedulers racing silently.

---

## 7. Defaults (summary)

- All timers: **off**.
- ClamAV scan scope if enabled: `~/Downloads`.
- Cleanup tiers: Safe defaults only.
- Unclaimed-file age threshold: 180 days, adjustable.
- Wedges hidden by default: osv-scanner (Developer extras badge).
- Nothing writes shared config without an explicit confirmation dialog + backup + rollback path.

---

## 8. Marketplace alignment (must-haves, translated)

Every tile helper is a bounded process: argv-array commands only (no shell-string interpolation), absolute `/usr/bin` paths, producer-side output caps (`LC_ALL=C`, `head -c $((MAX+1))`, pipefail), full deadlines plus process-group teardown, `textFormat: Text.PlainText` on every QML sink, sanitized/length-capped strings into any host component or notification, no secrets in argv, plugin-owned state files (0700 dir / 0600 files, atomic writes), sibling-component files read or written only with explicit consent + proof + restore, no agent-instruction files in the installable tree, README-code parity audited, exact removal section listing every artifact and the `omarchy plugin remove omarchy.keepwell` command.

---

## 9. Deliberately rejected

| Idea | Why |
|---|---|
| Trivy / Perplexity Bumblebee | bloat; arch-audit is the lean fit |
| Password manager integration | user responsibility |
| Own AV scanner/scheduler | ClamAV/ClamTK counterpart adapters instead |
| Snapshot UI | exists as `omarchy-snapshots` plugin |
| Telemetry "hardening" bundles | per-key confirmed changes only |
| Auto-executing cleanup on a timer | preview + confirm always; timers may *report*, never act |

---

## 10. Open items for implementation phase

1. Verify exact `arch-audit` output format (JSON vs. human) chosen for parsing, and worth of `--severity` filtering.
2. Confirm Omarchy's default disk-usage `.desktop` name/appearance for detection.
3. ClamTK `nvdata` exact key names for scheduled scans — verify against current ClamTK version before coding the adapter.
4. Chromium `Local State` vs. `Preferences` file responsibility per key (crash/metrics split).
5. Decide cross-link behavior with `omarchy-snapshots` (launch? button-as-link? README mention only).

---

## 11. Amendments (2026-10-19)

1. **Plugin ID** is `keasbeexd.keepwell`: the shell rejects third-party IDs in the reserved `omarchy.*` namespace.
2. **ClamTK dropped.** ClamTK is no longer maintained (its README says so), and its scheduler writes user-crontab lines (`# clamtk-scan`, `# clamtk-defs`), not `~/.clamtk/nvdata` — and Omarchy ships no `crontab`. Keepwell offers ClamAV alone: definitions via `clamav-freshclam`, scans run from Keepwell in a visible terminal. §3.1's ClamTK adapter and §6's ClamTK row no longer apply.
3. **Checks at shell start** — one local, read-only check so the bar icon is meaningful; arch-audit (network) only on explicit request.
4. **Network privacy (new, Privacy tab)** — six optional settings adapted from omarchy-black-ops: telemetry hosts in `/etc/hosts`, empty `FallbackDNS`, NetworkManager connectivity check off, private MAC + no DHCP hostname, Avahi publishing off, debuginfod off. Plus the Chromium managed privacy policy (on the Browser telemetry check) and `DO_NOT_TRACK` (on Data from your apps). Shown as Info, never as a problem. Settings Black Ops applied are shown as "managed by Black Ops" and never touched. Black Ops' watchdog and listen mode are out of scope.
5. **Snapshots** — `snapper list` and `/.snapshots` are root-only, so the tile shows setup and Limine sync state only; the count is left to the `omarchy-snapshots` plugin.
6. **Scans run in the background** (2026-10-19): ClamAV and gitleaks scans run as transient `systemd-run --user` services at idle priority with a notification when they end, instead of in a terminal — they are read-only and need no root, and a home-folder scan can take half an hour. Keepwell keeps its own ClamAV logs (`~/.local/state/keepwell/clamav/`) for "last scan".
7. **arch-audit presentation**: only a released fix is actionable. Issues with no fix yet are shown with their kind in plain words and "no fix released yet", as Info — never as something to act on.
8. **State directory** `~/.local/state/keepwell/` (0700): `pending.json` (survives the shell restart that `omarchy update` causes), `audit.json`, `gitleaks.json` (locations only, never secrets), `clamav/*.log`.
9. **Snapshots**: the last snapshot's number and time come from the `limine-snapper-sync` journal ("CREATE,ISDIR -> N"), which needs no root.
10. **Unclaimed-files finder (§5.3) — claim by name, not by pacman file list.** `pacman -Qlq` lists no paths under `~`, so "not owned by any package" is true of everything there. Keepwell instead treats a folder as claimed when its name matches (exactly, or by prefix either way) an installed package, a program in `/usr/bin`/`~/.local/bin`/mise shims, a desktop or Flatpak app, a folder Omarchy's files mention or ship, or a standard XDG location. Candidates must also be untouched for the chosen age (90/180/365/730 days). The claim set is cached and rebuilt when pacman's database changes, as the spec intended. Per-folder overrides are "Ignore".
11. **Background checks (§5.5)**: a persistent user timer (`~/.config/systemd/user/keepwell-report.{timer,service}`, marked as Keepwell's, removed on Turn off) on the days of the week and time the user picks (30-minute steps), off by default. A run can include the arch-audit check, the cleanup report and a ClamAV scan of Downloads or home (replacing the ClamTK schedule adapter of §3.1). One notification per run; nothing is ever acted on.
12. **Dependency vulnerabilities (§3.3) in the Security tab**, not behind a hidden "Developer extras" switch: the user wanted it visible, with the information made worth having — per vulnerable library: worst severity, CVEs, summary, the version that fixes all its issues, and where it lives; rows link to osv.dev. Same home/choose-folder and background-scan model as gitleaks. Online mode (OSV.dev API), disclosed on the card and in the README.
13. **Always-on checks and scheduled deep scans (supersedes 6, 11)**: the quick checks (every check except the deep scans, including arch-audit) run by themselves at login and hourly while logged in, and notify once when a check newly needs attention — the one deliberate exception to "nothing runs in the background unless you turn it on", stated in the UI and README. arch-audit's ~900 KB download is skipped hourly on a metered connection; when the tracker can't be reached the last result stays, marked. The deep scans (virus Downloads/home, secrets, dependencies) have one opt-in schedule (`keepwell-deep.timer`). A scheduled run that would start more than 10 minutes late — computer off, suspended or hibernating — is recorded as missed (shield, one notification, a strip with Run now/Dismiss), never run late. One summary notification per run; scans skipped on battery by default.
14. **Remote access (Security) and Failed services (System Care)** (2026-10-19). Remote access reads whether an SSH server is installed, running or enabled, and its effective password and root-login settings (`sshd_config` plus drop-ins, first value wins); passwords on is Review, root by password Act now, keys only or no server OK. Actions: turn SSH off, or allow keys only through a marked drop-in that is tested with `sshd -t` and removed if the test fails — offered only once `authorized_keys` holds a key, so nobody locks themselves out. Failed services lists failed system and user units as Info, never a problem (some fail harmlessly on every boot); actions show their status in a terminal or clear the list (`reset-failed`), never restart anything.
15. **Software outside updates (Security)** (2026-10-19). omarchy update covers the official repositories, the AUR (`yay -Sua`) and mise; this check lists what it misses: compiled programs and AppImages installed by hand, foreign packages the AUR no longer has (so yay can't update them), `cargo install`/`go install`/pipx/uv tools, and Flatpak apps. Info, except Review when a hand-installed program hides a packaged one of the same name. Telling an AUR package from a self-built one needs the AUR's answer, so this adds Keepwell's own network request: one capped HTTPS request to the AUR RPC carrying only the foreign package names, with the hourly checks at most every six hours and never on a metered connection; the answer is cached in `aur.json`. One action: Update Flatpak apps.

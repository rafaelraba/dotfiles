# Portable Pi, Fish and Omarchy desktop configuration

A reviewed snapshot of Pi preferences/resources, local skills (with supporting files), Fish startup, Starship, Hyprland and the Herdr app. Restore copies owned files only; it never installs dependencies, deletes unrelated files, or restores credentials.

## Quick start

Clone the primary repository into a hidden local folder:

```sh
git clone https://github.com/rafaelraba/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
python3 restore.py                          # Preview only: no destination writes
python3 restore.py --apply                  # Restore to your current home
```

The repository name is `dotfiles`; the local `.dotfiles` folder is hidden by convention. The previous macOS/dotly setup and its history are preserved separately at [dotfiles-macos](https://github.com/rafaelraba/dotfiles-macos). This Pi/Fish snapshot does not restore that macOS desktop setup.

Alternatively, transfer this entire directory as `dotfiles/` and run `python3 dotfiles/restore.py` from its parent; add `--apply` only after reviewing the preview.

For an isolated preview or another username:

```sh
python3 dotfiles/restore.py --home '/tmp/my test home'
python3 dotfiles/restore.py --home '/tmp/my test home' --apply
```

Python 3.9+ is sufficient for restoration. Linux is the intended target. Install Fish and optionally Starship separately using your machine's package manager. The prompt uses Nerd Font glyphs; a missing font affects display, not restoration. Starship is guarded when unavailable. Restart Fish after restoring.

**This restores configuration, not a ready-to-run authenticated Pi installation.** Complete the separate dependency and login steps below before starting Pi. Do not run capture or restore while another process is editing the same files.

## Install dependencies separately (explicit network opt-in)

After restoring, use Node.js **22.19+** and npm. Review third-party packages before installing them. These commands are instructions, not commands run by restore:

```sh
npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.5.2
pi update --extensions
```

`pi update --extensions` reconciles the pinned declarations already restored in `~/.pi/agent/settings.json`. Plain `pi update` updates Pi itself; it is **not** the package reinstall command. Package pins were read from installed metadata:

| Package | Version |
|---|---|
| pi-web-access | 0.47.0 |
| pi-btw | 0.8.1 |
| pi-claude-bridge | 0.12.0 |

Direct install alternatives are `pi install npm:pi-web-access@0.47.0`, `pi install npm:pi-btw@0.8.1` and `pi install npm:pi-claude-bridge@0.12.0`. Reconciliation is preferred because it preserves settings filters. No MCP servers are configured (`mcp.json` is empty). No dependency installation or network connectivity was tested here.

Run `/login` in Pi to authenticate again and select an available model if the saved model is unavailable to your account. If future capture redacts credential fields, `manifest.json` lists their key paths and replaces string fields with `${VARIABLE_NAME}` placeholders; supply the corresponding variables privately, never commit them.

## What is included

| Resource | Portable treatment |
|---|---|
| Pi settings, keybindings, `omarchy-system` theme, empty `mcp.json` | Package sources pinned; paths relative to the agent directory |
| Pi extensions (`herdr-agent-state`, `moshi-hooks`, `statusline`) | Copied as-is; Herdr/Moshi integrations stay inactive without their environment |
| `~/.agents/skills` | Local source skills copied recursively; package skills remain package dependencies |
| Omarchy, omarchy-app and diagnose-crash skills | Dereferenced into ordinary skill directories with their supporting Markdown; no host symlinks |
| Fish and Starship | Startup plus reviewed empty `fish_greeting`; no universal-variable dump |
| Aliases | Reviewed portable subset of Omarchy Bash defaults translated to Fish in `conf.d/20-portable-aliases.fish` |
| Hyprland (`~/.config/hypr`) | `hyprland.lua`, `autostart.lua`, `bindings.lua`, `input.lua`, `looknfeel.lua`, `monitors.lua`, `hyprsunset.conf`, `xdph.conf` |
| Herdr app (`~/.config/herdr-app`) | Personal files only: `keys.json`, `settings.json`, `programs.json`, layouts and mods not listed in Herdr's `installed.json` (code, `mod.json`, SVG icons, licenses). Shipped mods/layouts, generated `.d.ts`/`jsconfig.json`, binaries, backups and app state are left out; Herdr regenerates them |
| Omarchy (`~/.config/omarchy`) | `shell.json`, menu extension, branding, `defaults/{agent,dictation}`, personal hooks (`install-voxtype`, `setup-agent`, `setup-fingerprint`, `10-owe-sync`) and per-theme backgrounds (images). Shipped `*.sample` files and git-cloned themes are left out |
| Terminals and tools | `alacritty.toml`, `ghostty/config`, `git/{config,ignore}`, `herdr/{config.toml,plugins.json}`, `btop.conf`, `mise/config.toml`, `voxtype/config.toml`, `input-remapper-2` (config + presets), `environment.d`, `mimeapps.list` |
| Neovim (`~/.config/nvim`) | LazyVim config, plugins and `lazy-lock.json`; Lazy reinstalls plugins on first start |
| systemd user units | `voxtype.service`, `moshi-hook.service`, Ghostty override. Enablement links are not restored (see below) |

Pi discovers `~/.agents/skills` natively; settings also explicitly list `../../.agents/skills` relative to `~/.pi/agent`. The duplicate live Omarchy links in `~/.pi/agent/skills` are intentionally not recreated. Package-provided skills are installed by the pinned Pi packages, not copied from node_modules. Omarchy/crash skill instructions remain available elsewhere, but their system-specific commands still require Omarchy/Linux/systemd tools. They are not a desktop backup.

Fish autoload shortcuts in `~/.config/fish/functions/` make `nvim` without arguments run `command nvim .` and `h` run `command herdr`. Explicit arguments and exit statuses are preserved; the existing `n` shortcut remains unchanged. Neovim and Herdr must be installed separately. Capture includes this functions directory, so future refreshes retain the live shortcuts.

`fish_user_key_bindings.fish` rebinds Ctrl+L to `clear -x` plus a prompt repaint: Fish 4's default (scrollback-push) does not clear in Herdr terminals. The binding lives in that function, not `config.fish`, because Fish erases `config.fish` bindings when it reloads key bindings.

At initial capture, Fish had no personal alias functions, abbreviations, or binding files. Its only universal variable was the empty greeting. `.bashrc` had no personal overrides and sourced Omarchy defaults. Portable aliases include directory traversal, Git, optional eza/Docker/Rails/tmux/nvim, and Linux `xdg-open`. Desktop/agent launchers, automatic approval aliases (`cx`, `cy`), mise update shortcuts, fzf/editor/zoxide helpers, and distribution Bash functions/completions/inputrc are intentionally omitted. Bash itself is not restored.

Known resource-path tokens are translated to `~/.agents/...` or `~/.pi/...`; arbitrary home substrings are not rewritten. Unknown `/home/...` or `/Users/...` paths cause capture to fail for review. Script code is not generically templated.

## After restoring on a new Omarchy machine

Steps restore cannot do for you:

```sh
omarchy theme install https://github.com/bjarneo/omarchy-aura-theme   # aura theme (git clone)
systemctl --user daemon-reload
systemctl --user enable --now moshi-hook.service owed.service bt-agent.service
hyprctl reload
```

- `moshi-hook` expects its binary at `~/.local/bin/moshi-hook`; `voxtype.service` is restored but left disabled, as on the original machine.
- Neovim's `mdscope.lua` loads a local plugin from `~/Code/mdscope.nvim`; clone it there or remove that file.
- The Omarchy hooks install voxtype, the agent and fingerprint setup on the next `omarchy update`.
- `git/config` contains your name and email (this repository is public; the email already appears in commit metadata).

## Safety and backups

- Dry-run is the default. `--apply` is required to write files.
- The entire manifest, checksums, targets and existing parents are validated before any writes. Unsupported manifests, traversal, source/destination symlinks (including inside-home links), system-root homes, directory conflicts, and overlapping targets are rejected.
- Conflicting owned files are copied with their previous bytes and mode to `~/.dotfiles-backups/<UTC timestamp>-<unique ID>/<original relative path>` before replacement. New content is written to a unique sibling temporary file and assigned its mode before replacing the target directory entry; unrelated hardlinks retain their bytes and mode. Temporary files are cleaned up on failure. Identical content and permissions are skipped, so a second apply creates no backups.
- Unrelated files are never removed. Existing obsolete snapshot files are not automatically pruned by capture; review them before versioning.
- Restore is not an atomic transaction: disk/permission failures can leave a partial apply. Backups are retained. Concurrent filesystem mutation is not supported; symlink checks are not a protection against a malicious concurrent writer.
- Checksums detect snapshot drift, not malicious changes to both files and manifest. Review imported extension/skill code before restoring or starting Pi.

Backups may contain private data from the destination machine; keep them private and out of Git. To undo a conflict, manually copy its backup to the corresponding home-relative path after reviewing it. There is no automatic deletion-based rollback.

## Refresh the snapshot

```sh
python3 dotfiles/capture.py                 # Read-only preview; audits resources
python3 dotfiles/capture.py --apply         # Write snapshot only, never live config
python3 -m unittest discover -s dotfiles/tests -v
```

Capture reads explicit resource roots, not the entire home. It pins packages from installed metadata and rejects unknown external symlinks, unsupported binary files, credential patterns and unknown machine-home paths. Only the three reviewed Omarchy skill links (omarchy, diagnose-crash, omarchy-app) are dereferenced. Additional Fish universal variables require deliberate review/export; they are not silently copied. The generated alias subset is retained unless the live home supplies that file. New configuration types/resources outside the allowlist need a reviewed code change. Always inspect the snapshot diff before committing: pattern scans cannot prove arbitrary text is secret-free.

## Exclusions

Credentials/API keys/OAuth state, `.env` files, private keys, histories, sessions, trust decisions, model catalogs/store, caches, logs, package directories, installer-managed asset indexes, backups, personal project instructions, Omarchy shipped defaults and git-cloned themes are excluded. No live configuration, home Git branch, task progress document, or package installation is modified by preparing this snapshot. Generated artifacts and documentation are in English; skill instruction language is preserved from its source.

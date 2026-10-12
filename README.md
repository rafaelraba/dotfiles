# Portable Pi and Fish configuration

A reviewed snapshot of Pi preferences/resources, local skills (with supporting files), Fish startup, and Starship. Restore copies owned files only; it never installs dependencies, deletes unrelated files, or restores credentials.

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
npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0
pi update --extensions
npm install --prefix "$HOME/.pi/mcp" --ignore-scripts --no-audit --no-fund @upstash/context7-mcp@2.2.5
```

`pi update --extensions` reconciles the pinned declarations already restored in `~/.pi/agent/settings.json`. Plain `pi update` updates Pi itself; it is **not** the package reinstall command. Installed Pi 1.1.0 documentation confirms this distinction. Package pins were read from installed metadata:

| Package | Version |
|---|---|
| gentle-pi | 4.0.0 |
| gentle-engram | 0.4.2 |
| pi-web-access | 0.38.0 |
| pi-btw | 0.8.0 |

Direct install alternatives are `pi install npm:gentle-pi@4.0.0`, `pi install npm:gentle-engram@0.4.2`, `pi install npm:pi-web-access@0.38.0`, and `pi install npm:pi-btw@0.8.0`. Reconciliation is preferred because it preserves settings filters.

Context7's version comes from the original MCP declaration, not independently verified installed metadata. Its command now points to `~/.pi/mcp/node_modules/.bin/context7-mcp`: starting Pi will **not** implicitly download it with `npx -y`. Install it with the separate command above. Engram requires its own executable on PATH (or `ENGRAM_BIN`); its binary version was not verified or bundled. Install it using its upstream instructions. No dependency installation or network connectivity was tested here. npm top-level pins do not lock the entire transitive dependency graph or guarantee continued registry availability.

Run `/login` in Pi to authenticate again and select an available model if the saved model is unavailable to your account. MCP entries contain no credentials in this snapshot. If future capture redacts credential fields, `manifest.json` lists their key paths and replaces string fields with `${VARIABLE_NAME}` placeholders; supply the corresponding variables privately, never commit them. Other services may require separate authentication. Built-in Pi MCP understands these placeholders; `directTools` and `lifecycle` in the original Engram entry are retained legacy adapter options, not built-in exposure controls.

The old `~/.pi/npm/package.json` only declares `pi-mcp-adapter` with an unpinned range, has no installed package metadata, and is not referenced by current Pi settings. It is omitted rather than pretending it is a pinned dependency. Pi 1.1.0 has built-in MCP support.

## What is included

| Resource | Portable treatment |
|---|---|
| Pi settings, theme, subagent model profiles | Package sources pinned; paths relative to the agent directory |
| `~/.pi/gentle-ai/{persona,banner,models,profiles}.json` | Saved persona, appearance, agent models and active profile |
| Agents, chains, Herdr extension, Gentle AI support docs | Current resources preserved, including package-managed agent copies; Herdr is optional and its extension is inactive without its environment |
| `~/.agents/skills` | Local source skills and `_shared` references copied recursively; package skills remain package dependencies |
| Omarchy and diagnose-crash skills | Dereferenced into ordinary skill directories with their supporting Markdown; no host symlinks |
| Fish and Starship | Startup plus reviewed empty `fish_greeting`; no universal-variable dump |
| Aliases | Reviewed portable subset of Omarchy Bash defaults translated to Fish in `conf.d/20-portable-aliases.fish` |

Pi discovers `~/.agents/skills` natively; settings also explicitly list `../../.agents/skills` relative to `~/.pi/agent`. The duplicate live Omarchy links in `~/.pi/agent/skills` are intentionally not recreated. Package-provided skills are installed by the pinned Pi packages, not copied from node_modules. Omarchy/crash skill instructions remain available elsewhere, but their system-specific commands still require Omarchy/Linux/systemd tools. They are not a desktop backup.

Fish autoload shortcuts in `~/.config/fish/functions/` make `nvim` without arguments run `command nvim .` and `h` run `command herdr`. Explicit arguments and exit statuses are preserved; the existing `n` shortcut remains unchanged. Neovim and Herdr must be installed separately. Capture includes this functions directory, so future refreshes retain the live shortcuts.

At initial capture, Fish had no personal alias functions, abbreviations, or binding files. Its only universal variable was the empty greeting. `.bashrc` had no personal overrides and sourced Omarchy defaults. Portable aliases include directory traversal, Git, optional eza/Docker/Rails/tmux/nvim, and Linux `xdg-open`. Desktop/agent launchers, automatic approval aliases (`cx`, `cy`), mise update shortcuts, fzf/editor/zoxide helpers, and distribution Bash functions/completions/inputrc are intentionally omitted. Bash itself is not restored.

Known resource-path tokens are translated to `~/.agents/...` or `~/.pi/...`; arbitrary home substrings are not rewritten. Unknown `/home/...` or `/Users/...` paths cause capture to fail for review. Script code is not generically templated.

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

Capture reads explicit resource roots, not the entire home. It pins packages from installed metadata and rejects unknown external symlinks, unsupported binary files, credential patterns and unknown machine-home paths. Only the two reviewed Omarchy skill links are dereferenced. Additional Fish universal variables require deliberate review/export; they are not silently copied. The generated alias subset is retained unless the live home supplies that file. New configuration types/resources outside the allowlist need a reviewed code change. Always inspect the snapshot diff before committing: pattern scans cannot prove arbitrary text is secret-free.

## Exclusions

Credentials/API keys/OAuth state, `.env` files, private keys, histories, sessions, trust decisions, model catalogs/store, caches, logs, package directories, installer-managed asset indexes, backups, personal project instructions, and desktop configuration are excluded. No live configuration, home Git branch, task progress document, or package installation is modified by preparing this snapshot. Generated artifacts and documentation are in English; skill instruction language is preserved from its source.

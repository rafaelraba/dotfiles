#!/usr/bin/env python3
"""Restore reviewed, manifest-owned files. No shell commands or dependency installs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True

TREE_TARGETS = ('.agents/skills/', '.pi/agent/skills/', '.pi/agent/agents/',
                '.pi/agent/chains/', '.pi/agent/extensions/', '.pi/agent/prompts/',
                '.pi/agent/themes/', '.pi/agent/gentle-ai/support/',
                '.config/fish/conf.d/', '.config/fish/functions/')
FILE_TARGETS = {'.config/fish/config.fish', '.config/starship.toml',
                '.pi/agent/settings.json', '.pi/agent/subagents.json',
                '.pi/agent/mcp.json', '.pi/agent/keybindings.json',
                '.pi/agent/AGENTS.md', '.pi/agent/SYSTEM.md', '.pi/agent/APPEND_SYSTEM.md',
                '.pi/gentle-ai/persona.json', '.pi/gentle-ai/banner.json',
                '.pi/gentle-ai/models.json', '.pi/gentle-ai/profiles.json'}


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid relative path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Absolute or traversing path rejected')
    excluded = {'auth.json', 'mcp-auth.json', 'credentials.json', 'tokens.json',
                'secrets.json', 'fish_variables', 'fish_history', '__pycache__',
                '.git', 'node_modules', 'sessions', 'cache', 'trust.json', 'models-store.json'}
    if any(p.startswith('.env') or p in excluded or 'credentials' in p.lower()
           or p.endswith(('.pem', '.key', '.pyc', '.bak', '.backup', '.log'))
           or '.bak-' in p or '.bak.' in p for p in path.parts):
        raise ValueError('Sensitive or generated path rejected')
    return path


def no_links(path):
    """Reject symlinks, including dangling links and links in existing parents."""
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError('Symlink rejected: ' + str(part))


def checked_home(home, repo):
    home = Path(os.path.abspath(os.path.expanduser(str(home))))
    no_links(home)
    system_roots = {'etc', 'usr', 'var', 'bin', 'sbin', 'proc', 'sys', 'dev', 'boot'}
    if len(home.parts) < 3 or home.parts[1] in system_roots or home == repo or repo in home.parents:
        raise ValueError('Home must be a dedicated directory outside the snapshot')
    if home.exists() and not home.is_dir():
        raise ValueError('Home is not a directory')
    return home


def plan(repo, home):
    repo = Path(repo).absolute()
    no_links(repo)
    home = checked_home(home, repo)
    manifest_path = repo / 'manifest.json'
    no_links(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError('Cannot read valid manifest') from exc
    if (not isinstance(manifest, dict) or type(manifest.get('version')) is not int
            or manifest.get('version') != 1 or not isinstance(manifest.get('files'), list)):
        raise ValueError('Unsupported manifest schema')
    seen = set()
    actions = []
    backup_directory = home / '.dotfiles-backups'
    no_links(backup_directory)
    if backup_directory.exists() and not backup_directory.is_dir():
        raise ValueError('Backup root is not a directory')
    for entry in manifest['files']:
        if not isinstance(entry, dict) or set(entry) != {'source', 'target', 'sha256', 'mode'}:
            raise ValueError('Invalid file entry')
        source_rel = relative(entry['source'])
        target_rel = relative(entry['target'])
        if source_rel.parts[0] != 'files' or len(source_rel.parts) < 2:
            raise ValueError('Source must be inside files/')
        target_name = str(target_rel)
        if target_name not in FILE_TARGETS and not target_name.startswith(TREE_TARGETS):
            raise ValueError('Target not in owned resource trees')
        if target_name in seen:
            raise ValueError('Duplicate target')
        if any(target_name.startswith(other + '/') or other.startswith(target_name + '/') for other in seen):
            raise ValueError('Overlapping file and directory targets')
        seen.add(target_name)
        mode = entry['mode']
        if type(mode) is not int or mode not in (0o600, 0o644, 0o700, 0o755):
            raise ValueError('Unsafe file permissions')
        source = repo / source_rel
        target = home / target_rel
        no_links(source)
        no_links(target)
        if target == repo or repo in target.parents or target in repo.parents:
            raise ValueError('Target overlaps snapshot')
        for parent in target.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError('Destination parent is not a directory')
        if not source.is_file():
            raise ValueError('Source is not a regular file')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Snapshot checksum mismatch: ' + entry['source'])
        if target.exists() and not target.is_file():
            raise ValueError('Destination is not a regular file')
        unchanged = (target.exists() and target.read_bytes() == data
                     and stat.S_IMODE(target.stat().st_mode) == mode)
        actions.append((target, data, mode, 'unchanged' if unchanged else 'backup + write' if target.exists() else 'write'))
    return home, actions


def restore(repo, home, apply=False):
    home, actions = plan(repo, home)
    backup_root = home / '.dotfiles-backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex)
    for target, data, mode, action in actions:
        print(('APPLY' if apply else 'DRY-RUN') + ': ' + action + ' ' + str(target.relative_to(home)))
        if not apply or action == 'unchanged':
            continue
        # Recheck immediately before mutation; use only when no concurrent writer exists.
        no_links(target)
        if target.exists():
            backup = backup_root / target.relative_to(home)
            no_links(backup)
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with backup.open('xb') as output:
                output.write(target.read_bytes())
            backup.chmod(stat.S_IMODE(target.stat().st_mode))
        target.parent.mkdir(parents=True, exist_ok=True)
        # Replace the directory entry, not the inode shared by any hardlinks.
        descriptor, temporary_name = tempfile.mkstemp(
            prefix='.' + target.name + '.dotfiles-', suffix='.tmp', dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
                output.flush()
                os.fchmod(output.fileno(), mode)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home(), help='Target home (default: current home)')
    parser.add_argument('--apply', action='store_true', help='Write files; otherwise only show the plan')
    args = parser.parse_args()
    try:
        restore(Path(__file__).resolve().parent, args.home, args.apply)
    except (ValueError, OSError) as exc:
        parser.exit(1, 'Restore refused: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()

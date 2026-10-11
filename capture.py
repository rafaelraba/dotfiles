#!/usr/bin/env python3
"""Capture explicit configuration/resource roots; dry-run unless --apply is supplied."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('portable_restore', Path(__file__).with_name('restore.py'))
safety = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(safety)

SECRET = re.compile(r'(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_|github_pat_|sk-(?:proj-)?)[A-Za-z0-9_-]{20,}|\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)')
SENSITIVE_KEY = re.compile(r'(?i)(?:api[_-]?key|secret|password|authorization|token|credential)')
RESOURCE_ROOTS = ('.agents/skills', '.pi/agent', '.pi/gentle-ai')
DIRECTORIES = ('.agents/skills', '.pi/agent/agents', '.pi/agent/chains',
               '.pi/agent/extensions', '.pi/agent/prompts', '.pi/agent/themes',
               '.pi/agent/gentle-ai/support', '.config/fish/conf.d', '.config/fish/functions')
SINGLES = ('.config/fish/config.fish', '.config/starship.toml',
           '.pi/agent/settings.json', '.pi/agent/subagents.json', '.pi/agent/keybindings.json',
           '.pi/agent/AGENTS.md', '.pi/agent/SYSTEM.md', '.pi/agent/APPEND_SYSTEM.md',
           '.pi/gentle-ai/persona.json', '.pi/gentle-ai/banner.json',
           '.pi/gentle-ai/models.json', '.pi/gentle-ai/profiles.json', '.pi/agent/mcp.json')
OMARCHY = Path('/usr/share/omarchy/default/agents/skills')


def audit(text, label):
    if SECRET.search(text):
        raise ValueError('Credential pattern detected in ' + label + ' (value suppressed)')
    # Detect credential assignments rather than mere documentation mentions.
    assignment = re.compile(r'''(?im)^\s*(?:export\s+|set\s+-\w+\s+)?(?:[A-Z_]*(?:API_KEY|PASSWORD|SECRET|TOKEN))\s*=\s*["']?([^\s"']+)''')
    for match in assignment.finditer(text):
        if not match.group(1).startswith(('$', '<', 'YOUR_', 'example', 'REDACTED')):
            raise ValueError('Credential assignment detected in ' + label + ' (value suppressed)')


def portable_text(text, home):
    """Translate only known resource path tokens, never arbitrary home substrings."""
    for root in RESOURCE_ROOTS:
        prefix = str(home / root)
        text = re.sub(re.escape(prefix) + r'(?=/|[\s\"\'`\]\),:]|$)', '~/' + root, text)
    if re.search(r'/home/[^/\s]+|/Users/[^/\s]+', text):
        raise ValueError('Unreviewed machine-specific home path (value suppressed)')
    return text


def sanitize_json(value, home, redactions, trail=()):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            path = trail + (key,)
            environment_value = bool(trail and trail[-1] == 'env' and key not in ('LANG', 'LC_ALL', 'TZ'))
            header_value = bool(trail and trail[-1] == 'headers')
            if (SENSITIVE_KEY.search(key) or environment_value or header_value) and isinstance(child, str):
                if re.fullmatch(r'(?:Bearer )?\$\{[A-Z_][A-Z0-9_]*\}', child):
                    result[key] = child
                else:
                    placeholder = re.sub('[^A-Z0-9_]', '_', key.upper())
                    result[key] = '${' + placeholder + '}'
                    redactions.append('.'.join(path))
            else:
                result[key] = sanitize_json(child, home, redactions, path)
        return result
    if isinstance(value, list):
        return [sanitize_json(child, home, redactions, trail + (str(i),)) for i, child in enumerate(value)]
    if isinstance(value, str):
        return portable_text(value, home)
    return value


def walk_files(root):
    safety.no_links(root)
    if not root.exists():
        return
    for child in sorted(root.iterdir()):
        safety.relative(child.name)  # Reject secret/artifact names before opening.
        if child.is_symlink():
            raise ValueError('Unreviewed source symlink: ' + str(child))
        if child.is_dir():
            yield from walk_files(child)
        elif child.is_file():
            yield child
        else:
            raise ValueError('Non-regular source resource')


def write_snapshot(repo, content):
    # Preflight every output before any writes. Never remove stale files.
    for relative in content:
        safety.relative(relative)
        target = repo / relative
        safety.no_links(target)
        if target.exists() and not target.is_file():
            raise ValueError('Snapshot output is not a regular file')
    for relative, data in content.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def pinned_packages(settings, home):
    entries = []
    for declaration in settings.get('packages', []):
        source = declaration if isinstance(declaration, str) else declaration['source']
        if not source.startswith('npm:'):
            raise ValueError('Non-npm package needs explicit portability review')
        name = source[4:].rsplit('@', 1)[0] if '@' in source[5:] else source[4:]
        if not re.fullmatch(r'(?:@[a-z0-9._-]+/)?[a-z0-9._-]+', name):
            raise ValueError('Invalid npm package identity')
        metadata = home / '.pi/agent/npm/node_modules' / name / 'package.json'
        safety.no_links(metadata)
        data = json.loads(metadata.read_text())
        version = data['version']
        if data['name'] != name or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?', version):
            raise ValueError('Package metadata mismatch')
        pinned = 'npm:' + name + '@' + version
        entries.append(pinned if isinstance(declaration, str) else dict(declaration, source=pinned))
    return entries


def pi_metadata():
    executable = shutil.which('pi')
    if not executable:
        raise ValueError('Pi executable missing; cannot verify installed CLI version')
    for directory in Path(executable).resolve().parents:
        candidate = directory / 'package.json'
        if candidate.is_file():
            data = json.loads(candidate.read_text())
            if data.get('name') == '@earendil-works/pi-coding-agent':
                return {'name': data['name'], 'version': data['version'], 'node': data.get('engines', {}).get('node')}
    raise ValueError('Installed Pi metadata not found')


def capture(repo, home, apply=False):
    home = Path(home).absolute()
    safety.no_links(home)
    redactions = []
    records = {}
    content = {}
    origins = {}

    def add(path, target, origin='local'):
        safety.relative(target)
        safety.no_links(path)
        text = path.read_text(encoding='utf-8')
        if path.suffix == '.json':
            data = sanitize_json(json.loads(text), home, redactions, (target,))
            if target == '.pi/agent/settings.json':
                data['packages'] = pinned_packages(data, home)
                # Agent-directory-relative resource path, independent of username.
                data['skills'] = list(dict.fromkeys(data.get('skills', []) + ['../../.agents/skills']))
            if target == '.pi/agent/mcp.json':
                context = data.get('mcpServers', {}).get('context7', {})
                expected = ['-y', '--package=@upstash/context7-mcp@2.2.5', '--', 'context7-mcp']
                if context.get('command') == 'npx' and context.get('args') == expected:
                    # Do not allow an ordinary Pi launch to download dependencies.
                    context['command'] = '~/.pi/mcp/node_modules/.bin/context7-mcp'
                    context['args'] = []
            text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        else:
            text = portable_text(text, home)
        audit(text, target)
        if target == '.config/fish/config.fish':
            text = text.replace('    starship init fish | source',
                                '    if type -q starship\n        starship init fish | source\n    end')
        encoded = text.encode()
        source = 'files/' + target
        content[source] = encoded
        mode = 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644
        records[target] = {'source': source, 'target': target, 'sha256': hashlib.sha256(encoded).hexdigest(), 'mode': mode}
        origins[target] = origin

    for relative in SINGLES:
        path = home / relative
        safety.no_links(path)
        if path.is_file():
            add(path, relative)
    for relative in DIRECTORIES:
        root = home / relative
        if relative == '.agents/skills' and root.exists():
            safety.no_links(root)
            for child in sorted(root.iterdir()):
                if child.is_symlink():
                    if child.name not in ('omarchy', 'diagnose-crash') or child.resolve() != OMARCHY / child.name:
                        raise ValueError('Unreviewed external skill symlink: ' + child.name)
                    external = OMARCHY / child.name
                    for file in walk_files(external):
                        add(file, relative + '/' + child.name + '/' + str(file.relative_to(external)), 'Omarchy vendored resource')
                elif child.is_dir():
                    for file in walk_files(child):
                        add(file, relative + '/' + str(file.relative_to(root)))
                elif child.is_file():
                    add(child, relative + '/' + child.name)
        else:
            for file in walk_files(root):
                add(file, relative + '/' + str(file.relative_to(root)))
    # Export only the reviewed empty greeting. Never copy universal vars wholesale.
    variables = home / '.config/fish/fish_variables'
    safety.no_links(variables)
    if variables.is_file():
        names = []
        greeting = False
        for line in variables.read_text().splitlines():
            if line.startswith('SETUVAR '):
                name, _, value = line[8:].partition(':')
                names.append(name.split()[-1])
                if name == 'fish_greeting' and value in ('', r'\x1d'):
                    greeting = True
        if names != ['fish_greeting']:
            raise ValueError('Additional Fish universal variable names need review; values suppressed')
        if greeting:
            target = '.config/fish/conf.d/10-portable-greeting.fish'
            encoded = b'# Reviewed universal greeting exported as non-secret startup preference.\nset -g fish_greeting ""\n'
            content['files/' + target] = encoded
            records[target] = {'source': 'files/' + target, 'target': target, 'sha256': hashlib.sha256(encoded).hexdigest(), 'mode': 0o644}
    # Preserve separately reviewed generated aliases during refresh; do not infer shell syntax.
    aliases = repo / 'files/.config/fish/conf.d/20-portable-aliases.fish'
    safety.no_links(aliases)
    if aliases.is_file() and '.config/fish/conf.d/20-portable-aliases.fish' not in records:
        add(aliases, '.config/fish/conf.d/20-portable-aliases.fish', 'reviewed Omarchy Bash alias translations')
    settings = json.loads(content.get('files/.pi/agent/settings.json', b'{}'))
    manifest = {'version': 1, 'files': [records[k] for k in sorted(records)],
                'dependencies': {'pi': pi_metadata(), 'packages': settings.get('packages', []),
                                 'mcp': {'context7': '@upstash/context7-mcp@2.2.5', 'engram': 'external executable; version not verified'}},
                'redacted_fields': redactions,
                'origins': origins,
                'excluded': ['credentials, history, sessions, caches, trust, models-store, node_modules',
                             'desktop configuration and Bash distribution runtime',
                             'inactive legacy .pi/npm/package.json pi-mcp-adapter range; no installed metadata',
                             'managed-assets runtime index; package installer may refresh managed agents'],
                'external_requirements': ['Engram executable (ENGRAM_BIN optional)', 'optional Herdr integration',
                                          'Omarchy/crash skill commands depend on Linux/Omarchy tools']}
    content['manifest.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode()
    print(('APPLY' if apply else 'DRY-RUN') + ': capture ' + str(len(records)) + ' files; redacted field count ' + str(len(redactions)))
    if apply:
        write_snapshot(repo, content)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home(), help='Source home; live files are read-only')
    parser.add_argument('--apply', action='store_true', help='Refresh snapshot and manifest, never live configuration')
    args = parser.parse_args()
    try:
        capture(Path(__file__).resolve().parent, args.home, args.apply)
    except (ValueError, OSError, UnicodeError, KeyError) as exc:
        parser.exit(1, 'Capture refused: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()

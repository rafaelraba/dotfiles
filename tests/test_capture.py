import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / 'capture.py'


class CaptureTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('capture', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix='capture fixture ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_json_redaction_and_resource_path_only_translation(self):
        home = self.root / 'old user'
        value = {'headers': {'Authorization': 'private-value'},
                 'env': {'API_KEY': 'private-value', 'LANG': 'C.UTF-8'},
                 'skills': [str(home / '.agents/skills')], 'defaultModel': 'unchanged'}
        cleaned = self.module.sanitize_json(value, home, [])
        self.assertEqual(cleaned['headers']['Authorization'], '${AUTHORIZATION}')
        self.assertEqual(cleaned['env']['API_KEY'], '${API_KEY}')
        self.assertEqual(cleaned['env']['LANG'], 'C.UTF-8')
        self.assertEqual(cleaned['skills'], ['~/.agents/skills'])
        self.assertEqual(cleaned['defaultModel'], 'unchanged')

    def test_unknown_environment_and_header_values_are_not_exported(self):
        value = {'env': {'SERVICE_VALUE': 'private-value', 'LANG': 'C.UTF-8',
                         'API_KEY': '${EXISTING_KEY}'},
                 'headers': {'X-Auth': 'private-value'}, 'token': 'private-value'}
        cleaned = self.module.sanitize_json(value, self.root, [])
        self.assertEqual(cleaned['env']['SERVICE_VALUE'], '${SERVICE_VALUE}')
        self.assertEqual(cleaned['headers']['X-Auth'], '${X_AUTH}')
        self.assertEqual(cleaned['env']['API_KEY'], '${EXISTING_KEY}')
        self.assertEqual(cleaned['token'], '${TOKEN}')

    def test_unknown_machine_path_fails_closed(self):
        with self.assertRaises(ValueError):
            self.module.portable_text('go to /home/other/private', self.root)

    def test_secret_pattern_fails_without_value_in_exception(self):
        value = 'ghp_' + 'x' * 40
        with self.assertRaises(ValueError) as caught:
            self.module.audit(value, 'sample.md')
        self.assertNotIn(value, str(caught.exception))

    def test_source_symlink_rejected(self):
        external = self.root / 'external'
        external.mkdir()
        (external / 'SKILL.md').write_text('safe')
        link = self.root / 'skills'
        link.symlink_to(external)
        with self.assertRaises(ValueError):
            list(self.module.walk_files(link))

    def test_secret_named_source_rejected_before_read(self):
        root = self.root / 'skills'
        root.mkdir()
        for name in ['.env', 'credentials.json', 'tokens.json', 'sample.bak']:
            with self.subTest(name=name):
                directory = root / name.replace('.', '_')
                directory.mkdir()
                (directory / name).write_text('do not read')
                with self.assertRaises(ValueError):
                    list(self.module.walk_files(directory))

    def test_capture_dry_run_apply_support_and_no_automatic_mcp_download(self):
        home = self.root / 'source user'
        repo = self.root / 'snapshot'
        repo.mkdir()
        agent = home / '.pi/agent'
        agent.mkdir(parents=True)
        (agent / 'settings.json').write_text('{"packages": []}')
        (agent / 'mcp.json').write_text(json.dumps({'mcpServers': {'context7': {
            'command': 'npx', 'args': ['-y', '--package=@upstash/context7-mcp@2.2.5', '--', 'context7-mcp']}}}))
        support = home / '.agents/skills/_shared'
        support.mkdir(parents=True)
        (support / 'guide.md').write_text('Shared resource')
        with patch.object(self.module, 'pi_metadata', return_value={'name': 'pi', 'version': '1.0.0'}):
            self.module.capture(repo, home)
            self.assertEqual(list(repo.iterdir()), [])
            manifest = self.module.capture(repo, home, apply=True)
        self.assertEqual(len(manifest['files']), 3)
        self.assertTrue((repo / 'files/.agents/skills/_shared/guide.md').is_file())
        settings = json.loads((repo / 'files/.pi/agent/settings.json').read_text())
        self.assertEqual(settings['skills'], ['../../.agents/skills'])
        context = json.loads((repo / 'files/.pi/agent/mcp.json').read_text())['mcpServers']['context7']
        self.assertEqual(context['command'], '~/.pi/mcp/node_modules/.bin/context7-mcp')
        self.assertEqual(context['args'], [])

    def herdr_fixture(self, home):
        root = home / '.config/herdr-app'
        (root / 'layouts/.state').mkdir(parents=True)
        (root / 'installed.json').write_text(json.dumps({'toast': {}, 'layout:main': {}}))
        (root / 'keys.json').write_text('{"global": {"alt-f": "mod.open:scratch"}}')
        (root / 'settings.json').write_text('{"zoom": 1}')
        (root / 'shared.json').write_text('{"state": 1}')
        (root / 'AGENTS.md').write_text('rewritten by Herdr')
        (root / 'layouts/main.json').write_text('{"id": "root"}')
        (root / 'layouts/mine.json').write_text('{"id": "root", "cloned_from": {"name": "main"}}')
        (root / 'layouts/mine.json.old-1').write_text('{}')
        (root / 'layouts/.state/mine.json').write_text('{}')
        shipped = root / 'mods/toast'
        shipped.mkdir(parents=True)
        (shipped / 'main.js').write_text('shipped')
        mod = root / 'mods/scratch'
        (mod / 'icons').mkdir(parents=True)
        (mod / 'main.js').write_text('export default 1;\n')
        (mod / 'mod.json').write_text('{"place": "none"}')
        (mod / 'icons/x.svg').write_text('<svg/>')
        (mod / 'gpui-kit.d.ts').write_text('generated')
        (mod / 'jsconfig.json').write_text('{}')
        (mod / 'main.js.bak-visible').write_text('backup')
        (mod / 'shot.png').write_bytes(b'\x89PNG\x00\xff')
        (mod / '.debug.log').write_text('hidden')
        return root

    def test_herdr_captures_only_personal_files(self):
        home = self.root / 'source user'
        self.herdr_fixture(home)
        targets = {target for _, target in self.module.herdr_files(home)}
        self.assertEqual(targets, {'.config/herdr-app/layouts/mine.json',
                                   '.config/herdr-app/mods/scratch/main.js',
                                   '.config/herdr-app/mods/scratch/mod.json',
                                   '.config/herdr-app/mods/scratch/icons/x.svg'})

    def test_herdr_capture_writes_snapshot_with_keys_and_settings(self):
        home = self.root / 'source user'
        repo = self.root / 'snapshot'
        repo.mkdir()
        self.herdr_fixture(home)
        with patch.object(self.module, 'pi_metadata', return_value={'name': 'pi', 'version': '1.0.0'}):
            manifest = self.module.capture(repo, home, apply=True)
        targets = {entry['target'] for entry in manifest['files']}
        self.assertIn('.config/herdr-app/keys.json', targets)
        self.assertIn('.config/herdr-app/settings.json', targets)
        self.assertNotIn('.config/herdr-app/shared.json', targets)
        self.assertEqual(manifest['origins']['.config/herdr-app/keys.json'], 'Herdr app (personal)')
        self.assertTrue((repo / 'files/.config/herdr-app/mods/scratch/main.js').is_file())

    def test_herdr_without_installed_list_fails_closed(self):
        home = self.root / 'source user'
        root = self.herdr_fixture(home)
        (root / 'installed.json').unlink()
        with self.assertRaises(ValueError):
            list(self.module.herdr_files(home))

    def test_herdr_mod_symlink_rejected(self):
        home = self.root / 'source user'
        root = self.herdr_fixture(home)
        outside = self.root / 'outside mod'
        outside.mkdir()
        (root / 'mods/linked').symlink_to(outside)
        with self.assertRaises(ValueError):
            list(self.module.herdr_files(home))

    def test_snapshot_symlink_write_rejected(self):
        repo = self.root / 'repo'
        repo.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (repo / 'files').symlink_to(outside)
        with self.assertRaises(ValueError):
            self.module.write_snapshot(repo, {'files/item': b'safe'})
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

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

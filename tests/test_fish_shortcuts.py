"""Exercise launchers with isolated Fish and executable stubs, never real apps."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
LIVE = REPO.parent / '.config/fish/functions'
TARGETS = ['.config/fish/functions/' + name + '.fish' for name in ('nvim', 'h')]


def load(name):
    spec = importlib.util.spec_from_file_location('shortcut_' + name, REPO / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FishShortcutsTests(unittest.TestCase):
    def setUp(self):
        self.fish = shutil.which('fish')
        self.assertIsNotNone(self.fish, 'Fish is required for launcher verification')
        temp = tempfile.TemporaryDirectory(prefix='fish shortcuts ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('nvim', 'herdr'):
            stub = self.bin / name
            stub.write_text('#!' + sys.executable + '\nimport json, os, sys\n'
                            'print(json.dumps(sys.argv[1:]))\n'
                            'sys.exit(int(os.environ["STUB_STATUS"]))\n')
            stub.chmod(0o755)
        self.env = {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'PATH': str(self.bin), 'STUB_STATUS': '0', 'LC_ALL': 'C'}

    def invoke(self, directory, name, args, sourced=False, status=0, normal=False):
        self.env['STUB_STATUS'] = str(status)
        setup = ('source $argv[1];' if sourced else 'set fish_function_path $argv[1];')
        code = setup + ' set -e argv[1]; ' + name + ' $argv; exit $status'
        command = [self.fish] + ([] if normal else ['--no-config'])
        result = subprocess.run(command + ['-c', code, str(directory / (name + '.fish') if sourced else directory), *args],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(json.loads(result.stdout), args if name == 'h' or args else ['.'])

    def test_live_and_snapshot_argument_and_status_contract(self):
        for directory in (LIVE, REPO / 'files/.config/fish/functions'):
            for name in ('nvim', 'h'):
                self.assertTrue((directory / (name + '.fish')).is_file())
                for sourced in (False, True):
                    for args in ([], ['file'], ['--flag', 'two words', '', 'second', '*.txt']):
                        for status in (0, 37):
                            with self.subTest(directory=directory, name=name, args=args, sourced=sourced, status=status):
                                self.invoke(directory, name, args, sourced, status)

    def test_manifest_integrity_and_matching_live_copies(self):
        manifest = json.loads((REPO / 'manifest.json').read_text())
        entries = {entry['target']: entry for entry in manifest['files']}
        for target in TARGETS:
            entry = entries[target]
            snapshot = REPO / entry['source']
            self.assertEqual(snapshot.read_bytes(), (REPO.parent / target).read_bytes())
            self.assertEqual(entry['sha256'], hashlib.sha256(snapshot.read_bytes()).hexdigest())
            self.assertEqual(entry['mode'], 0o644)
            self.assertEqual(snapshot.stat().st_mode & 0o777, entry['mode'])
            self.assertEqual(manifest['origins'][target], 'local')
        # Validate every owned file, without reading or writing the real home.
        load('restore').plan(REPO, self.home)

    def test_restore_normal_autoload_and_capture_preservation(self):
        manifest = json.loads((REPO / 'manifest.json').read_text())
        entries = [entry for entry in manifest['files'] if entry['target'] in TARGETS]
        self.assertEqual(len(entries), 2)
        repo = self.root / 'snapshot'
        repo.mkdir()
        for entry in entries:
            source = repo / entry['source']
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes((REPO / entry['source']).read_bytes())
        (repo / 'manifest.json').write_text(json.dumps({'version': 1, 'files': entries}))
        load('restore').restore(repo, self.home, apply=True)
        directory = self.home / '.config/fish/functions'
        for name in ('nvim', 'h'):
            # Normal startup discovers functions in the restored home automatically.
            result = subprocess.run([self.fish, '-c', name], env=self.env, text=True,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), ['.'] if name == 'nvim' else [])
        capture = load('capture')
        with patch.object(capture, 'pi_metadata', return_value={'name': 'test', 'version': '0.0.0'}):
            refreshed = capture.capture(repo, self.home, apply=True)
        self.assertEqual(refreshed['files'], entries)
        for entry in entries:
            self.assertEqual((repo / entry['source']).read_bytes(), (directory / Path(entry['target']).name).read_bytes())


if __name__ == '__main__':
    unittest.main()

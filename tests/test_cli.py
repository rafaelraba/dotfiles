"""Exercise the real snapshot via the CLI, using temporary homes only."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]


class SnapshotCliTests(unittest.TestCase):
    def test_relocated_snapshot_cli_dry_run_apply_twice_and_conflict(self):
        with tempfile.TemporaryDirectory(prefix='snapshot CLI home ') as temp:
            root = Path(temp)
            relocated = root / 'relocated snapshot with spaces'
            relocated.mkdir()
            for name in ['restore.py', 'manifest.json']:
                shutil.copyfile(REPO / name, relocated / name)
            shutil.copytree(REPO / 'files', relocated / 'files')
            home = root / 'new username with spaces'
            command = [sys.executable, '-B', str(relocated / 'restore.py'), '--home', str(home)]

            def run(apply=False):
                result = subprocess.run(command + (['--apply'] if apply else []),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout

            self.assertIn('DRY-RUN', run())
            self.assertFalse(home.exists())
            first = run(True)
            self.assertIn('APPLY: write', first)
            second = run(True)
            manifest = json.loads((relocated / 'manifest.json').read_text())
            self.assertEqual(second.count('APPLY: unchanged'), len(manifest['files']))
            self.assertFalse((home / '.dotfiles-backups').exists())
            for entry in manifest['files']:
                self.assertEqual((home / entry['target']).read_bytes(),
                                 (relocated / entry['source']).read_bytes())
            target = home / '.config/fish/config.fish'
            target.write_text('original conflict\n')
            unrelated = home / 'unrelated'
            unrelated.write_text('preserve me')
            self.assertIn('backup + write', run())
            self.assertEqual(target.read_text(), 'original conflict\n')
            self.assertFalse((home / '.dotfiles-backups').exists())
            run(True)
            backups = list((home / '.dotfiles-backups').rglob('config.fish'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), 'original conflict\n')
            self.assertEqual(unrelated.read_text(), 'preserve me')
            print('CLI verification: fresh-home dry-run wrote nothing; '
                  f'{len(manifest["files"])} files applied twice; conflict backup and unrelated file verified')

    def test_snapshot_has_no_symlinks_home_paths_or_detected_credentials(self):
        spec = importlib.util.spec_from_file_location('capture', REPO / 'capture.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        count = 0
        for path in (REPO / 'files').rglob('*'):
            self.assertFalse(path.is_symlink(), str(path.relative_to(REPO)))
            if path.is_file():
                text = path.read_text()
                module.audit(text, str(path.relative_to(REPO)))
                self.assertNotRegex(text, r'/home/[^/\s]+|/Users/[^/\s]+')
                count += 1
        manifest = json.loads((REPO / 'manifest.json').read_text())
        self.assertEqual(count, len(manifest['files']))
        self.assertEqual(manifest['redacted_fields'], [])
        print(f'Content scan: {count} snapshot files; no detected credentials, home paths, or symlinks; redacted keys: none')


if __name__ == '__main__':
    unittest.main()

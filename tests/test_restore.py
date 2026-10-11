import importlib.util
import json
from pathlib import Path
import hashlib
import os
import stat
import tempfile
import unittest
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().parents[1] / 'restore.py'


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='portable dotfiles ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'relocated repository'
        self.repo.mkdir()
        self.home = self.root / 'different user'
        self.source = self.repo / 'files/config.fish'
        self.source.parent.mkdir()
        self.source.write_text('set -g fish_greeting ""\n')
        self.entry = {'source': 'files/config.fish', 'target': '.config/fish/config.fish',
                      'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(), 'mode': 420}
        self.manifest = {'version': 1, 'files': [self.entry], 'dependencies': {}}
        self.save()
        spec = importlib.util.spec_from_file_location('restore', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def save(self):
        (self.repo / 'manifest.json').write_text(json.dumps(self.manifest))

    def run_restore(self, apply=False):
        return self.module.restore(self.repo, self.home, apply=apply)

    def test_dry_run_does_not_create_home(self):
        self.run_restore()
        self.assertFalse(self.home.exists())

    def test_apply_idempotence_spaces_and_relocation(self):
        self.run_restore(True)
        target = self.home / self.entry['target']
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.run_restore(True)
        self.assertFalse((self.home / '.dotfiles-backups').exists())

    def test_conflict_backup_and_unrelated_preservation(self):
        target = self.home / self.entry['target']
        target.parent.mkdir(parents=True)
        target.write_text('old configuration')
        unrelated = self.home / 'unrelated.txt'
        unrelated.write_text('keep')
        self.run_restore()
        self.assertEqual(target.read_text(), 'old configuration')
        self.assertFalse((self.home / '.dotfiles-backups').exists())
        self.run_restore(True)
        backups = list((self.home / '.dotfiles-backups').rglob('config.fish'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'old configuration')
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_hardlinked_target_preserves_external_bytes_and_mode(self):
        target = self.home / self.entry['target']
        target.parent.mkdir(parents=True)
        external = self.root / 'unrelated external file'
        external.write_bytes(b'original shared bytes\n')
        external.chmod(0o600)
        os.link(external, target)
        original_inode = external.stat().st_ino
        self.run_restore()
        self.assertEqual(external.read_bytes(), b'original shared bytes\n')
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o600)
        self.assertFalse((self.home / '.dotfiles-backups').exists())
        self.run_restore(True)
        self.assertEqual(external.read_bytes(), b'original shared bytes\n')
        self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o600)
        self.assertEqual(external.stat().st_ino, original_inode)
        self.assertNotEqual(target.stat().st_ino, original_inode)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), self.entry['mode'])
        backups = list((self.home / '.dotfiles-backups').rglob('config.fish'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b'original shared bytes\n')
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.run_restore(True)
        self.assertEqual(len(list((self.home / '.dotfiles-backups').rglob('config.fish'))), 1)

    def test_replace_failure_retains_target_and_cleans_sibling_temp(self):
        target = self.home / self.entry['target']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'original bytes')
        target.chmod(0o600)
        def fail_replace(temporary, destination):
            self.assertEqual(Path(temporary).read_bytes(), self.source.read_bytes())
            self.assertEqual(stat.S_IMODE(Path(temporary).stat().st_mode), self.entry['mode'])
            self.assertEqual(destination, target)
            raise OSError('simulated replacement failure')

        with patch.object(self.module.os, 'replace', side_effect=fail_replace):
            with self.assertRaises(OSError):
                self.run_restore(True)
        self.assertEqual(target.read_bytes(), b'original bytes')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_bad_manifest_preflight_no_writes(self):
        for mutation in [None, {'version': 2, 'files': []}, {'version': True, 'files': []},
                         {'version': 1, 'files': [self.entry, self.entry]},
                         {'version': 1, 'files': [{'source': '../escape', 'target': '../escape'}]}]:
            with self.subTest(mutation=mutation):
                (self.repo / 'manifest.json').write_text(json.dumps(mutation))
                with self.assertRaises(ValueError):
                    self.run_restore(True)
                self.assertFalse(self.home.exists())

    def test_traversal_absolute_and_sensitive_targets(self):
        for field, value in [('source', '/etc/passwd'), ('source', 'files/../escape'),
                             ('target', '../escape'), ('target', '/etc/test'),
                             ('target', '.ssh/config'), ('target', '.config/fish/.env')]:
            with self.subTest(field=field, value=value):
                entry = dict(self.entry)
                entry[field] = value
                self.manifest['files'] = [entry]
                self.save()
                with self.assertRaises(ValueError):
                    self.run_restore(True)
                self.assertFalse(self.home.exists())

    def test_symlink_source_rejected(self):
        outside = self.root / 'outside'
        outside.write_text('not allowed')
        link = self.repo / 'files/link'
        link.symlink_to(outside)
        self.entry['source'] = 'files/link'
        self.save()
        with self.assertRaises(ValueError):
            self.run_restore(True)

    def test_destination_symlink_leaf_parent_home_and_backup_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        for relative in ['.config', '.config/fish/config.fish', '.dotfiles-backups']:
            with self.subTest(relative=relative):
                home = self.root / ('test ' + relative.replace('/', '_'))
                link = home / relative
                link.parent.mkdir(parents=True)
                link.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError):
                    self.module.restore(self.repo, home, apply=True)
                self.assertEqual(list(outside.iterdir()), [])
        link = self.root / 'linked home'
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.module.restore(self.repo, link, apply=True)

    def test_home_safeguards(self):
        for home in [Path('/'), Path('/home'), Path('/tmp'), self.repo, self.repo / 'child']:
            with self.subTest(home=home):
                with self.assertRaises(ValueError):
                    self.module.restore(self.repo, home, apply=True)

    def test_hash_mismatch_and_directory_conflict(self):
        self.source.write_text('changed')
        with self.assertRaises(ValueError):
            self.run_restore(True)
        self.source.write_text('set -g fish_greeting ""\n')
        (self.home / self.entry['target']).mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.run_restore(True)

    def test_conflicting_manifest_paths_and_backup_file_preflight(self):
        entries = []
        for target in ['.agents/skills/resource', '.agents/skills/resource/file.md']:
            entries.append(dict(self.entry, target=target))
        self.manifest['files'] = entries
        self.save()
        with self.assertRaises(ValueError):
            self.run_restore(True)
        self.assertFalse(self.home.exists())
        self.manifest['files'] = [self.entry]
        self.save()
        self.home.mkdir()
        (self.home / '.dotfiles-backups').write_text('not a directory')
        with self.assertRaises(ValueError):
            self.run_restore(True)
        self.assertFalse((self.home / '.config').exists())

    def test_no_dependency_execution(self):
        self.manifest['dependencies'] = {'pi': 'not-installed', 'packages': ['not-installed']}
        self.save()
        self.run_restore(True)
        self.assertTrue((self.home / self.entry['target']).is_file())


if __name__ == '__main__':
    unittest.main()

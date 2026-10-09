"""Verify artifact copy-on-write and runner index isolation without loading an LLM."""
import builtins
import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_isolated import ArtifactMirror, ROOT


class ArtifactGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='texeira-artifact-guard-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = self.root / 'project' / 'docs'
        self.docs.mkdir(parents=True)
        self.mirror = self.root / 'mirror'
        self.history = self.docs / 'historical.json'
        self.history.write_text('{"historical": true}', encoding='utf-8')
        self.original = self.history.read_bytes()

    def test_all_open_apis_read_written_mirror_and_preserve_history(self):
        with ArtifactMirror(self.docs, self.mirror):
            self.assertEqual(self.history.read_bytes(), self.original)
            with builtins.open(self.history, 'w', encoding='utf-8') as handle:
                handle.write('builtins')
            self.assertEqual(self.history.read_text(encoding='utf-8'), 'builtins')
            with io.open(self.history, 'w', encoding='utf-8') as handle:
                handle.write('io')
            with builtins.open(self.history, encoding='utf-8') as handle:
                self.assertEqual(handle.read(), 'io')
            self.history.write_text('path', encoding='utf-8')
            self.assertEqual(self.history.read_text(encoding='utf-8'), 'path')
            self.history.write_bytes(b'bytes')
            self.assertEqual(self.history.read_bytes(), b'bytes')
        self.assertEqual(self.history.read_bytes(), self.original)
        self.assertEqual((self.mirror / 'historical.json').read_bytes(), b'bytes')

    def test_append_update_and_exclusive_modes_keep_file_semantics(self):
        with ArtifactMirror(self.docs, self.mirror):
            with self.assertRaises(FileExistsError):
                io.open(self.history, 'x')
            self.assertFalse((self.mirror / 'historical.json').exists())
            with io.open(self.history, 'r+', encoding='utf-8') as handle:
                self.assertEqual(handle.read(), self.original.decode())
                handle.seek(0)
                handle.write('updated')
                handle.truncate()
            with builtins.open(self.history, 'a+', encoding='utf-8') as handle:
                handle.write('-appended')
                handle.seek(0)
                self.assertEqual(handle.read(), 'updated-appended')
            with self.assertRaises(FileExistsError):
                io.open(self.history, 'x')
            new_file = self.docs / 'new.txt'
            with builtins.open(new_file, 'x', encoding='utf-8') as handle:
                handle.write('new')
            self.assertEqual(new_file.read_text(encoding='utf-8'), 'new')
            self.assertTrue(new_file.exists())
            self.assertEqual(new_file.stat().st_size, 3)
            with self.assertRaises(FileExistsError):
                builtins.open(new_file, 'x')
        self.assertEqual(self.history.read_bytes(), self.original)
        self.assertFalse(new_file.exists())

    def test_relative_paths_directories_and_unprotected_files(self):
        previous = Path.cwd()
        try:
            os.chdir(self.docs.parent)
            with ArtifactMirror(self.docs, self.mirror):
                Path('docs/new/subdir').mkdir(parents=True)
                Path('docs/new/subdir/result.txt').write_text('temporary', encoding='utf-8')
                self.assertEqual(Path('docs/new/subdir/result.txt').read_text(encoding='utf-8'), 'temporary')
                with builtins.open(os.fsencode('docs/binary.bin'), 'wb') as handle:
                    handle.write(b'\x00\x01')
                self.assertEqual(Path('docs/binary.bin').read_bytes(), b'\x00\x01')
                Path('outside.txt').write_text('outside', encoding='utf-8')
        finally:
            os.chdir(previous)
        self.assertFalse((self.docs / 'new').exists())
        self.assertFalse((self.docs / 'binary.bin').exists())
        self.assertEqual((self.docs.parent / 'outside.txt').read_text(encoding='utf-8'), 'outside')
        self.assertEqual((self.mirror / 'new/subdir/result.txt').read_text(encoding='utf-8'), 'temporary')

    def test_patches_restore_after_failure(self):
        before_open, before_io, before_mkdir, before_stat = builtins.open, io.open, Path.mkdir, Path.stat
        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
            with ArtifactMirror(self.docs, self.mirror):
                self.history.write_text('temporary', encoding='utf-8')
                raise RuntimeError('synthetic failure')
        self.assertIs(builtins.open, before_open)
        self.assertIs(io.open, before_io)
        self.assertIs(Path.mkdir, before_mkdir)
        self.assertIs(Path.stat, before_stat)
        self.assertEqual(self.history.read_bytes(), self.original)

    def test_missing_parent_is_not_silently_created(self):
        destination = self.docs / 'missing' / 'result.txt'
        with ArtifactMirror(self.docs, self.mirror):
            with self.assertRaises(FileNotFoundError):
                destination.write_text('must fail', encoding='utf-8')
            self.assertFalse(destination.parent.exists())
            destination.parent.mkdir()
            self.assertTrue(destination.parent.is_dir())
            destination.write_text('valid', encoding='utf-8')
            self.assertTrue(destination.is_file())
            self.assertEqual(destination.read_text(encoding='utf-8'), 'valid')
        self.assertFalse(destination.parent.exists())

    def test_low_level_mutations_cannot_bypass_mirror(self):
        original_index = self.root / 'index-original'
        original_index.mkdir()
        index_file = original_index / 'chroma.sqlite3'
        index_file.write_bytes(b'index-original')
        with ArtifactMirror(self.docs, self.mirror, protected_index=original_index):
            with self.assertRaisesRegex(AssertionError, 'mutation prohibited'):
                os.open(self.history, os.O_WRONLY | os.O_TRUNC)
            with self.assertRaisesRegex(AssertionError, 'mutation prohibited'):
                os.remove(self.history)
            with self.assertRaisesRegex(AssertionError, 'mutation prohibited'):
                os.mkdir(self.docs / 'unmirrored')
            with self.assertRaisesRegex(AssertionError, 'mutation prohibited'):
                os.rename(self.history, self.root / 'moved.json')
            with self.assertRaisesRegex(AssertionError, 'mutation prohibited'):
                index_file.write_bytes(b'corrupted')
            self.assertEqual(self.history.read_bytes(), self.original)
            self.assertEqual(index_file.read_bytes(), b'index-original')
        self.assertEqual(self.history.read_bytes(), self.original)
        self.assertEqual(index_file.read_bytes(), b'index-original')

    def test_runner_binds_index_copy_and_leaves_original_unchanged(self):
        self.assertEqual(os.environ.get('TEXEIRA_ISOLATED_TEST'), '1', 'Run through tests/run_isolated.py')
        import trial_support
        state = Path(os.environ['TEXEIRA_STATE_DIR']).resolve()
        copied = trial_support.INDEX.resolve()
        self.assertEqual(copied, Path(os.environ['TEXEIRA_ISOLATED_INDEX_DIR']).resolve())
        self.assertTrue(copied.is_relative_to(state))
        source = ROOT / 'chroma_catalogo_20260926_db'
        self.assertNotEqual(copied, source.resolve())
        source_files = {path.relative_to(source): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in source.rglob('*') if path.is_file()}
        copy_files = {path.relative_to(copied): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in copied.rglob('*') if path.is_file()}
        self.assertTrue(source_files, 'The local index must be present for this copy check')
        self.assertEqual(copy_files, source_files)
        marker = next(iter(source_files))
        (copied / marker).write_bytes(b'synthetic index change')
        self.assertEqual(hashlib.sha256((source / marker).read_bytes()).hexdigest(), source_files[marker])
        docs_mirror = Path(os.environ['TEXEIRA_ISOLATED_DOCS_DIR']).resolve()
        self.assertTrue(docs_mirror.is_relative_to(state))
        self.assertFalse(docs_mirror.is_relative_to(ROOT / 'docs'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

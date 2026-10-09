"""Windows HNSW cleanup checks with manual vectors; no app or external models."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_isolated import ROOT, close_isolated_chroma


def create_index(path):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    collection = client.create_collection(
        'cleanup-check', embedding_function=None,
        metadata={'hnsw:batch_size': 3, 'hnsw:sync_threshold': 3})
    collection.add(ids=['one', 'two', 'three'],
                   embeddings=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    result = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)
    if result['ids'] != [['one']] or not list(path.rglob('data_level0.bin')):
        raise AssertionError('Persistent HNSW index must be loaded for cleanup check')
    return client, collection


class ChromaCleanupTests(unittest.TestCase):
    def test_stop_releases_hnsw_files_with_live_client_references(self):
        with tempfile.TemporaryDirectory(prefix='texeira-chroma-close-') as directory:
            state = Path(directory)
            index = state / 'index'
            client, collection = create_index(index)
            try:
                self.assertEqual(close_isolated_chroma(state), 1)
                # Keep these alive: cleanup must come from stop(), not GC.
                self.assertIsNotNone(client)
                self.assertIsNotNone(collection)
                shutil.rmtree(index)
                self.assertFalse(index.exists())
            finally:
                close_isolated_chroma(state)

    def test_stop_preserves_a_system_outside_requested_temporary_root(self):
        from chromadb.api.shared_system_client import SharedSystemClient
        with tempfile.TemporaryDirectory(prefix='texeira-chroma-scope-') as directory:
            root = Path(directory)
            owned = root / 'owned'
            sibling = root / 'sibling'
            owned_client, _ = create_index(owned / 'index')
            sibling_client, sibling_collection = create_index(sibling / 'index')
            try:
                sibling_key = sibling_client._identifier
                sibling_system = SharedSystemClient._identifier_to_system[sibling_key]
                self.assertEqual(close_isolated_chroma(owned), 1)
                self.assertNotIn(owned_client._identifier, SharedSystemClient._identifier_to_system)
                self.assertIs(SharedSystemClient._identifier_to_system[sibling_key], sibling_system)
                self.assertEqual(sibling_collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)['ids'], [['one']])
                self.assertEqual(close_isolated_chroma(root), 1)
            finally:
                close_isolated_chroma(root)

    def test_runner_cleans_index_and_preserves_nonzero_target_exit(self):
        child_env = dict(os.environ, TEXEIRA_CHROMA_CLEANUP_PROBE='1')
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tests/run_isolated.py'), Path(__file__).name],
            cwd=ROOT, env=child_env, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=45)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        marker = 'CHROMA_CLEANUP_PROBE_DIR='
        paths = [line[len(marker):] for line in result.stdout.splitlines() if line.startswith(marker)]
        self.assertEqual(len(paths), 1, result.stdout + result.stderr)
        self.assertFalse(Path(paths[0]).exists(), 'Runner must remove its temporary state after target failure')
        self.assertIn('[ISOLATED] Closed 1 temporary Chroma system(s).', result.stdout)
        self.assertNotIn('WinError 32', result.stderr)


if __name__ == '__main__':
    if os.environ.get('TEXEIRA_CHROMA_CLEANUP_PROBE') == '1':
        state = Path(os.environ['TEXEIRA_STATE_DIR'])
        probe_client, probe_collection = create_index(state / 'cleanup-probe')
        print(f'CHROMA_CLEANUP_PROBE_DIR={state}', flush=True)
        raise SystemExit(7)
    unittest.main(verbosity=2)

"""Run one regression with temporary state, artifacts and index; no external network."""
import builtins
import errno
import io
import os
import runpy
import shutil
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ArtifactMirror:
    """Keep docs writes temporary and read the changed copy within this process.

    Path.read/write_text and Path.read/write_bytes use io.open, so they receive
    the same protection as builtins.open. Append/update modes copy the original
    first; untouched historical documents remain available for reading.
    """

    def __init__(self, source, destination, protected_index=None):
        self.source = Path(source).resolve()
        self.destination = Path(destination).resolve()
        self.protected = [self.source]
        if protected_index is not None:
            self.protected.append(Path(protected_index).resolve())
        self.audit_active = False

    def _is_protected(self, file):
        if isinstance(file, int):
            return False
        try:
            path = Path(os.path.abspath(os.fsdecode(os.fspath(file))))
        except TypeError:
            return False
        return any(candidate.is_relative_to(root)
                   for candidate in (path, Path(os.path.realpath(path))) for root in self.protected)

    def _audit(self, event, args):
        if not self.audit_active:
            return
        paths = []
        if event == 'open':
            file, mode, flags = args
            writing = (isinstance(mode, str) and any(flag in mode for flag in 'wax+'))
            writing = writing or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing:
                paths = [file]
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'shutil.rmtree', 'sqlite3.connect'):
            paths = [args[0]]
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            paths = args[:2]
        if any(self._is_protected(path) for path in paths):
            raise AssertionError(f'Original docs/index mutation prohibited during isolated regression: {event}')

    def _destination(self, file):
        if isinstance(file, int):
            return None
        try:
            path = Path(os.path.abspath(os.fsdecode(os.fspath(file))))
        except TypeError:
            return None
        # Cover both a path inside docs and another path resolving into docs.
        for candidate in (path, Path(os.path.realpath(path))):
            try:
                relative = candidate.relative_to(self.source)
            except ValueError:
                continue
            return self.destination / relative
        return None

    def _file(self, file, mode):
        mirror = self._destination(file)
        if mirror is None:
            return file
        writing = any(flag in mode for flag in 'wax+')
        if not writing:
            return mirror if mirror.exists() else file
        original = Path(os.fsdecode(file))
        if not mirror.parent.is_dir() and not original.parent.is_dir():
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(file))
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if 'x' in mode and (mirror.exists() or original.exists()):
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), os.fspath(file))
        if not mirror.exists() and ('a' in mode or ('+' in mode and 'w' not in mode)):
            if original.is_file():
                shutil.copy2(original, mirror)
        return mirror

    def __enter__(self):
        self.original_open = builtins.open
        self.original_io_open = io.open
        self.original_mkdir = Path.mkdir
        self.original_stat = Path.stat

        def mirror_open(file, mode='r', *args, **kwargs):
            return self.original_open(self._file(file, mode), mode, *args, **kwargs)

        def mirror_io_open(file, mode='r', *args, **kwargs):
            return self.original_io_open(self._file(file, mode), mode, *args, **kwargs)

        def mirror_mkdir(path, mode=0o777, parents=False, exist_ok=False):
            destination = self._destination(path)
            if destination is None:
                return self.original_mkdir(path, mode, parents, exist_ok)
            if path.exists() and not exist_ok:
                raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), os.fspath(path))
            if not parents and not destination.parent.is_dir() and not path.parent.is_dir():
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(path))
            if path.parent.is_dir():
                destination.parent.mkdir(parents=True, exist_ok=True)
            return self.original_mkdir(destination, mode, parents, exist_ok)

        def mirror_stat(path, *args, **kwargs):
            destination = self._destination(path)
            if destination is not None and destination.exists():
                return self.original_stat(destination, *args, **kwargs)
            return self.original_stat(path, *args, **kwargs)

        builtins.open = mirror_open
        io.open = mirror_io_open
        Path.mkdir = mirror_mkdir
        Path.stat = mirror_stat
        self.audit_active = True
        sys.addaudithook(self._audit)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.audit_active = False
        builtins.open = self.original_open
        io.open = self.original_io_open
        Path.mkdir = self.original_mkdir
        Path.stat = self.original_stat


def close_isolated_chroma(state):
    """Stop only persistent Chroma systems owned by this temporary regression.

    Chroma 0.6 keeps systems in a shared cache even after retrievers disappear.
    System.stop closes the HNSW file handles and SQLite pools on Windows; merely
    dropping cache references does not. Do not import Chroma for unused suites.
    """
    module = sys.modules.get('chromadb.api.shared_system_client')
    if module is None:
        return 0
    cache = module.SharedSystemClient._identifier_to_system
    temporary_root = Path(state).resolve()
    stopped = set()
    for key, system in list(cache.items()):
        if not system.settings.is_persistent:
            continue
        persistence = Path(system.settings.persist_directory).resolve()
        if not persistence.is_relative_to(temporary_root):
            continue
        if id(system) not in stopped:
            system.stop()
            stopped.add(id(system))
        if cache.get(key) is system:
            del cache[key]
    return len(stopped)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    target = (ROOT / 'tests' / sys.argv[1]).resolve()
    if target.parent != ROOT / 'tests' or not target.is_file():
        raise ValueError('Specify a test filename inside tests/')
    with tempfile.TemporaryDirectory(prefix='texeira-regression-') as directory:
        state = Path(directory)
        # También aislar consumidores antiguos con rutas SQLite relativas.
        os.chdir(state)
        os.environ.update(DATABASE_URL='', TEXEIRA_STATE_DIR=directory,
            TEXEIRA_ISOLATED_TEST='1',
            SQLITE_DB_PATH=str(state / 'trial_logs.db'),
            TEXEIRA_ENABLE_WHATSAPP='false', TEXEIRA_ENABLE_MESSENGER='false',
            TEXEIRA_ENABLE_ADVISOR_NOTIFICATIONS='false',
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
            CHROMA_PERSIST_DIR=str(state / 'index'),
            CHROMA_HYBRID_DIR=str(state / 'index'),
            ADMIN_USER='', ADMIN_PASSWORD='', K_SERVICE='', ALLOW_CLOUD_RUN='')
        import runtime_settings
        original_configure = runtime_settings.configure
        runtime_settings.configure = lambda env=None, values=None: original_configure(env=env, values={})
        original_connect = socket.socket.connect
        def guarded_connect(sock, address):
            if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
                return original_connect(sock, address)
            raise AssertionError('External network prohibited during isolated regression')
        socket.socket.connect = guarded_connect
        trial_support = None
        original_index = None
        try:
            import catalog_service
            copied = state / 'catalog.json'
            shutil.copyfile(catalog_service.CATALOG_JSON_PATH, copied)
            catalog_service.CATALOG_JSON_PATH = copied
            catalog_service.IMAGES_DIR = state / 'images'
            catalog_service.BROCHURES_DIR = state / 'brochures'
            catalog_service.IMAGES_DIR.mkdir()
            catalog_service.BROCHURES_DIR.mkdir()
            import trial_support
            original_index = trial_support.INDEX
            isolated_index = state / 'index'
            if original_index.is_dir():
                shutil.copytree(original_index, isolated_index)
            else:
                isolated_index.mkdir()
            trial_support.INDEX = isolated_index
            trial_support.retriever.cache_clear()
            docs_mirror = state / 'docs'
            docs_mirror.mkdir()
            os.environ['TEXEIRA_ISOLATED_DOCS_DIR'] = str(docs_mirror)
            os.environ['TEXEIRA_ISOLATED_INDEX_DIR'] = str(isolated_index)
            sys.argv = [str(target)]
            with ArtifactMirror(ROOT / 'docs', docs_mirror, protected_index=original_index):
                runpy.run_path(str(target), run_name='__main__')
        finally:
            try:
                if trial_support is not None:
                    trial_support.retriever.cache_clear()
                closed = close_isolated_chroma(state)
                if closed:
                    print(f'[ISOLATED] Closed {closed} temporary Chroma system(s).', flush=True)
            finally:
                if trial_support is not None and original_index is not None:
                    trial_support.INDEX = original_index
                socket.socket.connect = original_connect
                runtime_settings.configure = original_configure
                os.chdir(ROOT)

if __name__ == '__main__':
    main()

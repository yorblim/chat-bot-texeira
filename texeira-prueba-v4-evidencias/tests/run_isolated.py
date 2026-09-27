"""Run one local regression with temporary data and external networking blocked."""
import os
import runpy
import shutil
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
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
        import catalog_service
        copied = state / 'catalog.json'
        shutil.copyfile(catalog_service.CATALOG_JSON_PATH, copied)
        catalog_service.CATALOG_JSON_PATH = copied
        catalog_service.IMAGES_DIR = state / 'images'
        catalog_service.BROCHURES_DIR = state / 'brochures'
        catalog_service.IMAGES_DIR.mkdir()
        catalog_service.BROCHURES_DIR.mkdir()
        sys.argv = [str(target)]
        try:
            runpy.run_path(str(target), run_name='__main__')
        finally:
            os.chdir(ROOT)

if __name__ == '__main__':
    main()

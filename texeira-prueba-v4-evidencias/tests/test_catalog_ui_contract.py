"""Exercise the rendered JavaScript against a minimal DOM and synthetic API."""
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog_ui import get_catalog_html

html = get_catalog_html('synthetic-csrf')
script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
result = subprocess.run(['C:/Program Files/nodejs/node.exe',
                         str(Path(__file__).with_suffix('.js'))],
                        input=script, text=True, encoding='utf-8', capture_output=True)
print(result.stdout)
print(result.stderr, file=sys.stderr)
raise SystemExit(result.returncode)

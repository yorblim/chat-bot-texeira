"""Independent rate-save regressions; real UI JavaScript, synthetic DOM/API only."""
import os
import re
import subprocess
from pathlib import Path

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run via tests/run_isolated.py")

from catalog_ui import get_catalog_html

script = re.search(r"<script>(.*?)</script>", get_catalog_html("review-csrf"), re.S).group(1)
result = subprocess.run(
    ["C:/Program Files/nodejs/node.exe", str(Path(__file__).with_suffix(".js"))],
    input=script, text=True, encoding="utf-8", capture_output=True,
)
print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)

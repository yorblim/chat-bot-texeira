import os

tests_dir = os.path.join('texeira-prueba-v4-evidencias', 'tests')
bootstrap = "import sys, os\nsys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))\n"

count = 0
for f in os.listdir(tests_dir):
    if f.endswith('.py') and f not in ('conftest.py', '__init__.py'):
        path = os.path.join(tests_dir, f)
        with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()
        if 'sys.path.insert(0' not in content:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write(bootstrap + content)
            count += 1

print(f"Bootstrap inyectado en {count} scripts de prueba.")

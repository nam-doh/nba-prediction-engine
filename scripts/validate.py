"""Offline syntax and notebook structure checks; never execute training."""
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for folder in ('src', 'scripts', 'tests'):
    for path in (root / folder).rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
for path in (root / 'notebooks').glob('*.ipynb'):
    notebook = json.loads(path.read_text())
    assert notebook['nbformat'] == 4 and isinstance(notebook['cells'], list), path
print('Python syntax and notebook structure valid; no training/holdout execution.')

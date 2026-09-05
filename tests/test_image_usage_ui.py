"""The shared usage control preserves the existing saved values and label binding."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_shared_usage_control_preserves_saved_mode_and_backend_field():
    if not shutil.which('node'):
        pytest.skip('Node is only needed for the frontend developer check')
    script = """
      import {readFileSync} from 'node:fs';
      const source = readFileSync('static/boundaries.js', 'utf8');
      const {boundaryUsageField} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
      console.log(JSON.stringify([boundaryUsageField(), boundaryUsageField('commercial'), boundaryUsageField('education_nc')]));
    """
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', check=True)
    default, commercial, educational = json.loads(result.stdout)
    assert default == commercial
    for html in (commercial, educational):
        assert 'id="boundary_usage"' in html and 'for="boundary_usage"' in html
        assert 'Destinazione d’uso di mappe e immagini' in html
        assert 'Commons' in html and 'Openverse' in html and 'CShapes' in html
        assert html.count(' selected') == 1
    assert 'value="commercial" selected' in commercial
    assert 'value="education_nc" selected' in educational

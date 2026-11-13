"""Contract-only stand-ins, used only until WP1/WP2 publish their modules."""
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def missing(name):
    return importlib.util.find_spec(name) is None

if missing('modelproof.data'):
    data = types.ModuleType('modelproof.data')
    data.PROTECTED = ['SEX', 'MARRIAGE', 'AGE_BAND', 'EDUCATION']
    data.age_band = lambda age: pd.cut(age, [-float('inf'),25,35,45,55,float('inf')], right=False, labels=['<25','25-34','35-44','45-54','55+'])
    sys.modules[data.__name__] = data
@pytest.fixture(autouse=True)
def isolate_artifacts(tmp_path, monkeypatch):
    from modelproof import config
    monkeypatch.setattr(config, 'ARTIFACTS', tmp_path / 'artifacts')
    monkeypatch.setattr(config, 'ROOT', ROOT)

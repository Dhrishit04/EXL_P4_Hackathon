"""Contract-only stand-ins, used only until WP1/WP2 publish their modules."""
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def missing(name):
    return importlib.util.find_spec(name) is None

if missing('modelproof.schemas'):
    spec = importlib.util.spec_from_file_location('modelproof.schemas', Path(__file__).with_name('_contract_schemas.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
if missing('modelproof.config'):
    config = types.ModuleType('modelproof.config')
    config.ROOT = ROOT
    config.ARTIFACTS = ROOT / 'artifacts'
    config.REBUILT = ROOT / 'rebuilt'
    config.LEGACY = ROOT / 'legacy_estate'
    config.MODELS = {}
    config.load_policy = lambda: yaml.safe_load((Path(__file__).parent / 'fixtures/policy.yaml').read_text())
    def artifact_dir(model_id):
        path = config.ARTIFACTS / model_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    config.artifact_dir = artifact_dir
    sys.modules[config.__name__] = config
if missing('modelproof.data'):
    data = types.ModuleType('modelproof.data')
    data.PROTECTED = ['SEX', 'MARRIAGE', 'AGE_BAND', 'EDUCATION']
    data.age_band = lambda age: pd.cut(age, [-float('inf'),25,35,45,55,float('inf')], right=False, labels=['<25','25-34','35-44','45-54','55+'])
    sys.modules[data.__name__] = data
if missing('modelproof.audit'):
    audit = types.ModuleType('modelproof.audit')
    audit.append = lambda *args, **kwargs: 'test-only-audit'
    audit.read = list
    sys.modules[audit.__name__] = audit

@pytest.fixture(autouse=True)
def isolate_artifacts(tmp_path, monkeypatch):
    from modelproof import config
    monkeypatch.setattr(config, 'ARTIFACTS', tmp_path / 'artifacts')

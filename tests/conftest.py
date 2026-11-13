"""Put src/ on the path; fall back to test-only stubs for WP1 modules not yet on main."""
import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for name in ("config", "schemas", "audit", "llm"):
    try:
        importlib.import_module(f"modelproof.{name}")
    except ModuleNotFoundError:
        stub = ROOT / "tests/_stubs" / f"{name}.py"
        if stub.exists():
            spec = importlib.util.spec_from_file_location(f"modelproof.{name}", stub)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"modelproof.{name}"] = mod
            spec.loader.exec_module(mod)

"""Python fact extractor (ast)."""
import ast
import re
from collections.abc import Callable
from pathlib import Path

ESTIMATOR = re.compile(r"(Classifier|Regressor|Regression|SVC|GLM|Logit)$")


def strs(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def fname(call: ast.Call) -> str:
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")


def extract(path: Path, ev: Callable[[int, int], str]) -> dict:
    tree = ast.parse(path.read_text())
    r = {k: [] for k in ("datasets_read", "datasets_written", "variables_created", "variables_used", "model_calls")}
    r.update(parameters={}, target=None, libnames={})
    seen: list[str] = []  # every name / column string, one entry per occurrence
    frames: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        r["variables_created"].append(x.id)
                if isinstance(t, ast.Subscript) and strs(t.slice):
                    r["variables_created"].append(strs(t.slice)[0])
            if isinstance(n.value, ast.Call) and fname(n.value) == "read_csv":
                frames |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    created_nodes = {id(x) for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets for x in ast.walk(t)}
    for n in ast.walk(tree):
        if id(n) in created_nodes:
            continue
        if isinstance(n, ast.Name):
            seen.append(n.id)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            seen.append(n.value)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in frames:
            seen.append(n.attr)
        if isinstance(n, ast.Call):
            e, f = ev(n.lineno, n.end_lineno), fname(n)
            if f in ("read_csv", "to_csv"):
                (r["datasets_read"] if f == "read_csv" else r["datasets_written"]).extend(s for s in strs(n) if s.endswith((".csv", ".parquet")))
            elif ESTIMATOR.search(f):
                r["model_calls"].append({"kind": f, "text": ast.unparse(n), "evidence_id": e})
                r["parameters"].update({k.arg: {"value": ast.unparse(k.value), "evidence_id": e} for k in n.keywords})
            elif f == "train_test_split":
                r["parameters"].update({k.arg: {"value": ast.unparse(k.value), "evidence_id": e} for k in n.keywords if isinstance(k.value, ast.Constant)})
                y = n.args[1]
                if isinstance(y, ast.Attribute):
                    r["target"] = y.attr
                elif isinstance(y, ast.Subscript) and strs(y.slice):
                    r["target"] = strs(y.slice)[0]
    r["variables_used"] = seen
    return r

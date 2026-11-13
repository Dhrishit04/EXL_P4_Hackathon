"""Static checks and an isolated pytest run for LLM generated code."""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWED = {"numpy", "pandas", "math", "statsmodels", "scipy"}
# whole modules are unsafe (typing.sys, get_type_hints evaluates strings) but a fixed set of names is fine for type hints
NAMED = {"typing": {"Any", "Callable", "Iterable", "Sequence", "Mapping", "Optional", "Union", "Literal", "Tuple", "List", "Dict"},
         "__future__": {"annotations"}}
BANNED_NAMES = {"eval", "exec", "compile", "open", "__import__", "__builtins__", "getattr", "setattr", "delattr",
                "globals", "locals", "vars", "breakpoint", "input"}
# file / process access reachable through the allowed libraries
BANNED_ATTRS = {"eval", "exec", "popen", "system", "load", "loads", "loadtxt", "genfromtxt", "fromfile", "fromregex",
                "save", "savez", "savetxt", "tofile", "memmap", "open_memmap", "loadmat", "savemat", "to_csv",
                "to_pickle", "to_parquet", "to_excel", "to_json", "to_sql", "to_feather", "to_hdf", "to_stata",
                "to_clipboard", "to_html", "to_latex", "to_markdown", "to_xml", "to_orc",
                # modules re-exported by the allowed libraries
                "sys", "os", "subprocess", "builtins", "importlib", "shutil", "pathlib", "socket", "modules", "io", "compat",
                "testing", "ctypeslib", "f2py", "distutils", "ctypes", "typing",
                # string evaluated entry points (patsy formulas and pandas query run code from strings)
                "query", "from_formula", "formula"}


# Methods that look a method up BY NAME from a string (so a string reaches banned or private attributes).
# STRICT: every argument must be a reducer name, a callable reference or a literal; anything computed is rejected.
STRICT = {"agg", "aggregate", "apply", "transform"}
AGGFUNC = {"pivot_table", "crosstab"}  # their other strings are column names; only `aggfunc` dispatches
WEAK = {"map", "applymap", "pipe"}  # no name dispatch, but a string constant must still be a reducer
REDUCERS = {"sum", "mean", "min", "max", "count", "std", "var", "median", "first", "last", "size", "nunique", "prod"}


SAFE_BUILTINS = {"len", "abs", "round", "float", "int", "str", "bool", "min", "max", "sum", "sorted"}


def _scope(tree: ast.AST) -> set[str]:
    """Names that provably hold callables: bound exactly once, by an import or a def, and never assigned to,
    looped over, captured, shadowed by a parameter or have an attribute assigned. Builtins only if never bound."""
    binds: dict[str, int] = {}
    good: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import | ast.ImportFrom):
            names = [(a.asname or a.name).split(".")[0] for a in n.names]
            good |= set(names)
        elif isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names = [n.name]
            if not isinstance(n, ast.ClassDef):
                good.add(n.name)
        elif isinstance(n, ast.arg):
            names = [n.arg]
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store | ast.Del):
            names = [n.id]
        elif isinstance(n, ast.Global | ast.Nonlocal):
            names = list(n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names = [n.name]
        else:
            continue
        for x in names:
            binds[x] = binds.get(x, 0) + 1
    for n in ast.walk(tree):  # np.sum = ...  /  del np.sum  /  setattr is banned elsewhere
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store | ast.Del):
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                binds[n.id] = binds.get(n.id, 0) + 2
    return {x for x in good if binds.get(x) == 1} | {x for x in SAFE_BUILTINS if x not in binds}


def _func_ok(x: ast.expr, ok: set[str]) -> bool:
    if isinstance(x, ast.Attribute):  # np.log, math.sqrt: rooted in an imported library
        while isinstance(x, ast.Attribute):
            x = x.value
        return isinstance(x, ast.Name) and x.id in ok
    return isinstance(x, ast.Lambda) or (isinstance(x, ast.Name) and x.id in ok) or (
        isinstance(x, ast.Constant) and (not isinstance(x.value, str) or x.value in REDUCERS))


def _arg_ok(x: ast.expr, ok: set[str], named: bool = False) -> bool:
    if isinstance(x, ast.List | ast.Tuple):
        if named and len(x.elts) == 2 and isinstance(x.elts[0], ast.Constant) and isinstance(x.elts[0].value, str):
            return _func_ok(x.elts[1], ok)  # named aggregation: (column, reducer)
        return all(_func_ok(e, ok) for e in x.elts)
    return all(_func_ok(v, ok) for v in x.values) if isinstance(x, ast.Dict) else _func_ok(x, ok)


def dispatch_violations(call: ast.Call, name: str, ok: set[str]) -> list[str]:
    if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
        return [f"line {call.lineno}: .{name}(*args / **kwargs) is not allowed"]
    if name in STRICT:  # the (column, reducer) tuple shape is only for new-column keywords, never func= / arg= / f=
        args = [(a, False) for a in call.args] + [(k.value, k.arg not in ("func", "arg", "f")) for k in call.keywords]
    elif name in AGGFUNC:  # aggfunc is positional #4 (DataFrame.pivot_table), #5 (pd.pivot_table) or #6 (crosstab)
        args = [(a, False) for a in call.args[3 if name == "pivot_table" else 5:]] + [(k.value, False) for k in call.keywords if k.arg == "aggfunc"]
    else:  # WEAK: only constant strings are judged
        args = [(a, False) for a in call.args[:1] if isinstance(a, ast.Constant)] + [
            (k.value, False) for k in call.keywords if k.arg in ("func", "arg", "f") and isinstance(k.value, ast.Constant)]
    return [f"line {call.lineno}: .{name}() argument is not a reducer name or a provable callable" for a, n in args if not _arg_ok(a, ok, n)]


def risky(parts: list[str]) -> bool:
    """A dotted import path or imported name that is a banned attribute, private, or a star import."""
    return any(p == "*" or p.startswith("_") or p in BANNED_ATTRS for p in parts)


def check_code(code: str, allow: tuple[str, ...] = ()) -> list[str]:
    """Violations of the allowlist (empty list = OK). `allow` adds import roots, e.g. for generated tests."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"line {e.lineno}: syntax error: {e.msg}"]
    ok, bad, scope = ALLOWED | set(allow), [], _scope(tree)
    for n in ast.walk(tree):
        line = getattr(n, "lineno", 0)
        if isinstance(n, ast.Import):
            bad += [f"line {line}: import {a.name} is not allowed" for a in n.names if a.name.split(".")[0] not in ok or risky(a.name.split("."))]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in NAMED:
            bad += [f"line {line}: from {n.module} import {a.name} is not allowed" for a in n.names if a.name not in NAMED[n.module]]
        elif isinstance(n, ast.ImportFrom) and (n.level or (n.module or "").split(".")[0] not in ok
                                                or risky((n.module or "").split(".") + [a.name for a in n.names])):
            bad.append(f"line {line}: from {'.' * n.level}{n.module or ''} import {', '.join(a.name for a in n.names)} is not allowed")
        elif isinstance(n, ast.Match) or getattr(n, "decorator_list", None):  # rebinding the scope check cannot see
            bad.append(f"line {line}: decorators and match statements are not allowed")
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in STRICT | AGGFUNC | WEAK:
            bad += dispatch_violations(n, n.func.attr, scope)
        elif isinstance(n, ast.Name) and n.id in BANNED_NAMES:
            bad.append(f"line {line}: {n.id} is not allowed")
        elif isinstance(n, ast.Attribute) and (n.attr.startswith("_") or "__" in n.attr or n.attr in BANNED_ATTRS or n.attr.startswith("read_")):
            bad.append(f"line {line}: attribute .{n.attr} is not allowed")
    return bad


def run_pytest(workdir: Path, timeout: int = 120) -> tuple[bool, str]:
    """pytest in a temp copy of workdir, isolated interpreter, secrets stripped from the environment."""
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_KEY", "_TOKEN", "_SECRET"))}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(workdir, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        try:
            r = subprocess.run([sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=work,
                               env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"pytest timed out after {timeout}s"
    return r.returncode == 0, (r.stdout + r.stderr)[-4000:]


def check_tests(code: str) -> list[str]:
    """Generated tests: plain asserts on the module only. No pytest import and no fixtures, because
    `pytest.importorskip` and `monkeypatch.setattr("os.system", ...)` import arbitrary modules by name."""
    bad = check_code(code, allow=("cr_pd_002",))
    if bad and bad[0].endswith("syntax error"):
        return bad
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test"):
            args = [a.arg for a in n.args.posonlyargs + n.args.args + n.args.kwonlyargs if a.arg != "self"] + [a.arg for a in (n.args.vararg, n.args.kwarg) if a]
            bad += [f"line {n.lineno}: test function {n.name} must take no arguments (fixture {a} is not allowed)" for a in args]
    return bad

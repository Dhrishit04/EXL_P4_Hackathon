"""Code fact extraction (WP2): dispatch by file type, collect Evidence, write artifacts/<id>/facts.json."""
import hashlib
import re
from pathlib import Path

from modelproof import config
from modelproof.extract import py, r, sas
from modelproof.schemas import Evidence, Facts

LANG = {".sas": ("SAS", sas), ".R": ("R", r), ".py": ("Python", py)}


def evidence_id(model_id: str, name: str, a: int, b: int) -> str:
    return f"{model_id}:{name}:L{a}" + (f"-L{b}" if b != a else "")


def source_files(model_id: str) -> list[Path]:
    """Code and old documents of a model folder. SCENARIO.md (estate disclosure) and golden/ are not model inputs."""
    return sorted(p for p in config.model_dir(model_id).iterdir() if p.is_file() and p.name != "SCENARIO.md" and p.suffix in {*LANG, ".md", ".txt"})


def _resolve(name: str, libs: dict[str, str]) -> str:
    lib, _, member = name.partition(".")
    return f"{libs.get(lib.lower(), lib)}/{member}".lower() if member else name.lower()


def _stale_comment(lines: list[str], line: int, name: str, value: str) -> tuple[int, str] | None:
    """A number written beside `name` in a comment on the previous or same line that differs from the code value."""
    pat = re.compile(rf"{name.replace('_', '[ _]')}\W+(\d[\d.]*)", re.IGNORECASE)
    for n in (line - 1, line):
        c = re.search(r"/\*(.*?)\*/|#(.*)$", lines[n - 1]) if n else None
        if c and (m := pat.search(c[1] or c[2])) and m[1] != value:
            return n, m[1]


def collect(model_id: str) -> dict:
    from modelproof import security  # lazy: security imports this package

    ev: dict[str, Evidence] = {}
    out = {"files": [], "lang": None, "libs": {}, "calls": [], "params": {}, "target": None,
           "proxy": [], **{k: [] for k in ("datasets_read", "datasets_written", "variables_created", "variables_used")}}
    hit_lines = {(p, n) for p, n, _ in security.hits(model_id)}
    for p in source_files(model_id):
        data = p.read_bytes()
        lines = data.decode().splitlines()
        rel, sha, code = p.relative_to(config.ROOT).as_posix(), hashlib.sha256(data).hexdigest(), p.suffix in LANG

        def mk(a: int, b: int | None = None, p=p, rel=rel, sha=sha, code=code, lines=lines) -> str:
            b = b or a
            i = evidence_id(model_id, p.name, a, b)
            ev.setdefault(i, Evidence(id=i, kind="code" if code else "doc", path=rel, line_start=a, line_end=b,
                                      excerpt="\n".join(lines[a - 1:b])[:1500], sha256=sha))
            return i

        out["files"].append({"path": rel, "sha256": sha, "n_lines": len(lines), "kind": "code" if code else "doc"})
        for n in sorted(n for q, n in hit_lines if q == p):
            mk(n)
        if not code:
            for n, ln in enumerate(lines, 1):
                if ln.strip():
                    mk(n)
            continue
        out["lang"], mod = LANG[p.suffix]
        x = mod.extract(p, mk)
        for a in range(1, len(lines) + 1, 6):  # 6 line blocks so every code line is citable
            if any(ln.strip() for ln in lines[a - 1:a + 5]):
                mk(a, min(a + 5, len(lines)))
        for v in dict.fromkeys(x["variables_used"]):
            if v.lower() in security.PROXY:
                n = next(i for i, ln in enumerate(lines, 1) if re.search(rf"\b{v}\b", ln, re.I) and not ln.lstrip().startswith(("/*", "#", "*")))
                out["proxy"].append((v, mk(n), lines[n - 1].strip()))
        for k in ("datasets_read", "datasets_written", "variables_created", "variables_used"):
            out[k] += x[k]
        for name, v in x["parameters"].items():
            out["params"].setdefault(name, v)
            if (s := _stale_comment(lines, ev[v["evidence_id"]].line_start, name, v["value"])) and f"{name}_comment" not in out["params"]:
                out["params"][f"{name}_comment"] = {"value": s[1], "evidence_id": mk(s[0], ev[v["evidence_id"]].line_end)}
        out["calls"] += x["model_calls"]
        out["libs"].update(x["libnames"])
        out["target"] = out["target"] or x["target"]
    out["evidence"] = list(ev.values())
    return out


def facts_for(model_id: str) -> Facts:
    c = collect(model_id)
    reads = {_resolve(n, c["libs"]) for n in c["datasets_read"]}
    deps = []
    for other in config.MODELS:
        if other != model_id:
            o = collect(other)
            if reads & {_resolve(n, o["libs"]) for n in o["datasets_written"]}:
                deps.append(other)

    def uniq(xs: list) -> list:
        return list(dict.fromkeys(xs))

    used = set(c["variables_used"])
    facts = Facts(
        model_id=model_id, language=c["lang"], files=c["files"], datasets_read=uniq(c["datasets_read"]),
        datasets_written=uniq(c["datasets_written"]), variables_created=uniq(c["variables_created"]),
        variables_used=uniq(c["variables_used"]), dead_variables=[v for v in uniq(c["variables_created"]) if v not in used],
        model_calls=c["calls"], target=c["target"], parameters=c["params"], dependencies=deps, evidence=c["evidence"])
    (config.artifact_dir(model_id) / "facts.json").write_text(facts.model_dump_json(indent=2))
    return facts

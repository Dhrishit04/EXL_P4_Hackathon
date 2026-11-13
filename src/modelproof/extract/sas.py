"""SAS fact extractor: statement level regexes (comments blanked, line numbers kept)."""
import re
from collections.abc import Callable
from pathlib import Path

KEYWORDS = {"if", "then", "else", "in", "and", "or", "not", "eq", "ne", "lt", "gt", "le", "ge", "do", "end"}
IDS = re.compile(r"\b[A-Za-z_]\w*\b(?!\s*\()")


def ids(expr: str) -> list[str]:
    expr = re.sub(r"'[^']*'|\"[^\"]*\"|&\w+\.?", " ", expr)
    return [i for i in IDS.findall(expr) if i.lower() not in KEYWORDS]


def ds(names: str) -> list[str]:  # permanent datasets only; WORK is scratch
    return [n for n in re.sub(r"\([^)]*\)", " ", names).split() if "." in n and not n.lower().startswith("work.")]


def extract(path: Path, ev: Callable[[int, int], str]) -> dict:
    clean = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), path.read_text(), flags=re.DOTALL)
    r = {k: [] for k in ("datasets_read", "datasets_written", "variables_created", "variables_used", "model_calls")}
    r.update(parameters={}, target=None, libnames={})
    proc = "PROC"
    for m in re.finditer(r"[^;]*;", clean):
        s = m.group().strip(" \n\t;")
        a = clean.count("\n", 0, m.start() + len(m.group()) - len(m.group().lstrip())) + 1
        e = ev(a, clean.count("\n", 0, m.end()) + 1)
        param = lambda k, v, e=e: r["parameters"].setdefault(k, {"value": v, "evidence_id": e})
        s = re.sub(r"^ELSE\s+", "", s, flags=re.IGNORECASE)
        if x := re.match(r"%LET\s+(\w+)\s*=\s*(.*)$", s, re.IGNORECASE):
            param(x[1], x[2].strip())
        elif x := re.match(r"LIBNAME\s+(\w+)\s+[\"'](.*?)[\"']", s, re.IGNORECASE):
            r["libnames"][x[1].lower()] = x[2]
        elif x := re.match(r"DATA\s+(.*)$", s, re.IGNORECASE):
            r["datasets_written"] += ds(x[1])
        elif x := re.match(r"(?:SET|MERGE)\s+(.*)$", s, re.IGNORECASE):
            r["datasets_read"] += ds(x[1])
        elif x := re.match(r"(PROC\s+\w+|SCORE(?=\s+(?:DATA|OUT)\b))\s*(.*)$", s, re.IGNORECASE):
            proc = " ".join(x[1].upper().split()) if x[1].upper() != "SCORE" else proc
            for opt, key in (("DATA|INMODEL", "datasets_read"), ("OUT|OUTEST|OUTMODEL", "datasets_written")):
                if y := re.search(rf"\b(?:{opt})\s*=\s*(\S+)", x[2], re.IGNORECASE):
                    r[key] += ds(y[1])
        elif x := re.match(r"MODEL\s+(\w+)\s*=\s*([^/]*)", s, re.IGNORECASE):
            r["target"] = r["target"] or x[1]
            r["variables_used"] += ids(x[2])
            r["model_calls"].append({"kind": proc, "text": " ".join(s.split()), "evidence_id": e})
        elif re.match(r"(?:KEEP|WHERE)\s", s, re.IGNORECASE):
            r["variables_used"] += ids(s.split(None, 1)[1])
        else:
            if c := re.match(r"IF\s+(.*?)\s+THEN\s+(.*)$", s, re.IGNORECASE):
                r["variables_used"] += ids(c[1])
                s = c[2]
                if (g := re.match(r"\w+\s*>=\s*(\d+)$", c[1])) and (y := re.match(r"grade\s*=\s*'(\w)'", s, re.IGNORECASE)):
                    param(f"grade_{y[1]}_min", g[1])
                if g := re.search(r"ranuni\((\d+)\)\s*<\s*([\d.]+)", c[1], re.IGNORECASE):
                    param("dev_sample_share", g[2])
            elif re.match(r"IF\s", s, re.IGNORECASE):
                r["variables_used"] += ids(s[3:])
            if x := re.match(r"(\w+)\s*=\s*(.+)$", s):
                r["variables_created"].append(x[1])
                r["variables_used"] += ids(x[2])
                if x[1].lower() == "score" and re.search(r"\bROUND\s*\(", x[2], re.IGNORECASE):
                    param("rounding", "SAS ROUND (half away from zero)")
    return r

"""R fact extractor: regex tokenizer over comment-stripped source (base R, no parser dependency)."""
import re
from collections.abc import Callable
from pathlib import Path

TOK = re.compile(r"\"[^\"]*\"|'[^']*'|[A-Za-z_.][\w.]*|\d[\d.eE]*|<<-|<-|=|[()$,\[\]{};~]")
CONST = re.compile(r"^([A-Z][A-Z0-9_]*)\s*<-\s*(-?[\d.]+|c\([-\d.,\s]+\))\s*$")


def tokens(clean: list[str]) -> list[tuple[int, str, str]]:
    """(line, type, text); type in sym | fn | arg | str | assign | op. Function formals are skipped."""
    out, depth, formals = [], 0, None
    for n, line in enumerate(clean, 1):
        for m in TOK.finditer(line):
            t = m.group()
            if t in ("(", ")"):
                depth += 1 if t == "(" else -1
                if formals is not None and depth == formals:
                    formals = None
            if t[0] in "\"'":
                out.append((n, "str", t[1:-1]))
            elif t in ("<-", "<<-") or (t == "=" and depth == 0):
                out.append((n, "assign", t))
            elif re.match(r"[A-Za-z_.]", t):
                nxt = line[m.end():].lstrip()[:1]
                if formals is not None:
                    continue
                if t == "function":
                    formals = depth
                is_arg = depth > 0 and re.match(r"=(?!=)", line[m.end():].lstrip())
                out.append((n, "fn" if nxt == "(" else "arg" if is_arg else "sym", t))
            else:
                out.append((n, "op", t))
    return out


def extract(path: Path, ev: Callable[[int, int], str]) -> dict:
    clean = [re.sub(r"#.*$", "", ln) for ln in path.read_text().splitlines()]
    toks = tokens(clean)
    r = {k: [] for k in ("datasets_read", "datasets_written", "variables_created", "variables_used", "model_calls")}
    r.update(parameters={}, target=None, libnames={})
    lhs = set()
    for i, (n, tp, _) in enumerate(toks):
        if tp != "assign":
            continue
        k = i
        while k > 0 and toks[k - 1][0] == n and toks[k - 1][2] not in ";{}":
            k -= 1
        j = next((j for j in range(k, i) if toks[j][1] == "sym"), None)
        if j is not None:
            if j + 2 < i and toks[j + 1][2] == "$" and toks[j + 2][1] == "sym":
                j += 2
            lhs.add(j)
            r["variables_created"].append(toks[j][2])
    made = set(r["variables_created"])  # a string naming a created variable counts as a use (dynamic access, b[[ft]])
    r["variables_used"] = [t for i, (_, tp, t) in enumerate(toks)
                           if (tp in ("sym", "fn") and i not in lhs) or (tp == "str" and t in made)]
    for i, (n, tp, t) in enumerate(toks):
        if tp != "fn" or t not in ("read.csv", "write.csv", "glm", "lm"):
            continue
        if t in ("glm", "lm"):
            s = "\n".join(clean[n - 1:])
            a = s.index(t + "(")
            d = 0
            for b in range(a, len(s)):
                d += (s[b] == "(") - (s[b] == ")")
                if d == 0 and s[b] == ")":
                    break
            call = " ".join(s[a:b + 1].split())
            r["model_calls"].append({"kind": t, "text": call, "evidence_id": ev(n, n + s[a:b].count("\n"))})
            r["target"] = r["target"] or re.match(rf"{t}\(\s*(\w+)\s*~", call)[1]
        else:
            strs, d = [], 0
            for _, tp2, t2 in toks[i + 1:]:
                d += (t2 == "(") - (t2 == ")")
                strs += [t2] if tp2 == "str" else []
                if d == 0:
                    break
            name = strs[-2] + "*" + strs[-1] if len(strs) > 1 and strs[-1].startswith(".") else strs[-1]
            r["datasets_read" if t == "read.csv" else "datasets_written"].append(name)
    for n, ln in enumerate(clean, 1):
        if c := CONST.match(ln.strip()):
            r["parameters"][c[1]] = {"value": c[2], "evidence_id": ev(n, n)}
        if re.search(r"\bscore\s*<-\s*round\(", ln):
            r["parameters"].setdefault("rounding", {"value": "R round (half to even)", "evidence_id": ev(n, n)})
    return r

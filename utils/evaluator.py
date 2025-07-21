# utils/evaluator.py
import re
import datetime

class Evaluator:
    """Evaluator for live preview with token & function support."""

    FUNC_RE = re.compile(r"\$(\w+)\(([^)]*)\)")

    def __init__(self, meta: dict[str, str]):
        self.meta = meta

    def _list_token(self, base: str, all_: list[str], idx: int | None = None) -> str:
        if idx is None:
            return " ".join(all_)
        if 0 <= idx < len(all_):
            return all_[idx]
        return ""

    def _eval_func(self, match: re.Match) -> str:
        func = match.group(1).lower()
        args_raw = match.group(2)
        args = self._split_args(args_raw)

        def resolve(arg: str) -> str:
            arg = arg.strip()
            if arg.startswith("%") and arg.endswith("%"):
                return self.meta.get(arg[1:-1], "")
            if arg in self.meta:
                return self.meta.get(arg, "")
            return arg

        # ── string helpers ───────────────────────────────────────────
        if func == "upper"  and len(args) == 1: return resolve(args[0]).upper()
        if func == "lower"  and len(args) == 1: return resolve(args[0]).lower()
        if func == "title"  and len(args) == 1: return resolve(args[0]).title()
        if func == "len"    and len(args) == 1: return str(len(resolve(args[0])))

        if func == "substr" and 2 <= len(args) <= 3:
            txt = resolve(args[0]); start = int(args[1]); end = int(args[2]) if len(args)==3 else None
            return txt[start:end]

        if func == "left"   and len(args) == 2: return resolve(args[0])[:int(args[1])]
        if func == "right"  and len(args) == 2: return resolve(args[0])[-int(args[1]):]

        if func == "replace" and len(args) == 3:
            return resolve(args[0]).replace(args[1], args[2])

        if func == "pad" and len(args) >= 2:
            txt, n   = resolve(args[0]), int(args[1])
            ch       = args[2] if len(args) == 3 else " "
            return txt.ljust(n, ch)

        # ── date/time helpers ────────────────────────────────────────
        if func == "datetime" and len(args) == 0:
            return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if func in ("year", "month", "day") and len(args) == 1:
            val = resolve(args[0])
            try:
                dt = datetime.datetime.strptime(val, "%Y-%m-%d")
                return {
                    "year":  str(dt.year),
                    "month": f"{dt.month:02d}",
                    "day":   f"{dt.day:02d}"
                }[func]
            except Exception:
                return ""

        # ── math helpers (treat empty/non‑numeric as 0) ──────────────
        def num(a): 
            try:  return float(resolve(a))
            except ValueError: return 0.0

        if func == "add" and len(args)==2: return str(num(args[0]) + num(args[1]))
        if func == "sub" and len(args)==2: return str(num(args[0]) - num(args[1]))
        if func == "mul" and len(args)==2: return str(num(args[0]) * num(args[1]))
        if func == "div" and len(args)==2:
            denom = num(args[1])
            return "∞" if denom == 0 else str(num(args[0]) / denom)

        # ── comparisons / logic (truthy = non‑empty & not "0") ──────
        def truth(a): return bool(resolve(a)) and resolve(a) != "0"

        if func == "eq"  and len(args)==2: return str(resolve(args[0]) == resolve(args[1]))
        if func == "lt"  and len(args)==2: return str(num(args[0]) <  num(args[1]))
        if func == "gt"  and len(args)==2: return str(num(args[0]) >  num(args[1]))

        if func == "and": return str(all(truth(a) for a in args))
        if func == "or":  return str(any(truth(a) for a in args))
        if func == "not" and len(args)==1: return str(not truth(args[0]))

        # ── conditional helpers ─────────────────────────────────────
        if func == "if" and len(args)==3:
            return resolve(args[1]) if truth(args[0]) else resolve(args[2])

        if func == "if2" and len(args) >= 2:
            *candidates, fallback = args
            for cand in candidates:
                val = resolve(cand)
                if val: return val
            return resolve(fallback)

        # unknown function → leave as‑is
        return match.group(0)

    def _split_args(self, s: str) -> list[str]:
        parts = []
        current = []
        in_quotes = False
        quote_char = None
        for c in s:
            if c in ('"', "'"):
                if in_quotes:
                    if c == quote_char:
                        in_quotes = False
                        quote_char = None
                    else:
                        current.append(c)
                else:
                    in_quotes = True
                    quote_char = c
            elif c == ',' and not in_quotes:
                part = "".join(current).strip()
                if part.startswith(("'", '"')) and part.endswith(("'", '"')):
                    part = part[1:-1]
                parts.append(part)
                current = []
            else:
                current.append(c)
        if current:
            part = "".join(current).strip()
            if part.startswith(("'", '"')) and part.endswith(("'", '"')):
                part = part[1:-1]
            parts.append(part)
        return parts

    def eval(self, text: str) -> str:
        res = text

        # Handle %formatN#% tokens and %format%
        fmts = [f.strip() for f in self.meta.get("format", "").split(",") if f.strip()]
        adds = [a.strip() for a in self.meta.get("additional", "").split(",") if a.strip()]

        res = re.sub(
            r"%formatN(\d+)%",
            lambda m: self._list_token("formatN", fmts, int(m.group(1)) - 1),
            res,
        )
        res = res.replace("%formatN%", ", ".join(fmts))
        res = res.replace("%format%", fmts[0] if fmts else "")

        res = re.sub(
            r"%additionalN(\d+)%",
            lambda m: self._list_token("additionalN", adds, int(m.group(1)) - 1),
            res,
        )
        res = res.replace("%additionalN%", ", ".join(adds))
        res = res.replace("%additional%", adds[0] if adds else "")

        # Replace simple %token% except format/additional handled above
        for k, v in self.meta.items():
            if k in ("format", "additional"):
                continue
            res = res.replace(f"%{k}%", v)

        # Recursively evaluate $func(...) tokens until no changes
        prev = None
        while prev != res:
            prev = res
            res = self.FUNC_RE.sub(self._eval_func, res)

        return res

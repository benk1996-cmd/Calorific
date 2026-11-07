"""pg_trgm-style trigram similarity (used by the eval script and tests; Postgres does this in production)."""
import re


def trigrams(s: str) -> set[str]:
    out: set[str] = set()
    for w in re.findall(r"[a-z0-9]+", s.lower()):
        p = f"  {w} "
        out |= {p[i : i + 3] for i in range(len(p) - 2)}
    return out


def similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0

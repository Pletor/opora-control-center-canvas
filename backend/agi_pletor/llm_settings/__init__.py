"""Nastavení LLM na tomto počítači jen ke čtení (docs/navrhy/2026-11-04-pletor-nastaveni-llm.md, M1).

`read_all()` → `{claude, codex, ollama, cswap, codexswap}` (účty Claude Code a Codexu); sekce běží souběžně a selže izolovaně (`{available: false, reason}`).
"""
from concurrent.futures import ThreadPoolExecutor

from backend.agi_pletor.llm_settings import claude, codex, codex_accounts, cswap, ollama

SECTIONS = {"claude": claude.read, "codex": codex.read, "ollama": ollama.read, "cswap": cswap.read,
            "codexswap": codex_accounts.read}


def _safe(read):
    try:
        return read()
    except Exception as error:  # noqa: BLE001 – jedna rozbitá sekce nesmí shodit ostatní ani route
        return {"available": False, "reason": f"{type(error).__name__}: {error}"[:200]}


def read_all():
    with ThreadPoolExecutor(len(SECTIONS)) as pool:
        return dict(zip(SECTIONS, pool.map(_safe, SECTIONS.values())))

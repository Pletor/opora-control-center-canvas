"""Registr strážců (`docs/strazci.md` §2): každý strážce je `{id, label, every_s, run(ctx)}`.

`run(ctx)` vrací **úplný** seznam aktuálních nálezů strážce (prázdný = vše v pořádku), nebo `None`, když se
vstup od posledního běhu nezměnil a strážce přeskočil. `ctx` je `GuardContext`: služba plátna, projekt, čas
běhu (epoch sekundy, testy podstrčí falešný) a `memo`, slovník strážce pro jeden projekt, který jádro uloží
jen po úspěšném běhu (např. hlava architektury, nad kterou strážce naposledy počítal).
"""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Guard:
    id: str
    label: str
    every_s: float
    run: Callable[["GuardContext"], list | None]


@dataclass
class GuardContext:
    service: Any
    project: str
    now: float
    memo: dict = field(default_factory=dict)


def default_guards():
    """První sada strážců: mapa a práce (G1), cesty a pravda (G2)."""
    from backend.canvas.strazci import guard_cesty, guard_mapa, guard_prace, guard_pravda
    return (guard_mapa.GUARD, guard_prace.GUARD, guard_cesty.GUARD, guard_pravda.GUARD)


def validate_registry(guards):
    """Jednoznačná id a kladný interval; jinak `ValueError` (chyba v kódu, ne v datech)."""
    seen = set()
    for guard in guards:
        if not isinstance(guard.id, str) or not guard.id or guard.id in seen:
            raise ValueError(f"Strážce potřebuje jednoznačné id: {guard.id!r}.")
        if not guard.every_s > 0:
            raise ValueError(f"Strážce {guard.id} potřebuje kladný interval.")
        seen.add(guard.id)
    return tuple(guards)

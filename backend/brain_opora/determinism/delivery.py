"""Kanál doručení práce projektu (docs/brain-heart.md §3e): komu srdce zadává práci, bez modelu.

`cards` = projekt má orchestrátor karet: aspoň jedna exekuce (claim karty přes `/api/oporahub/executions`) v kterémkoli
prostoru projektu, kdykoli. `gate` = žádná exekuce nikdy; práci berou jen pracovníci přes bránu (`opora_gate.py next`),
takže ji srdce zadává úkoly fronty (`task`). Bez časového okna: snímek nezávisí na čase a orchestrátor, který pár dní
nic nebral, pořád existuje. Relace pracovníků brány jsou jen podpora textu řádku, kanál nemění.
"""
import sqlite3

CARDS, GATE = "cards", "gate"


def channel(db, project):
    """`{"channel": cards|gate, "executions": n, "workers": n}` projektu; nečitelná tabulka = 0 (tedy `gate`)."""
    executions = _count(db, "SELECT COUNT(*) FROM opora_executions WHERE project_id=?", project)
    workers = _count(db, "SELECT COUNT(*) FROM gate_sessions WHERE project_id=? AND role='worker'", project)
    return {"channel": CARDS if executions else GATE, "executions": executions, "workers": workers}


def line(delivery):
    """Jeden řádek snímku `DORUČENÍ: …` s pravidlem, kterým příkazem srdce zadává práci."""
    if delivery["channel"] == CARDS:
        return (f"DORUČENÍ: cards – orchestrátor bere karty (exekucí {delivery['executions']});"
                " práci zadávej kartami (plan)")
    workers = f" (relací pracovníků brány {delivery['workers']})" if delivery["workers"] else ""
    return f"DORUČENÍ: gate – žádný orchestrátor karet{workers}; práci zadávej jako úkoly fronty (task)"


def _count(db, sql, project):
    try:
        return db.execute(sql, (project,)).fetchone()[0]
    except sqlite3.Error:
        return 0

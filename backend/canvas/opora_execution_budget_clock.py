"""Persisted fail-closed server clock; a regression cannot resurrect budget authority."""

from backend.canvas.opora_execution_budget_validation import finite


class BudgetClockConflict(ValueError):
    def __init__(self, high_water):
        super().__init__("Budget server clock regressed; authority is frozen.")
        self.high_water = high_water


def observe(db, now, project):
    finite(now)
    row = db.execute(
        "SELECT high_water,frozen,project_id FROM opora_execution_budget_clock WHERE id=1"
    ).fetchone()
    if row:
        finite(row[0])
        if row[1] not in (0, 1) or row[2] != project:
            raise ValueError("Malformed persisted budget clock.")
        if row[1] or now < row[0]:
            raise BudgetClockConflict(row[0])
        db.execute("UPDATE opora_execution_budget_clock SET high_water=? WHERE id=1", (now,))
    else:
        if db.execute(
            "SELECT 1 FROM opora_execution_budget_ledger WHERE kind='allocation' LIMIT 1"
        ).fetchone():
            raise BudgetClockConflict(now)
        db.execute("INSERT INTO opora_execution_budget_clock VALUES(1,?,0,?)", (now, project))
    return now


def freeze(db, high_water, project):
    db.execute(
        "INSERT INTO opora_execution_budget_clock VALUES(1,?,1,?) ON CONFLICT(id) DO UPDATE SET high_water=MAX(high_water,excluded.high_water),frozen=1",
        (high_water, project),
    )


def rollback_preserving_clock(db, project, conflict=None):
    row = db.execute(
        "SELECT high_water,frozen,project_id FROM opora_execution_budget_clock WHERE id=1"
    ).fetchone()
    db.rollback()
    if row:
        finite(row[0])
        if row[2] != project or row[1] not in (0, 1):
            raise ValueError("Malformed budget clock during rollback.")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO opora_execution_budget_clock VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET high_water=MAX(high_water,excluded.high_water),frozen=MAX(frozen,excluded.frozen)",
            (
                max(row[0], conflict.high_water if conflict else 0),
                int(bool(conflict) or bool(row[1])),
                project,
            ),
        )
        db.commit()
    elif conflict:
        db.execute("BEGIN IMMEDIATE")
        freeze(db, conflict.high_water, project)
        db.commit()

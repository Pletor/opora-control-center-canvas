"""Přístup k tabulce `guard_trend` (vzorky souhrnných čísel, `docs/strazci.md` §4); transakci vlastní volající."""


class GuardTrend:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def insert(self, at, values):
        """Jeden vzorek: `{metric: value}` se stejným `at`; opakovaný vzorek ve stejný okamžik se přepíše."""
        self.db.executemany("INSERT OR REPLACE INTO guard_trend(project_id,at,metric,value) VALUES(?,?,?,?)",
                            [(self.project, at, metric, float(value)) for metric, value in sorted(values.items())])

    def prune(self, cutoff_at):
        """Retence: smaže vzorky starší než `cutoff_at` (ISO v UTC)."""
        self.db.execute("DELETE FROM guard_trend WHERE project_id=? AND at<?", (self.project, cutoff_at))

    def series(self, since_at, metric=None):
        """{metric: [{at, value}]} od `since_at` vzestupně podle času; `metric` zúží na jedno číslo."""
        condition, parameters = "project_id=? AND at>=?", [self.project, since_at]
        if metric is not None:
            condition, parameters = condition + " AND metric=?", [*parameters, metric]
        result = {}
        for name, at, value in self.db.execute(f"SELECT metric,at,value FROM guard_trend WHERE {condition}"
                                               " ORDER BY metric, at", parameters):
            result.setdefault(name, []).append({"at": at, "value": int(value) if float(value).is_integer() else value})
        return result

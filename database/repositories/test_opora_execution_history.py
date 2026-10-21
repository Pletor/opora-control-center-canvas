"""Optional card filters retain bounded scope isolation and insertion ordering."""
import sqlite3

from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA


def test_recent_scope_history_is_bounded_and_filtered_history_unchanged():
    with sqlite3.connect(":memory:") as db:
        db.executescript(SCHEMA)
        repository = Executions(db, "p", "w")
        for number in range(105):
            repository.insert({"executionId": str(number), "nodeId": "a" if number % 2 else "b"},
                              "worker", str(number), "digest")
        for scope in (("p", "other"), ("other", "w")):
            Executions(db, *scope).insert({"executionId": str(scope), "nodeId": "a"}, "worker", "foreign", "digest")
        assert [row["executionId"] for row in repository.history()] == [str(n) for n in range(104, 4, -1)]
        assert [row["executionId"] for row in repository.history("a")] == [str(n) for n in range(103, 0, -2)]
        assert repository.history("missing") == []

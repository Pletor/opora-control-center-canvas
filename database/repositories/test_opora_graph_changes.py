"""Paměť re-derivace záznamů změn grafu adresovaných obsahem."""

def test_graph_change_rederivation_once_per_content_id(monkeypatch):
    # Id záznamu = hash obsahu: re-derivace se pro stejné id neopakuje, integrita se ověřuje vždy.
    import json
    from database.repositories import opora_graph_changes as module
    record = {"kind": "graph-changes", "project": "p", "workspace": "w", "x": 1}
    record["id"] = module.content_id({k: v for k, v in record.items()})
    calls = []
    monkeypatch.setattr(module, "VALIDATED", set())
    monkeypatch.setattr(module, "validate_record", calls.append)

    class Db:
        def __init__(self, content):
            self.content = content
        def execute(self, *_):
            return self
        def fetchone(self):
            return (self.content,)

    repo = module.GraphChanges.__new__(module.GraphChanges)
    repo.scope, repo.db = ("p", "w"), Db(json.dumps(record))
    assert repo.read(record["id"]) == record and repo.read(record["id"]) == record
    assert len(calls) == 1
    repo.db = Db(json.dumps({**record, "x": 2}))
    try:
        repo.read(record["id"])
        raise AssertionError("změněný obsah musí selhat")
    except ValueError:
        pass

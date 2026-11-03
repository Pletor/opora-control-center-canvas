import sqlite3

import pytest

from database.schema.project_schema import REGISTRY_SCHEMA, ensure_flow_owner_ref


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(connection)
    yield connection
    connection.close()


def node(nid, type_, **extra):
    return {"id": nid, "type": type_, "type_version": 1, "params": {}, "position": {"x": 0, "y": 0}, **extra}


def edge(eid, source, target, source_port="main", target_port="main", kind="main"):
    return {"id": eid, "source_node": source, "source_port": source_port, "target_node": target,
            "target_port": target_port, "kind": kind, "label": ""}

"""Opt-in ownership for atomic native library compositions; standalone commits stay unchanged."""
from contextlib import contextmanager
from contextvars import ContextVar

_owned = ContextVar("flow_owned_connections", default=frozenset())


@contextmanager
def transaction(db):
    if id(db) in _owned.get():
        yield db
    else:
        with db:
            yield db


@contextmanager
def atomic(db):
    if id(db) in _owned.get() or db.in_transaction:
        raise RuntimeError("Library transaction requires explicit outer ownership.")
    token = _owned.set(_owned.get() | {id(db)})
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            yield db
    finally:
        _owned.reset(token)

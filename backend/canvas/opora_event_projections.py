"""Transactional derived read models. Register features here, never fork the source event bus."""
from backend.library.harness_learning import project_event as harness_learning

PROJECTIONS = (harness_learning,)


def project(db, event_id, event):
    for callback in PROJECTIONS:
        callback(db, event_id, event)

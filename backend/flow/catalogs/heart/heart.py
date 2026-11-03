"""Srdce pro engine toků: stav (`state.py`), buzení (`wakes.py`) a hlídač gitu (`git_watch.py`) v jednom objektu.

Uzly katalogu (`nodes.py`) a `HeartDriver` s ním pracují přes `runtime.heart`; routy `/api/brain/heart/*` volají
`message` a `status`. Vlastní vlákno nemá, průchody řídí plánovač enginu (`backend/flow/scheduler.py`).
"""
from backend.flow.catalogs.heart.git_watch import GitWatch
from backend.flow.catalogs.heart.state import HeartState
from backend.flow.catalogs.heart.wakes import Wakes


class Heart(Wakes, GitWatch, HeartState):
    pass

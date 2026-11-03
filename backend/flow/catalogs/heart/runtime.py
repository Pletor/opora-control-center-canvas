"""Běhové vazby katalogu srdce: s čím uzly pracují (služba, `Heart`) a jak běží mimo zámek registru.

Typy uzlů jsou v registru napořád (graf jde validovat i bez srdce). Vykonat je jde jen po `bind`, který udělá
`HeartDriver.start` (srdce povolené, `state.enabled()`); bez vazby uzel selže a běh skončí `failed`.

`detached(work)` udělá z pomalé práce (síť, zámky projektu, `claude -p`) uzel, který vrátí `{"detach": True}`,
práci pustí ve vlastním vlákně, každých `heartbeat_seconds` pošle heartbeat a skončí `interpreter.finish` / `fail`.
Zámek registru drží jen na zápis do logu, nikdy během práce.
"""

import logging
import threading
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 60.0  # pod `stalls.HEARTBEAT_LIMIT` (5 min) s rezervou


def _thread(target):
    threading.Thread(target=target, name="opora-flow-node", daemon=True).start()


@dataclass
class Runtime:
    service: object  # `db` a `registry_lock` registru + vše, co čte srdce (`project_ids`, `db_for`, …)
    heart: object  # `Heart` (`heart.py`): vstupy, stav (`running`, `current`, `starts`, …) a exekutor dávky
    spawn: object = _thread
    heartbeat_seconds: float | None = HEARTBEAT_SECONDS  # None = bez heartbeatu (zkoušky se synchronním `spawn`)


_bound = {"runtime": None}


def bind(runtime):
    _bound["runtime"] = runtime


def current():
    runtime = _bound["runtime"]
    if runtime is None:
        raise RuntimeError("Srdce v enginu toků neběží (OPORA_HEART=off nebo mimo loopback).")
    return runtime


def detached(work):
    """`work(ctx, runtime) -> (port, output, extra)` jako funkce uzlu, který běží mimo zámek a hlásí se."""

    def run(ctx):
        from backend.flow import interpreter

        runtime = current()
        service, node_run_id, stop = runtime.service, ctx["node_run_id"], threading.Event()

        def beat():
            while not stop.wait(runtime.heartbeat_seconds):
                with service.registry_lock:
                    if not interpreter.heartbeat(service.db, node_run_id):
                        return

        def job():
            if runtime.heartbeat_seconds:
                runtime.spawn(beat)
            try:
                port, output, extra = work(ctx, runtime)
            except Exception as error:  # chyba práce = neúspěšný uzel, ne pád vlákna
                LOGGER.exception("Tok srdce: uzel %s selhal.", ctx["node"]["id"])
                stop.set()
                with service.registry_lock:
                    interpreter.fail(service.db, node_run_id, f"{type(error).__name__}: {error}"[:500])
                return
            stop.set()
            with service.registry_lock:
                interpreter.finish(service.db, node_run_id, port, output, extra)

        runtime.spawn(job)
        return {"detach": True}

    return run

"""Logování procesu do deníku chyb: zdroj z loggeru, výjimka s tracebackem, bez rekurze a bez čekání."""
import logging
import sqlite3
import time

from backend.app import error_log, errors
from backend.app.test_errors import (  # noqa: F401 - fixture registru s tabulkou deníku
    registry,
    rows,
)


def test_logger_exception_lands_in_journal(registry):  # noqa: F811
    error_log.install()
    error_log.install()  # podruhé nic nepřidá
    assert sum(isinstance(h, error_log.ErrorLogHandler) for h in logging.getLogger().handlers) == 1
    try:
        raise RuntimeError("plánovač spadl")
    except RuntimeError:
        logging.getLogger("backend.flow.scheduler").exception("Tik plánovače selhal")
    logging.getLogger("backend.brain_opora.heart.x").warning("srdce varuje")
    error_log.drain()
    flow, heart = rows(registry)
    assert (flow["source"], flow["kind"], flow["severity"]) == ("flow", "exception", "error")
    assert "RuntimeError: plánovač spadl" in flow["cause"] and '"logger": "backend.flow.scheduler"' in flow["data"]
    assert (heart["source"], heart["kind"], heart["severity"]) == ("heart", "log", "warn")
    assert error_log.source_of("backend.flow.catalogs.heart.driver") == "heart"
    assert error_log.source_of("uvicorn.error") == "server"


def test_failure_inside_record_does_not_recurse(registry, monkeypatch):  # noqa: F811
    def broken(*args, **kwargs):
        logging.getLogger("backend.canvas").error("chyba uvnitř deníku")
        raise RuntimeError("nikdy")
    monkeypatch.setattr(errors, "_connect", broken)
    handler = error_log.ErrorLogHandler()
    handler.emit(logging.LogRecord("backend.canvas", logging.ERROR, __file__, 1, "x", None, None))
    error_log.drain()  # vlákno přežilo: record chybu spolkl
    assert error_log._worker.is_alive()


def test_emit_does_not_wait_for_locked_registry(registry):  # noqa: F811
    holder = sqlite3.connect(registry, timeout=0)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        started = time.perf_counter()
        error_log.ErrorLogHandler().emit(logging.LogRecord("backend", logging.WARNING, __file__, 1, "x", None, None))
        assert time.perf_counter() - started < 0.1
    finally:
        holder.rollback()
        holder.close()
    error_log.drain()

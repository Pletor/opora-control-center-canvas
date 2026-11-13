"""Cesta do deníku chyb bez čekání: logování procesu a obsluha chyb serveru (docs/navrhy/2026-11-13-denik-chyb.md §3).

`submit` jen vloží záznam do omezené fronty a vrátí se; jedno vlákno na pozadí volá `errors.record`. Proto
WARNING zalogované uvnitř otevřené zápisové transakce registru nečeká 2 s na vlastní zámek a async obsluha 503
nezdrží smyčku událostí. Plná fronta záznam zahodí (deník nesmí zpomalit, co hlídá).
"""
import logging
import queue
import sys
import threading
import traceback

from backend.app import errors

QUEUE = queue.Queue(maxsize=1000)
SOURCES = (("backend.brain_opora", "heart"), ("backend.flow.catalogs.heart", "heart"), ("backend.flow", "flow"),
           ("backend.agi_pletor", "pletor"), ("backend.canvas", "card"))
_worker = None
_worker_lock = threading.Lock()
_inside = threading.local()


def _drain_forever():
    _inside.active = True  # cokoli zalogované z vlákna deníku se do deníku nevrací (jinak smyčka přes frontu)
    while True:
        args, kwargs = QUEUE.get()
        try:
            errors.record(*args, **kwargs)
        finally:
            QUEUE.task_done()


def submit(*args, **kwargs):
    """Stejné argumenty jako `errors.record`; nikdy nečeká ani nevyhodí."""
    global _worker
    try:
        if _worker is None:
            with _worker_lock:
                if _worker is None:
                    _worker = threading.Thread(target=_drain_forever, name="opora-errors", daemon=True)
                    _worker.start()
        QUEUE.put_nowait((args, kwargs))
    except Exception:  # noqa: BLE001, S110 – plná fronta nebo vlákno nejde spustit: záznam se ztratí, práce ne
        pass


def drain():
    """Počká, až vlákno zapíše vše z fronty (testy a ukončení)."""
    QUEUE.join()


def source_of(name):
    return next((source for prefix, source in SOURCES if name == prefix or name.startswith(prefix + ".")), "server")


class ErrorLogHandler(logging.Handler):
    """WARNING+ z kteréhokoli loggeru → deník; výjimka v záznamu = `exception`, jinak `log`."""

    def emit(self, record):
        if getattr(_inside, "active", False):
            return  # chyba při zápisu deníku nesmí znovu do deníku
        _inside.active = True
        try:
            exc = record.exc_info[1] if record.exc_info else None
            if getattr(exc, "_opora_recorded", False):
                return  # 500 už zapsala obsluha serveru s cestou a metodou
            submit(source_of(record.name), "exception" if exc else "log", record.getMessage(),
                   severity="error" if record.levelno >= logging.ERROR else "warn",
                   cause="".join(traceback.format_exception(*record.exc_info)) if exc else None,
                   data={"logger": record.name, "where": f"{record.pathname}:{record.lineno}"})
        except Exception:  # noqa: BLE001, S110
            pass
        finally:
            _inside.active = False


def install():
    """Jednou na proces: handler na kořenový logger; bez dalších handlerů i stderr, ať se WARNING+ neztratí."""
    root = logging.getLogger()
    if any(isinstance(handler, ErrorLogHandler) for handler in root.handlers):
        return
    if not root.handlers:  # vlastní handler by vypnul logging.lastResort (stderr)
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(logging.WARNING)
        root.addHandler(stderr)
    root.addHandler(ErrorLogHandler(logging.WARNING))

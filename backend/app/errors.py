"""Deník chyb OPORY: jeden záznam na otisk chyby, opakování zvedá `count` (docs/navrhy/2026-11-13-denik-chyb.md §2–§5).

`record` nikdy nevyhodí výjimku a píše vlastním krátkým spojením do registry.sqlite, mimo `registry_lock`
i zámek projektu: deník nesmí čekat na zámek, který hlídá. Bez `configure` je no-op. Zápis z logování
a z obsluhy chyb serveru jde přes frontu v `error_log.py`, aby volajícího nezdržel.
"""
import hashlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

MESSAGE, CAUSE, DATA = 300, 2000, 4000
RETENTION_DAYS, MAX_ROWS, PRUNE_EVERY = 30, 100_000, 1000
SEVERITY = {"critical": 0, "error": 1, "warn": 2}
# UUID, hex id ≥ 8 znaků a čísla → `#`, ať stejná chyba s jiným ID má stejný otisk.
VOLATILE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\b[0-9a-f]{8,}\b|\d+", re.IGNORECASE)
COLUMNS = ("id", "fingerprint", "first_at", "last_at", "count", "resolved_at", "severity", "kind", "source", "project",
           "workspace", "subject", "actor_kind", "actor_name", "session", "message", "cause", "lever", "data")

_path = None
_writes = 0


def configure(data_root):
    global _path
    _path = None if data_root is None else Path(data_root) / "registry.sqlite"


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def fingerprint(source, kind, message, project=None, subject=None):
    text = VOLATILE.sub("#", " ".join(str(message).split()))
    return hashlib.sha256("|".join(str(x or "") for x in (source, kind, project, subject, text)).encode()).hexdigest()


def _connect():
    # Jen existující soubor: connect by jinak založil prázdnou databázi bez tabulky.
    if _path is None or not _path.exists():
        return None
    db = sqlite3.connect(_path, timeout=2)
    db.row_factory = sqlite3.Row
    return db


def _redact(text):
    # Líně: deník budou importovat i moduly, které srdce samo importuje (cyklus importů).
    from backend.brain_opora.heart.steps import redact

    return redact(text)


def _data(data):
    if data is None:
        return None
    text = json.dumps(data, ensure_ascii=False, default=str)
    # Useknutý JSON by nešel přečíst; místo něj platný obal se začátkem textu.
    return text if len(text) <= DATA else json.dumps({"truncated": text[:DATA - 100]}, ensure_ascii=False)


def record(source, kind, message, *, severity="error", project=None, workspace=None, subject=None, actor=None,
           session=None, cause=None, lever=None, data=None):
    """Zapíše chybu nebo zvedne počet u stejného otisku (a znovu ji otevře). Nikdy nevyhodí výjimku."""
    global _writes
    try:
        db = _connect()
        if db is None:
            return
        message = _redact(message)[:MESSAGE]
        cause = None if cause is None else _redact(cause)[-CAUSE:]  # konec tracebacku nese příčinu
        actor_kind, actor_name = (actor if isinstance(actor, (tuple, list)) else (actor, None)) if actor else (None, None)
        stamp = now()
        row = (fingerprint(source, kind, message, project, subject), stamp, stamp, severity, kind, source, project,
               workspace, subject, actor_kind, actor_name, session, message, cause, lever, _data(data))
        try:
            with db:
                db.execute(
                    "INSERT INTO opora_errors(fingerprint, first_at, last_at, count, severity, kind, source, project,"
                    " workspace, subject, actor_kind, actor_name, session, message, cause, lever, data)"
                    " VALUES(?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET"
                    " count=count+1, last_at=excluded.last_at, resolved_at=NULL, severity=excluded.severity,"
                    " message=excluded.message, cause=excluded.cause, data=excluded.data,"
                    " lever=COALESCE(excluded.lever, lever)", row)
            _writes += 1
            if _writes % PRUNE_EVERY == 0:
                prune(db=db)
        finally:
            db.close()
    except Exception as error:  # noqa: BLE001 – deník nesmí shodit to, co hlídá; stderr, ne logging (rekurze)
        print(f"opora errors: zápis selhal: {type(error).__name__}: {error}", file=sys.stderr)


def resolve(fingerprint=None, *, source=None, subject=None, kind=None, project=None):
    """Uzavře otevřené záznamy (detektor: podmínka zmizela). Vrátí počet uzavřených, při chybě 0."""
    where = [(col, value) for col, value in (("fingerprint", fingerprint), ("source", source), ("subject", subject),
                                               ("kind", kind), ("project", project)) if value is not None]
    if not where:
        return 0
    try:
        db = _connect()
        if db is None:
            return 0
        try:
            with db:
                return db.execute("UPDATE opora_errors SET resolved_at=? WHERE resolved_at IS NULL AND "
                                  + " AND ".join(f"{col}=?" for col, _ in where),
                                  (now(), *(value for _, value in where))).rowcount
        finally:
            db.close()
    except Exception as error:  # noqa: BLE001
        print(f"opora errors: uzavření selhalo: {error}", file=sys.stderr)
        return 0


def _filters(project, open_only, since, kind, source):
    where, args = [], []
    for col, value in (("project", project), ("kind", kind), ("source", source)):
        if value:
            where.append(f"{col}=?")
            args.append(value)
    if open_only:
        where.append("resolved_at IS NULL")
    if since:
        where.append("last_at>=?")
        args.append(since)
    return (" WHERE " + " AND ".join(where) if where else ""), args


def read(*, project=None, open_only=True, since=None, kind=None, source=None, limit=200):
    """Záznamy: otevřené první, pak podle závažnosti, počtu a posledního výskytu."""
    db = _connect()
    if db is None:
        return []
    try:
        where, args = _filters(project, open_only, since, kind, source)
        rows = db.execute(
            f"SELECT * FROM opora_errors{where} ORDER BY resolved_at IS NOT NULL, CASE severity WHEN 'critical' THEN 0"
            f" WHEN 'error' THEN 1 ELSE 2 END, count DESC, last_at DESC LIMIT ?", (*args, max(1, min(limit, 1000))))
        out = [dict(row) for row in rows]
    finally:
        db.close()
    for row in out:
        try:
            row["data"] = json.loads(row["data"]) if row["data"] else None
        except ValueError:
            pass  # starý nebo cizí text zůstane, jak je
    return out


def counts(project=None):
    """Počet otevřených chyb (celkem a srdce), bez stropu výpisu."""
    db = _connect()
    if db is None:
        return {"open": 0, "heart": 0}
    try:
        where, args = _filters(project, True, None, None, None)
        total, heart = db.execute(f"SELECT COUNT(*), COALESCE(SUM(source='heart'), 0) FROM opora_errors{where}",
                                  args).fetchone()
        return {"open": total, "heart": heart}
    finally:
        db.close()


def text(rows):
    """Řádky pro agenta: co · kde · kolikrát · od kdy · páka."""
    if not rows:
        return "DENÍK CHYB: nic"
    lines = []
    for r in rows:
        where = " · ".join(str(x) for x in (r["project"], r["subject"]) if x)
        state = "" if r["resolved_at"] is None else f" (vyřešeno {r['resolved_at']})"
        lines.append(f"[{r['severity']}] {r['source']}/{r['kind']}{' · ' + where if where else ''} · {r['count']}× od "
                     f"{r['first_at']}, naposledy {r['last_at']}: {r['message']}"
                     f"{' → ' + r['lever'] if r['lever'] else ''}{state}")
    return "\n".join(lines)


def prune(now_at=None, *, db=None):
    """Vyřešené starší 30 dní pryč; nad strop 100 000 řádků mizí nejstarší vyřešené. Otevřené zůstávají vždy."""
    own = db is None
    db = _connect() if own else db
    if db is None:
        return
    try:
        cutoff = ((now_at or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
        with db:
            db.execute("DELETE FROM opora_errors WHERE resolved_at IS NOT NULL AND resolved_at<?", (cutoff,))
            extra = db.execute("SELECT COUNT(*) FROM opora_errors").fetchone()[0] - MAX_ROWS
            if extra > 0:
                db.execute("DELETE FROM opora_errors WHERE id IN (SELECT id FROM opora_errors WHERE resolved_at IS NOT"
                           " NULL ORDER BY resolved_at LIMIT ?)", (extra,))
    finally:
        if own:
            db.close()


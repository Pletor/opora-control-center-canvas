"""Tokeny rolí brány (docs/brain-gate.md §2): vydání, ověření a zneplatnění.

Token je 32 náhodných bajtů (url-safe) a ukáže se jen jednou, v odpovědi, která ho vydala. Ukládá se jen
`sha256(token)` v `gate_sessions` databáze projektu. Token pracovníka platí 8 h; token srdce vydává jen kód
v procesu (`issue_heart`), nikdy žádná routa, a platí, dokud ho nikdo nezneplatní.

Token sám projekt nenese. Kde leží, si proces pamatuje (`_WHERE`, otisk → projekt); po restartu ho
jednou dohledá průchodem projekty registru.
"""
import hashlib
import secrets
import threading
import uuid
from datetime import UTC, datetime, timedelta

from database.repositories.gate_sessions import GateSessionStore

HEADER = "X-Opora-Gate-Token"
WORKER_TTL = timedelta(hours=8)
ROLES = ("heart", "worker")

_WHERE: dict[str, str] = {}
_WHERE_LOCK = threading.Lock()


def stamp(moment=None):
    """Čas UTC v pevném tvaru, aby se dal porovnávat jako text."""
    return (moment or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _remember(token_hash, project):
    with _WHERE_LOCK:
        _WHERE[token_hash] = project


def _issue(service, project, workspace, role, name, meta, ttl, now=None):
    if role not in ROLES:
        raise ValueError("Neznámá role brány.")
    moment = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    session = {"id": "gs_" + uuid.uuid4().hex, "project_id": project, "workspace_id": workspace, "role": role,
               "worker_name": name, "worker_meta": meta, "token_hash": hash_token(token),
               "created_at": stamp(moment), "expires_at": stamp(moment + ttl) if ttl else None}
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            GateSessionStore(db).insert(session)
    _remember(session["token_hash"], project)
    return session, token


def issue_worker(service, project, workspace, worker, now=None):
    """Relace pracovníka: `{sessionId, token, expiresAt}`; token se už nikdy znovu neukáže."""
    meta = {key: worker[key] for key in ("office", "floor") if key in worker}
    session, token = _issue(service, project, workspace, "worker", worker["name"], meta, WORKER_TTL, now)
    return {"sessionId": session["id"], "token": token, "expiresAt": session["expires_at"]}


def issue_heart(service, project, workspace, now=None):
    """Token srdce jen pro kód v procesu (H2); vrací `(sessionId, token)`."""
    session, token = _issue(service, project, workspace, "heart", "heart", {}, None, now)
    return session["id"], token


def _lookup(service, project, token_hash):
    with service.reading(project):
        return GateSessionStore(service.db_for(project)).by_hash(token_hash)


def _find(service, token_hash):
    with _WHERE_LOCK:
        known = _WHERE.get(token_hash)
    if known is not None:
        try:
            return _lookup(service, known, token_hash)
        except ValueError:  # projekt mezitím zmizel
            return None
    for project in service.project_ids():
        try:
            session = _lookup(service, project, token_hash)
        except ValueError:
            continue
        if session is not None:
            _remember(token_hash, project)
            return session
    return None


def verify(service, token, now=None):
    """Platná relace tokenu, nebo None (neznámý, prošlý nebo zneplatněný token)."""
    if not isinstance(token, str) or not 20 <= len(token) <= 200:
        return None
    session = _find(service, hash_token(token))
    if session is None or session["revoked_at"] is not None:
        return None
    if session["expires_at"] is not None and session["expires_at"] <= stamp(now):
        return None
    return session


def revoke(service, project, session_id, now=None):
    """Zneplatní relaci; True, když ji zneplatnilo právě toto volání."""
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            return GateSessionStore(db).revoke(session_id, stamp(now))

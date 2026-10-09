"""Klient serveru OpenViking na loopbacku: jediné místo, kde Opora mluví HTTP s pamětí.

OpenViking je samostatný server (docker compose v jeho repozitáři). Opora ho jen čte a
zapisuje do něj; **žádný model tudy nespouští**. Extrakci paměti dělá OpenViking sám uvnitř
(commit session → jeho vlastní LLM), Opora o tom jen dostane `task_id`.

Disciplína spojení: pouze `http://` na loopback, bez proxy, bez přesměrování, s timeoutem a stropem velikosti
odpovědi. Klíč žije jen v hlavičce požadavku, nikdy v URL ani v odpovědi.

Mapování Opory na identity OpenVikingu (`docs/pamet-agentu.md`):
`user` = id role agenta (`role-frontend`…), `peer` = id projektu Opory, sekce karty jsou
resources pod `viking://user/{role}/peers/{project}/resources/cards/{nodeId}/`.

**Identitu určuje klíč, ne hlavička.** Server běží v režimu `auth_mode: api_key` a v něm si
uživatele odvozuje z předloženého `X-API-Key`; hlavičky `X-OpenViking-Account` /
`-User` / `-Actor-Peer` buď ignoruje, nebo je odmítne (ověřeno živě: `X-OpenViking-Account`
s uživatelským klíčem vrátil 403). Proto je klient **neposílá**, dokud mu někdo výslovně
nenastaví `trusted_identity=True` pro nasazení v režimu `trusted`. Role = jeden uživatel
OpenVikingu = jeden klíč; klíče rozdává `admin_*` metodami správcovský klíč.

Každá porucha přenosu, HTTP stavu i obálky končí `OpenVikingUnavailable` (podtřída OSError),
takže volající nikdy nedostane vymyšlený výsledek. `factory.py` mapuje OSError na HTTP 503.
"""

import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit

DEFAULT_OPENVIKING_URL = "http://127.0.0.1:1933"
DEFAULT_ACCOUNT = "default"
MAX_RESPONSE_BYTES = 512 * 1024
# Zdraví a správa rolí odpovídají hned; strop 5 s stačí a rychle pozná nedostupný server.
TIMEOUT_SECONDS = 5.0
# První vybavení nového dotazu musí počkat na zavektorování v Ollamě (~20 s živě naměřeno),
# proto mají data (search/write/session/task) vlastní, delší strop (docs/pamet-agentu.md).
DATA_TIMEOUT_SECONDS = 30.0
MAX_CONTENT_CHARS = 12000

URL_ENV = "OPORA_OPENVIKING_URL"
ACCOUNT_ENV = "OPORA_OPENVIKING_ACCOUNT"
ADMIN_KEY_ENV = "OPORA_OPENVIKING_ADMIN_API_KEY"
LEGACY_KEY_ENV = "OPORA_OPENVIKING_API_KEY"
TRUSTED_ENV = "OPORA_OPENVIKING_TRUSTED_IDENTITY"
TIMEOUT_ENV = "OPORA_OPENVIKING_TIMEOUT"
DATA_TIMEOUT_ENV = "OPORA_OPENVIKING_DATA_TIMEOUT"
TRUTHY = {"1", "true", "yes", "on", "ano"}

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SEARCH_MODES = ("list", "context", "find")
ADMIN_ROLES = ("user", "admin")
PEER_SCOPES = ("actor", "all")
MESSAGE_ROLES = ("user", "assistant", "system")
# user = id role, peer = id projektu Opory; server odmítá peer s lomítkem, my ho nepustíme dál.
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
TAG = re.compile(r"[A-Za-z0-9_.:-]{1,60}=[^\s=]{1,120}")


class OpenVikingUnavailable(OSError):
    """OpenViking neodpověděl pravdivým výsledkem; nikdy se nenahrazuje odhadem."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} musí být krátký identifikátor bez mezer a lomítek.")
    return value


def _validated_base_url(base_url):
    parts = urlsplit(base_url)
    if parts.scheme != "http" or (parts.hostname or "").lower() not in LOOPBACK_HOSTS:
        raise ValueError("Adresa OpenVikingu musí být http na loopbacku.")
    if parts.username or parts.password or parts.query or parts.fragment or parts.path.strip("/"):
        raise ValueError("Adresa OpenVikingu nesmí nést přihlášení, cestu ani dotaz.")
    return base_url.rstrip("/")


def admin_api_key_from_env():
    """Správcovský klíč: jen pro provisioning rolí, nikdy pro čtení a zápis dat role."""
    for name in (ADMIN_KEY_ENV, LEGACY_KEY_ENV):
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _float_env(name, default):
    """Kladné desetinné číslo z prostředí; prázdné nebo nesmyslné se čte jako výchozí hodnota."""
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def client_from_env(**overrides):
    """Konfigurace z prostředí; router ani služba si adresu ani klíč nevymýšlí."""
    settings = {
        "base_url": os.environ.get(URL_ENV) or DEFAULT_OPENVIKING_URL,
        "api_key": admin_api_key_from_env(),
        "account": os.environ.get(ACCOUNT_ENV) or DEFAULT_ACCOUNT,
        "trusted_identity": (os.environ.get(TRUSTED_ENV) or "").strip().lower() in TRUTHY,
        "timeout": _float_env(TIMEOUT_ENV, TIMEOUT_SECONDS),
        "data_timeout": _float_env(DATA_TIMEOUT_ENV, DATA_TIMEOUT_SECONDS),
    }
    settings.update(overrides)
    return OpenVikingClient(**settings)


class OpenVikingClient:
    """Tenký, synchronní klient nad API v1; vrací `result` z obálky, nic si nedomýšlí."""

    def __init__(self, base_url=None, api_key=None, account=None, *, trusted_identity=False,
                 urlopen=None, timeout=TIMEOUT_SECONDS, data_timeout=DATA_TIMEOUT_SECONDS):
        self.base_url = _validated_base_url(base_url or DEFAULT_OPENVIKING_URL)
        self.account = _identifier(account or DEFAULT_ACCOUNT, "Účet OpenVikingu")
        self.trusted_identity = bool(trusted_identity)
        self._api_key = api_key if isinstance(api_key, str) and api_key.strip() else None
        self._timeout = float(timeout)
        self._data_timeout = float(data_timeout)
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler)
        self._urlopen = urlopen or self._opener.open

    @property
    def has_api_key(self):
        """Pravdivá odpověď na „mám čím se představit“; klíč sám se nikdy nevydává."""
        return self._api_key is not None

    def with_api_key(self, api_key):
        """Týž přenos, jiný klíč = jiná identita. Tím si služba staví klienta na roli."""
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Klíč OpenVikingu musí být neprázdný text.")
        return OpenVikingClient(self.base_url, api_key.strip(), self.account,
                                trusted_identity=self.trusted_identity,
                                urlopen=self._urlopen, timeout=self._timeout,
                                data_timeout=self._data_timeout)

    # ---- přenos ---------------------------------------------------------------------

    def _request(self, method, path, payload=None, *, user=None, peer=None, timeout=None):
        data = None
        request = urllib.request.Request(self.base_url + path, method=method)
        request.add_header("Accept", "application/json")
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request.data = data
            request.add_header("Content-Type", "application/json")
        if self._api_key:
            request.add_header("X-API-Key", self._api_key)
        if self.trusted_identity:
            # Jen pro nasazení `auth_mode: trusted`. V režimu api_key server tyhle hlavičky
            # buď ignoruje, nebo na ně odpoví 403 — identitu tam nese výhradně klíč.
            request.add_header("X-OpenViking-Account", self.account)
            if user is not None:
                request.add_header("X-OpenViking-User", user)
            if peer is not None:
                request.add_header("X-OpenViking-Actor-Peer", peer)
        return self._read(request, self._timeout if timeout is None else timeout)

    def _read(self, request, timeout):
        try:
            with self._urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise OpenVikingUnavailable(f"OpenViking odpověděl stavem {error.code}.") from error
        except OpenVikingUnavailable:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise OpenVikingUnavailable("OpenViking není dostupný.") from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OpenVikingUnavailable("Odpověď OpenVikingu překročila povolenou velikost.")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise OpenVikingUnavailable("OpenViking nevrátil platný JSON.") from error
        if not isinstance(body, dict):
            raise OpenVikingUnavailable("OpenViking nevrátil JSON objekt.")
        return body

    @staticmethod
    def _envelope(body):
        """Obálka `{status, result, time}`; chyba má `{status, error:{code,message}}`."""
        if body.get("status") != "ok":
            error = body.get("error") if isinstance(body.get("error"), dict) else {}
            code = str(error.get("code", "UNKNOWN"))[:60]
            message = str(error.get("message", ""))[:240]
            raise OpenVikingUnavailable(f"OpenViking vrátil chybu {code}: {message}")
        return body.get("result")

    @classmethod
    def _result(cls, body):
        result = cls._envelope(body)
        if not isinstance(result, dict):
            raise OpenVikingUnavailable("OpenViking vrátil neočekávaný tvar výsledku.")
        return result

    # ---- zdraví ---------------------------------------------------------------------

    def health(self):
        """`GET /health` nemá obálku `result`; čte se přímo tělo a nevyžaduje ověření."""
        body = self._request("GET", "/health")
        if body.get("status") != "ok" or body.get("healthy") is not True:
            raise OpenVikingUnavailable("OpenViking hlásí, že není zdravý.")
        version = body.get("version")
        return {"healthy": True, "version": version if isinstance(version, str) else ""}

    # ---- vyhledání ------------------------------------------------------------------

    def search(self, user, query, *, mode, target_uri=None, peer=None, peer_scope="actor", limit=20):
        """`POST /api/v1/search/search`.

        `mode="context"` skládá blok sám, ale **neumí `target_uri`** (server vrací 400), takže
        rozsahové čtení role a projektu jde přes `mode="list"`. Naopak parametry jen pro
        context (`peer_scope`) se do list módu neposílají — server by je odmítl.
        """
        _identifier(user, "Role (user OpenVikingu)")
        if mode not in SEARCH_MODES:
            raise ValueError("Neplatný režim vyhledání v OpenVikingu.")
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("Dotaz do paměti musí být neprázdný text do 2000 znaků.")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limit výsledků musí být 1 až 100.")
        if peer is not None:
            _identifier(peer, "Projekt (peer OpenVikingu)")
        body = {"query": query, "mode": mode, "limit": limit}
        if mode == "context":
            if target_uri is not None:
                raise ValueError("Režim context neumí target_uri; použijte list.")
            if peer_scope not in PEER_SCOPES:
                raise ValueError("peer_scope musí být actor nebo all.")
            body["peer_scope"] = peer_scope
        elif target_uri is not None:
            body["target_uri"] = _viking_uri(target_uri)
        path = "/api/v1/search/find" if mode == "find" else "/api/v1/search/search"
        if mode == "find":
            body.pop("mode")
        return self._result(self._request("POST", path, body, user=user, peer=peer,
                                           timeout=self._data_timeout))

    # ---- zápis ----------------------------------------------------------------------

    def write(self, user, uri, text, tags=None):
        """`POST /api/v1/content/write` (+ volitelně `content/set_tags`).

        Štítky jsou metadata pro filtr; když se nepodaří je nastavit, zápis obsahu tím
        nemizí — výsledek jen pravdivě řekne `tagsApplied: false`.
        """
        _identifier(user, "Role (user OpenVikingu)")
        uri = _viking_uri(uri)
        if not isinstance(text, str) or "\0" in text or not text.strip() or len(text) > MAX_CONTENT_CHARS:
            raise ValueError(f"Obsah zápisu musí být neprázdný text do {MAX_CONTENT_CHARS} znaků bez NUL.")
        clean = _tags(tags)
        result = self._result(self._request(
            "POST", "/api/v1/content/write",
            {"uri": uri, "content": text, "mode": "replace", "wait": False}, user=user,
            timeout=self._data_timeout,
        ))
        applied = False
        if clean:
            try:
                self._result(self._request(
                    "POST", "/api/v1/content/set_tags",
                    {"uri": uri, "tags": clean, "mode": "replace"}, user=user,
                    timeout=self._data_timeout,
                ))
                applied = True
            except OpenVikingUnavailable:
                applied = False
        return {**result, "tagsApplied": applied}

    # ---- session a úlohy ------------------------------------------------------------

    def session_create(self, user, peer=None):
        _identifier(user, "Role (user OpenVikingu)")
        if peer is not None:
            _identifier(peer, "Projekt (peer OpenVikingu)")
        return self._result(self._request("POST", "/api/v1/sessions", {}, user=user, peer=peer,
                                           timeout=self._data_timeout))

    def session_add(self, user, session_id, role, content, peer=None):
        """Projekt (peer) jde do těla jako `peer_id`; hlavička identity v api_key režimu neplatí."""
        _identifier(user, "Role (user OpenVikingu)")
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ValueError("Neplatný identifikátor session OpenVikingu.")
        if role not in MESSAGE_ROLES:
            raise ValueError("Role zprávy musí být user, assistant nebo system.")
        if not isinstance(content, str) or "\0" in content or not content.strip() or len(content) > MAX_CONTENT_CHARS:
            raise ValueError(f"Zpráva musí být neprázdný text do {MAX_CONTENT_CHARS} znaků bez NUL.")
        body = {"role": role, "content": content}
        if peer is not None:
            body["peer_id"] = _identifier(peer, "Projekt (peer OpenVikingu)")
        path = f"/api/v1/sessions/{quote(session_id, safe='')}/messages"
        return self._result(self._request("POST", path, body, user=user, peer=peer,
                                           timeout=self._data_timeout))

    def session_commit(self, user, session_id):
        """Commit je asynchronní: vrací `task_id`, extrakci paměti dělá OpenViking sám."""
        _identifier(user, "Role (user OpenVikingu)")
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ValueError("Neplatný identifikátor session OpenVikingu.")
        path = f"/api/v1/sessions/{quote(session_id, safe='')}/commit"
        return self._result(self._request("POST", path, {}, user=user, timeout=self._data_timeout))

    def task(self, task_id, user=None):
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise ValueError("Neplatný identifikátor úlohy OpenVikingu.")
        if user is not None:
            _identifier(user, "Role (user OpenVikingu)")
        return self._result(self._request("GET", f"/api/v1/tasks/{quote(task_id, safe='')}", user=user,
                                           timeout=self._data_timeout))

    # ---- správa uživatelů (jen se správcovským klíčem) --------------------------------

    def admin_list_users(self, account=None):
        """`GET /api/v1/admin/accounts/{account}/users`; `result` je **pole**, ne objekt."""
        path = f"{self._account_path(account)}/users"
        listed = self._envelope(self._request("GET", path))
        if not isinstance(listed, list):
            raise OpenVikingUnavailable("OpenViking nevrátil seznam uživatelů.")
        return [item for item in listed
                if isinstance(item, dict) and isinstance(item.get("user_id"), str)]

    def admin_register_user(self, account, user_id, role="user"):
        """Založí uživatele (= roli) a vrátí **jeho klíč**. ADMIN smí jen ve svém účtu."""
        _identifier(user_id, "Uživatel OpenVikingu")
        if role not in ADMIN_ROLES:
            raise ValueError("Role uživatele OpenVikingu musí být user nebo admin.")
        path = f"{self._account_path(account)}/users"
        return _user_key(self._result(self._request("POST", path, {"user_id": user_id, "role": role})))

    def admin_regenerate_key(self, account, user_id):
        """Nový klíč existujícího uživatele; starý okamžitě přestává platit."""
        _identifier(user_id, "Uživatel OpenVikingu")
        path = f"{self._account_path(account)}/users/{quote(user_id, safe='')}/key"
        return _user_key(self._result(self._request("POST", path, {})))

    def _account_path(self, account):
        account = _identifier(account or self.account, "Účet OpenVikingu")
        return f"/api/v1/admin/accounts/{quote(account, safe='')}"


def _user_key(result):
    """Klíč role. Vrací se jen dovnitř služby; nikdy do odpovědi API ani do logu."""
    key = result.get("user_key")
    if not isinstance(key, str) or not key.strip():
        raise OpenVikingUnavailable("OpenViking nevrátil klíč uživatele.")
    return key.strip()


def _viking_uri(value):
    if not isinstance(value, str) or not value.startswith("viking://") or len(value) > 1000:
        raise ValueError("URI musí být viking:// adresa do 1000 znaků.")
    if "\0" in value or any(part in {"", ".", ".."} for part in value[len("viking://"):].split("/")):
        raise ValueError("URI nesmí obsahovat prázdné ani relativní části.")
    return value


def _tags(tags):
    if tags is None:
        return []
    if not isinstance(tags, (list, tuple)) or len(tags) > 20:
        raise ValueError("Štítky musí být pole nejvýše 20 položek ve tvaru k=v.")
    clean = []
    for tag in tags:
        if not isinstance(tag, str) or not TAG.fullmatch(tag):
            raise ValueError("Štítek musí mít přesný tvar k=v.")
        clean.append(tag)
    return clean

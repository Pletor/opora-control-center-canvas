"""Paměť agenta podle role: co role ví napříč projekty a co ví u jedné karty.

Mapování na OpenViking (`docs/pamet-agentu.md`): `user` = role (`role-frontend`…),
`peer` = projekt Opory, sekce karty jsou resources pod
`viking://user/{role}/peers/{project}/resources/cards/{nodeId}/`. OpenViking sám nezná pojem
projekt ani karta — tuto strukturu drží Opora v adresách a ve štítcích.

**Klíč na roli.** OpenViking běží v režimu `auth_mode: api_key` a identitu si odvozuje
z předloženého klíče — hlavičkou se za jiného uživatele vydávat nelze (ověřeno: 403). Role
proto není hlavička, ale **vlastní uživatel OpenVikingu s vlastním klíčem**. Správcovský klíč
(`OPORA_OPENVIKING_ADMIN_API_KEY`) umí jediné: rozdat rolím klíče (`provision_roles`). Data
čte a zapisuje vždy klíč té role. Klíče leží v `app_settings` pod `openviking.roleKeys`;
**nikdy** nejdou do odpovědi API ani do logu.

Čtyři pravidla, která tenhle modul nikdy neporuší:

1. **Aplikace nespouští model.** Zapisuje texty a otevírá session; extrakci dělá OpenViking
   uvnitř sebe. Odsud odchází data, nikdy příkaz modelu.
2. **Když je paměť vypnutá nebo server dole, řekne se to.** Každá metoda vrací
   `status: disabled | unavailable | skipped | needs_provisioning | configured`; nikdy prázdný
   výsledek, který by vypadal jako „nic jsme si nezapamatovali“.
3. **Zápis na pozadí (zrcadlení karty, uzavření karty) nikdy nepoloží uložení v Opoře.**
   `mirror_workspace` a `commit_card` nevyhazují výjimku, jen vrací seznam chyb.
4. **Tajemství nikdy neodchází.** Klíč role se nevrací, nevypisuje a neporovnává v odpovědi;
   ven jde jen „má klíč / nemá klíč“.

Přepínač je nastavení **celé aplikace**, ne projektu: leží v `registry.sqlite` v tabulce
`app_settings` a výchozí hodnotu bere z `OPORA_OPENVIKING_ENABLED`.
"""

import json
import os
import re
from datetime import UTC, datetime

from backend.integrations.openviking_client import (
    ADMIN_KEY_ENV,
    DEFAULT_OPENVIKING_URL,
    OpenVikingUnavailable,
    client_from_env,
)
from backend.memory import roles

SETTINGS_KEY = "openviking.enabled"
ROLE_KEYS_SETTING = "openviking.roleKeys"
ENABLED_ENV = "OPORA_OPENVIKING_ENABLED"
# Klíč TypeSafe Jev pro směrovač asistenta (docs/asistent.md §13.2); platí pro celou aplikaci.
TYPESAFE_KEY_SETTING = "typesafe.apiKey"
TYPESAFE_KEY_ENV = "TYPESAFE_API_KEY"
MAX_TYPESAFE_KEY = 512
TRUTHY = {"1", "true", "yes", "on", "ano"}
MAX_ROLE_KEY = 512

KINDS = ("note", "lesson", "decision")
CARD_SECTIONS = ("frame", "log", "failures", "fixes", "handoff")
SECTION_TITLES = {
    "frame": "Rámec a směr", "log": "Pracovní postup", "failures": "Co se nepovedlo",
    "fixes": "Úspěšné opravy", "handoff": "Předávka",
}

MAX_QUERY = 2000
MAX_TEXT = 12000
MAX_TOKENS = 4000
DEFAULT_MAX_TOKENS = 600
CHARS_PER_TOKEN = 4
SEARCH_LIMIT = 20
SCOPE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")

DISABLED_REASON = "Paměť rolí je v nastavení aplikace vypnutá."
NO_KEY_REASON = "Role nemá klíč; spusť provisioning."
NO_ADMIN_KEY_REASON = f"Chybí správcovský klíč OpenVikingu ({ADMIN_KEY_ENV}); role nelze založit."


def _clean_role_keys(mapping):
    """Mapa `role → klíč`. Neplatný tvar je chyba, ne tiše zahozené tajemství."""
    if not isinstance(mapping, dict):
        raise ValueError("Klíče rolí musí být objekt role → klíč.")
    clean = {}
    for role_id, key in mapping.items():
        if not isinstance(role_id, str) or not SCOPE_ID.fullmatch(role_id):
            raise ValueError("Klíč role musí být vedený pod krátkým id role.")
        if not isinstance(key, str) or not key.strip() or len(key) > MAX_ROLE_KEY:
            raise ValueError(f"Klíč role musí být neprázdný text do {MAX_ROLE_KEY} znaků.")
        clean[role_id] = key.strip()
    return clean


class AppSettings:
    """Nastavení platné pro celou aplikaci; nikdy se neukládá s klíčem projektu."""

    def __init__(self, canvas, key=SETTINGS_KEY, env=ENABLED_ENV, keys_key=ROLE_KEYS_SETTING):
        self.canvas = canvas
        self.key = key
        self.env = env
        self.keys_key = keys_key

    def _default(self):
        return (os.environ.get(self.env) or "").strip().lower() in TRUTHY

    def _read(self, key):
        with self.canvas.registry_lock:
            row = self.canvas.db.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,)
            ).fetchone()
        return None if row is None else row[0]

    def _write(self, key, value):
        with self.canvas.registry_lock, self.canvas.db:
            self.canvas.db.execute("INSERT OR REPLACE INTO app_settings VALUES(?,?)", (key, value))

    def enabled(self):
        stored = self._read(self.key)
        return self._default() if stored is None else stored == "1"

    def set_enabled(self, value):
        if type(value) is not bool:
            raise ValueError("Přepínač paměti rolí musí být true/false.")
        self._write(self.key, "1" if value else "0")
        return value

    def role_keys(self):
        """Klíče rolí jako `{role: klíč}`; poškozený zápis se čte jako „žádné klíče“."""
        raw = self._read(self.keys_key)
        try:
            stored = json.loads(raw) if raw else {}
            return _clean_role_keys(stored)
        except (TypeError, ValueError):
            return {}

    def set_role_keys(self, mapping):
        """Uloží klíče a vrátí **jen jména rolí** — tajemství se ven nevrací."""
        clean = _clean_role_keys(mapping)
        self._write(self.keys_key, json.dumps(clean, ensure_ascii=False, sort_keys=True))
        return sorted(clean)

    def typesafe_key(self):
        """Klíč Jev z nastavení aplikace, jinak z prostředí backendu; `None`, když chybí."""
        stored = self._read(TYPESAFE_KEY_SETTING)
        return stored or (os.environ.get(TYPESAFE_KEY_ENV) or "").strip() or None

    def set_typesafe_key(self, key):
        """Uloží (text) nebo smaže (`None`) klíč a vrátí jen, zda je nastavený."""
        if key is None:
            with self.canvas.registry_lock, self.canvas.db:
                self.canvas.db.execute("DELETE FROM app_settings WHERE key=?", (TYPESAFE_KEY_SETTING,))
        elif not isinstance(key, str) or not key.strip() or len(key) > MAX_TYPESAFE_KEY or any(
                ord(c) < 33 for c in key.strip()):
            raise ValueError(f"Klíč TypeSafe musí být text bez mezer do {MAX_TYPESAFE_KEY} znaků.")
        else:
            self._write(TYPESAFE_KEY_SETTING, key.strip())
        return self.typesafe_key() is not None


class _EnvToggle:
    """Záložní přepínač bez úložiště: čte jen prostředí, zápis platí do restartu."""

    def __init__(self, env=ENABLED_ENV):
        self._value = (os.environ.get(env) or "").strip().lower() in TRUTHY
        self._keys = {}

    def enabled(self):
        return self._value

    def set_enabled(self, value):
        if type(value) is not bool:
            raise ValueError("Přepínač paměti rolí musí být true/false.")
        self._value = value
        return value

    def role_keys(self):
        return dict(self._keys)

    def set_role_keys(self, mapping):
        self._keys = _clean_role_keys(mapping)
        return sorted(self._keys)


def _fail(message):
    raise ValueError(message)


def _role(role_id, label="Role"):
    if roles.role(role_id) is None:
        _fail(f"{label} {role_id!r} není v knihovně rolí agenta.")
    return role_id


def _scope(value, label):
    """Projekt i uzel jsou volitelné; když přijdou, musí být krátký identifikátor."""
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not SCOPE_ID.fullmatch(value):
        _fail(f"{label} musí být krátký identifikátor bez mezer a lomítek.")
    return value


def _query(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_QUERY:
        _fail(f"Dotaz do paměti musí být neprázdný text do {MAX_QUERY} znaků.")
    return value.strip()


def _budget(max_tokens):
    if max_tokens is None:
        return DEFAULT_MAX_TOKENS
    if type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKENS:
        _fail(f"maxTokens musí být celé číslo 1 až {MAX_TOKENS}.")
    return max_tokens


def _stamp():
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def memories_uri(role):
    return f"viking://user/{role}/memories"


def peer_uri(role, project):
    return f"viking://user/{role}/peers/{project}"


def card_uri(role, project, node_id, name):
    return f"{peer_uri(role, project)}/resources/cards/{node_id}/{name}"


def _hit_text(item):
    """L0 abstract je u pamětí celé tělo; overview je náhrada, když abstract chybí."""
    for key in ("abstract", "overview", "text", "content"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _hits(result):
    found = []
    if not isinstance(result, dict):
        return found
    for key in ("memories", "resources", "skills", "entries"):
        bucket = result.get(key)
        if isinstance(bucket, list):
            found.extend(item for item in bucket if isinstance(item, dict) and isinstance(item.get("uri"), str))
    return found


def _score(item):
    value = item.get("score")
    return float(value) if isinstance(value, (int, float)) and type(value) is not bool else 0.0


def render(items):
    """Blok, který jde vložit do kontextu agenta: jeden řádek hlavičky a text pod ním."""
    lines = []
    for item in items:
        lines.append(f"- {item['uri']} · {item['origin']} · skóre {item['score']:.2f}")
        if item["text"]:
            lines.append("  " + item["text"].replace("\n", "\n  "))
    return "\n".join(lines)


class MemoryService:
    """Jediné místo, kde Opora sahá na paměť rolí; routery a balíčky volají jen tohle."""

    def __init__(self, client_factory=None, settings_store=None):
        self._client_factory = client_factory or client_from_env
        self.settings = settings_store or _EnvToggle()

    # ---- dostupnost -----------------------------------------------------------------

    def _client(self, api_key=None):
        """Bez klíče = správcovský klient z prostředí; s klíčem = klient jedné role."""
        try:
            client = self._client_factory()
            return client.with_api_key(api_key) if api_key else client
        except (ValueError, OSError) as error:
            raise OpenVikingUnavailable(str(error)) from error

    def _role_keys(self):
        return dict(self.settings.role_keys())

    def _role_client(self, role):
        """Klient s klíčem role. Bez klíče se nic nevymýšlí — volající vrátí `unavailable`."""
        key = self._role_keys().get(role)
        if not isinstance(key, str) or not key.strip():
            raise OpenVikingUnavailable(NO_KEY_REASON)
        return self._client(key)

    def missing_roles(self):
        """Role z knihovny, které zatím nemají vlastní klíč; klíče samotné nikam nejdou."""
        stored = self._role_keys()
        return [role_id for role_id in roles.role_ids()
                if not (isinstance(stored.get(role_id), str) and stored[role_id].strip())]

    def _url(self):
        try:
            return self._client().base_url
        except OpenVikingUnavailable:
            return os.environ.get("OPORA_OPENVIKING_URL") or DEFAULT_OPENVIKING_URL

    def enabled(self):
        return bool(self.settings.enabled())

    def status(self):
        """`configured` až když server odpoví **a** každá role má svůj klíč.

        `disabled` = vypnuto v nastavení, `unavailable` = server neodpověděl zdravím,
        `needs_provisioning` = chybí správcovský klíč nebo klíče rolí (`missingRoles`).
        """
        if not self.enabled():
            return {"status": "disabled", "reason": DISABLED_REASON, "url": self._url()}
        try:
            client = self._client()
            client.health()
            missing = self.missing_roles()
        except (OpenVikingUnavailable, ValueError) as error:
            return {"status": "unavailable", "reason": str(error), "url": self._url()}
        if not client.has_api_key:
            return {"status": "needs_provisioning", "reason": NO_ADMIN_KEY_REASON,
                    "url": client.base_url, "missingRoles": missing}
        if missing:
            return {"status": "needs_provisioning", "url": client.base_url, "missingRoles": missing,
                    "reason": "Bez klíče zůstávají role: " + ", ".join(missing) + "."}
        return {"status": "configured", "reason": "OpenViking odpovídá na loopbacku.",
                "url": client.base_url}

    # ---- rozdání klíčů rolím ----------------------------------------------------------

    def provision_roles(self):
        """Každá role z knihovny dostane vlastního uživatele OpenVikingu a vlastní klíč.

        Klíč, který už máme uložený, se nechává být (`reused`) — regenerace by zneplatnila
        klíč, se kterým právě někdo pracuje. Roli, která u serveru už existuje, ale klíč k ní
        nemáme, nelze přečíst zpět; jediná pravdivá cesta je nový klíč (`admin_regenerate_key`).
        Výsledek nese jen jména rolí a důvody chyb, **nikdy klíče**.
        """
        empty = {"provisioned": [], "reused": [], "errors": []}
        if not self.enabled():
            return {"status": "disabled", "reason": DISABLED_REASON, **empty}
        try:
            client = self._client()
            role_ids = roles.role_ids()
        except (OpenVikingUnavailable, ValueError) as error:
            return {"status": "unavailable", "reason": str(error), **empty}
        if not client.has_api_key:
            return {"status": "needs_admin_key", "reason": NO_ADMIN_KEY_REASON, **empty}
        try:
            existing = {item["user_id"] for item in client.admin_list_users(client.account)}
        except (ValueError, OSError) as error:
            return {"status": "unavailable", "reason": str(error), **empty}
        stored, provisioned, reused, errors = self._role_keys(), [], [], []
        for role_id in role_ids:
            key = stored.get(role_id)
            if isinstance(key, str) and key.strip():
                reused.append(role_id)
                continue
            try:
                stored[role_id] = (client.admin_regenerate_key(client.account, role_id)
                                   if role_id in existing
                                   else client.admin_register_user(client.account, role_id))
                provisioned.append(role_id)
            except (ValueError, OSError) as error:
                errors.append({"role": role_id, "reason": str(error)})
        if provisioned:
            self.settings.set_role_keys(stored)
        status = "configured" if not errors else ("partial" if provisioned or reused else "unavailable")
        return {"status": status, "account": client.account,
                "provisioned": provisioned, "reused": reused, "errors": errors}

    def bootstrap_status(self):
        """Stav pro bootstrap klienta: **bez síťového volání**, jen podle přepínače."""
        enabled = self.enabled()
        return {"enabled": enabled, "status": "unknown" if enabled else "disabled"}

    # ---- vybavení -------------------------------------------------------------------

    def recall(self, role, project, node_id, query, max_tokens=DEFAULT_MAX_TOKENS):
        """Paměť role (napříč projekty) a k ní paměť projektu; ořez podle rozpočtu tokenů."""
        role = _role(role)
        project, node_id = _scope(project, "Projekt"), _scope(node_id, "Uzel")
        query, budget = _query(query), _budget(max_tokens)
        return self._recall(role, role, project, query, budget, origin=None)

    def lend(self, from_role, to_role, query, max_tokens=DEFAULT_MAX_TOKENS):
        """Půjčka z paměti jiné role; každá položka je označená `lent:<role>`, nikdy `self`."""
        from_role = _role(from_role, "Půjčující role")
        to_role = _role(to_role, "Žádající role")
        query, budget = _query(query), _budget(max_tokens)
        result = self._recall(from_role, to_role, None, query, budget, origin=f"lent:{from_role}")
        return {**result, "fromRole": from_role}

    def _recall(self, source_role, reported_role, project, query, budget, origin=None):
        if not self.enabled():
            return self._empty_recall("disabled", DISABLED_REASON, reported_role)
        scopes = [(memories_uri(source_role), None, "self")]
        if project:
            scopes.append((peer_uri(source_role, project), project, "project"))
        collected = []
        try:
            client = self._role_client(source_role)
            for target, peer, label in scopes:
                found = client.search(source_role, query, mode="list", target_uri=target,
                                      peer=peer, limit=SEARCH_LIMIT)
                for item in _hits(found):
                    collected.append({
                        "uri": item["uri"], "text": _hit_text(item), "score": _score(item),
                        "origin": origin or label,
                    })
        except OpenVikingUnavailable as error:
            return self._empty_recall("unavailable", str(error), reported_role)
        items, truncated = self._bounded(collected, budget)
        return {"status": "configured", "role": reported_role, "items": items,
                "rendered": render(items), "truncated": truncated}

    @staticmethod
    def _empty_recall(status, reason, role):
        return {"status": status, "reason": reason, "role": role,
                "items": [], "rendered": "", "truncated": False}

    @staticmethod
    def _bounded(collected, max_tokens):
        """Deterministické pořadí (skóre sestupně, pak URI) a tvrdý strop ≈4 znaky na token."""
        unique = {}
        for item in sorted(collected, key=lambda entry: (-entry["score"], entry["uri"])):
            unique.setdefault(item["uri"], item)
        remaining, truncated, items = max_tokens * CHARS_PER_TOKEN, False, []
        for item in unique.values():
            if remaining <= 0:
                truncated = True
                break
            text = item["text"][:remaining]
            if len(text) < len(item["text"]):
                truncated = True
            remaining -= len(text)
            items.append({**item, "text": text})
        return items, truncated

    # ---- zapamatování ---------------------------------------------------------------

    def remember(self, role, project, node_id, kind, text):
        """Jedna poznámka, poučení nebo rozhodnutí jako samostatný zdroj (historie se nepřepisuje)."""
        role = _role(role)
        project, node_id = _scope(project, "Projekt"), _scope(node_id, "Uzel")
        if kind not in KINDS:
            _fail(f"Druh zápisu musí být jeden z {', '.join(KINDS)}.")
        if not isinstance(text, str) or "\0" in text or not text.strip() or len(text) > MAX_TEXT:
            _fail(f"Text zápisu musí být neprázdný text do {MAX_TEXT} znaků bez NUL.")
        if not self.enabled():
            return {"status": "disabled", "reason": DISABLED_REASON, "uri": ""}
        name = f"{kind}-{_stamp()}.md"
        if project and node_id:
            uri = card_uri(role, project, node_id, name)
        else:
            uri = f"viking://user/{role}/resources/opora/{name}"
        tags = ["opora=1", f"role={role}", f"kind={kind}"]
        if project:
            tags.append(f"project={project}")
        if node_id:
            tags.append(f"node={node_id}")
        try:
            written = self._role_client(role).write(role, uri, text, tags=sorted(tags))
        except OpenVikingUnavailable as error:
            return {"status": "unavailable", "reason": str(error), "uri": ""}
        return {"status": "configured", "uri": uri, "tagsApplied": bool(written.get("tagsApplied"))}

    # ---- zápis na pozadí (nikdy nevyhazuje výjimku) ----------------------------------

    def mirror_workspace(self, role, project, node_id, sections):
        """Zrcadlí neprázdné sekce prostoru karty; uložení v Opoře na tom nikdy nestojí."""
        try:
            role = _role(role)
            project, node_id = _scope(project, "Projekt"), _scope(node_id, "Uzel")
            named = self._named_sections(sections)
        except ValueError as error:
            return {"status": "skipped", "reason": str(error), "mirrored": [], "errors": []}
        if not project or not node_id:
            return {"status": "skipped", "reason": "Zrcadlení potřebuje projekt i kartu.",
                    "mirrored": [], "errors": []}
        if not self.enabled():
            return {"status": "disabled", "reason": DISABLED_REASON, "mirrored": [], "errors": []}
        if not named:
            return {"status": "configured", "mirrored": [], "errors": []}
        mirrored, errors = [], []
        try:
            client = self._role_client(role)
        except OpenVikingUnavailable as error:
            return {"status": "unavailable", "reason": str(error), "mirrored": [],
                    "errors": [{"section": key, "reason": str(error)} for key, _ in named]}
        for key, value in named:
            uri = card_uri(role, project, node_id, f"{key}.md")
            try:
                client.write(role, uri, value, tags=sorted(
                    ["opora=1", f"role={role}", f"project={project}", f"node={node_id}", f"section={key}"]
                ))
                mirrored.append(uri)
            except (ValueError, OSError) as error:
                errors.append({"section": key, "reason": str(error)})
        status = "configured" if not errors else ("unavailable" if not mirrored else "partial")
        return {"status": status, "mirrored": mirrored, "errors": errors}

    def commit_card(self, role, project, node_id, sections):
        """Uzavřená karta jde do OpenVikingu jako session; extrakci si udělá on sám (async)."""
        try:
            role = _role(role)
            project, node_id = _scope(project, "Projekt"), _scope(node_id, "Uzel")
            named = self._named_sections(sections)
        except ValueError as error:
            return {"status": "skipped", "reason": str(error)}
        if not project or not node_id:
            return {"status": "skipped", "reason": "Uzavření karty potřebuje projekt i kartu."}
        if not self.enabled():
            return {"status": "disabled", "reason": DISABLED_REASON}
        if not named:
            return {"status": "skipped", "reason": "Karta nemá co předat: všechny sekce jsou prázdné."}
        try:
            client = self._role_client(role)
            session = client.session_create(role, project)
            session_id = session.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                return {"status": "unavailable", "error": "OpenViking nevrátil identifikátor session."}
            # Jedna zpráva na sekci; hlavičku nese každá zpráva, aby stála sama o sobě.
            # Projekt jde do těla zprávy jako `peer_id` — hlavička identity v api_key režimu neplatí.
            for key, value in named:
                client.session_add(role, session_id, "user", (
                    f"Uzavřená karta {node_id} v projektu {project} (role {role}) — "
                    f"{SECTION_TITLES.get(key, key)}\n{value}"
                ), peer=project)
            committed = client.session_commit(role, session_id)
        except (ValueError, OSError) as error:
            return {"status": "unavailable", "error": str(error)}
        task_id = committed.get("task_id")
        return {"status": "configured", "taskId": task_id if isinstance(task_id, str) else ""}

    @staticmethod
    def _named_sections(sections):
        if not isinstance(sections, dict):
            _fail("Sekce prostoru karty musí být objekt.")
        unknown = set(sections) - set(CARD_SECTIONS)
        if unknown:
            _fail("Neznámá sekce prostoru karty: " + ", ".join(sorted(unknown)) + ".")
        named = []
        for key in CARD_SECTIONS:
            value = sections.get(key)
            if isinstance(value, str) and value.strip() and "\0" not in value:
                named.append((key, value[:MAX_TEXT]))
        return named

"""Plán přehrání cesty zákazníka (`docs/brana-cesty.md` §2): co má harness projektu udělat, aby cestu ověřil.

Čistá funkce nad stejným grafem jako `journeys.derive_journeys`, bez modelu a bez I/O. Opora testy nespouští ani
nástroj nepředepisuje; plán jen říká, kterou stránku otevřít, kde hledat prvek, co s ním udělat a kam se má
zákazník dostat. Výbava harnessu (u webu typicky Playwright) ho přehraje a odevzdá doklad (`journey_runs.py`).

- Cesta = dvojice `applicationId` + `journeyId`. Bez `application_id` musí být `journeyId` v grafu jednoznačné,
  jinak `JourneyAmbiguous` (HTTP 409); neznámá cesta je `JourneyNotFound` (404); rozbitá cesta (`broken`,
  chybí stránka kroku) plán nemá: `JourneyBroken` (409) s důvodem z `derive_journeys`.
- `baseUrl`: `environments[0].host` aplikace; bez schématu se doplní `http://` pro `localhost` / `127.0.0.1`,
  jinak `https://`. Aplikace bez prostředí klíč nemá (runner ho dostane přes `--base-url`). Do `digest` nevstupuje.
- Segmenty v pořadí `derive_journeys` (krok navazuje na `after`, jinak na předchozí). Pro segment `from → to`:
  `open` = `site.path` stránky kroku `from` (menu `"nav"` = `"/"`); `scope` = `[data-opora-section="<id>"]` podle
  `via.section` cílového kroku, bez ní `nav` u menu, jinak `body`; `do` = `via.do` (bez `via` `click`); `text` =
  `via.text`, jen když je; `expectPath` = `site.path` stránky kroku `to`. Nerealizovaný přechod (bez vazby na
  mapě) v plánu je: cestu nerozbíjí a přehrání ukáže, zda web přechod přesto nese.
- `digest`: `sha256:` + sha256 kompaktního JSON (`separators=(",", ":")`, `sort_keys=True`, UTF-8) objektu
  `{applicationId, journeyId, segments}`. Změna kroků, `via`, sekce nebo cesty stránky digest změní.
"""

import hashlib
import json

from backend.canvas.site_metadata import JOURNEY_FROM_NAV
from backend.project.architecture.journeys import derive_journeys

SCHEMA = "opora.journey-plan/1"
LOCAL_HOSTS = ("localhost", "127.0.0.1")


class JourneyNotFound(LookupError):
    """Cesta s tímto id (v této aplikaci) v grafu není."""


class JourneyConflict(ValueError):
    """Cesta plán mít nemůže nebo není jednoznačná (HTTP 409)."""


class JourneyAmbiguous(JourneyConflict):
    """Stejné `journeyId` mají dvě aplikace a volající aplikaci neurčil."""


class JourneyBroken(JourneyConflict):
    """Cesta je rozbitá (chybí stránka kroku), plán nemá."""


def base_url(application):
    """URL prvního prostředí aplikace, nebo None, když aplikace prostředí nemá."""
    site = application.get("site") if isinstance(application.get("site"), dict) else {}
    environments = site.get("environments")
    first = environments[0] if isinstance(environments, list) and environments else None
    host = first.get("host") if isinstance(first, dict) else None
    if not isinstance(host, str) or not host:
        return None
    if "://" in host:
        return host
    name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return ("http://" if name.lower() in LOCAL_HOSTS else "https://") + host


def section_scope(section):
    return '[data-opora-section="' + section.replace("\\", "\\\\").replace('"', '\\"') + '"]'


def _segment(source, target):
    via = target.get("via") if isinstance(target.get("via"), dict) else {}
    nav = source["page"] == JOURNEY_FROM_NAV
    section = via.get("section")
    scope = section_scope(section) if isinstance(section, str) and section else "nav" if nav else "body"
    text = via.get("text")
    return {"from": source["id"], "to": target["id"], "open": "/" if nav else source["path"], "scope": scope,
            "do": via.get("do") if via.get("do") in ("click", "submit") else "click",
            **({"text": text} if isinstance(text, str) and text else {}),
            "expectPath": target["path"]}


def digest(application_id, journey_id, segments):
    """Otisk plánu: na `baseUrl` nezávisí, změní ho každá změna přechodů."""
    body = json.dumps({"applicationId": application_id, "journeyId": journey_id, "segments": segments},
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _plan(item, by_id):
    steps = {step["id"]: step for step in item["steps"]}
    segments = [_segment(steps[segment["from"]], steps[segment["to"]]) for segment in item["segments"]]
    url = base_url(by_id.get(item["applicationId"], {}))
    return {"schema": SCHEMA, "applicationId": item["applicationId"], "journeyId": item["id"], "name": item["name"],
            **({"baseUrl": url} if url else {}),
            "digest": digest(item["applicationId"], item["id"], segments), "segments": segments}


def journey_digests(graph):
    """{(applicationId, journeyId): digest} pro všechny nerozbité cesty grafu (jedno odvození cest)."""
    by_id = {node["id"]: node for node in graph.get("nodes") or []}
    return {(item["applicationId"], item["id"]): _plan(item, by_id)["digest"]
            for item in derive_journeys(graph) if "broken" not in item}


def journey_plan(graph, journey_id, application_id=None):
    """Plán přehrání cesty `journey_id` (v aplikaci `application_id`, když je dána)."""
    matches = [item for item in derive_journeys(graph)
               if item["id"] == journey_id and application_id in (None, item["applicationId"])]
    if not matches:
        raise JourneyNotFound(f"Cesta {journey_id} neexistuje.")
    if len(matches) > 1:
        raise JourneyAmbiguous(f"Cestu {journey_id} mají aplikace "
                               f"{', '.join(item['applicationId'] for item in matches)}; určete parametr application.")
    [item] = matches
    if "broken" in item:
        raise JourneyBroken(f"Cesta {item['name']}: {item['broken']}")
    return _plan(item, {node["id"]: node for node in graph.get("nodes") or []})

"""Čisté funkce runneru záměru stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §6), bez prohlížeče.

`tools/journey_run.py --intent PAGE` z nich skládá přehrání plánu `opora.intent-plan/1` a doklad
`opora.intent-run/1`. Prohlížeč dodá jen `act(step) -> (ok, důvod)` a ověření `{"visible": f(text), "path": f(cesta)}`
(`intent_run_browser.py`); pořadí, vyhodnocení a doklad jsou tady.

- Kroky (`kind: "step"`) se dělají v pořadí plánu. Po prvním neprošlém kroku se nic dalšího nedělá: zbylé uzly
  jsou neověřené (`ok: null`) s důvodem, srdce budí jen ten skutečně neprošlý.
- Očekávání (`kind: "expect"`): `visible` = text `value` je na stránce vidět, `path` = cesta URL je `value`;
  `request`, `email`, `record` (i bez druhu) prohlížeč neověří, uzel je neověřený s důvodem.
"""
from __future__ import annotations

try:
    from tools.journey_run_logic import normalize_path, short_reason
except ImportError:  # spuštěno jako skript z tools/
    from journey_run_logic import normalize_path, short_reason  # type: ignore[no-redef]

PLAN_SCHEMA = "opora.intent-plan/1"
RUN_SCHEMA = "opora.intent-run/1"
BROWSER_CHECKS = ("visible", "path")


def check_plan(plan: object) -> dict:
    """Ověří, že odpověď serveru je plán záměru, kterému runner rozumí."""
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"server nevrátil plán {PLAN_SCHEMA}")
    for key in ("pageId", "workflowVersionId", "digest", "path"):
        if not isinstance(plan.get(key), str):
            raise TypeError(f"plán nemá {key}")
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("plán nemá žádný krok ani očekávání")
    for item in nodes:
        if not isinstance(item, dict) or not isinstance(item.get("nodeId"), str) or item.get("kind") not in ("step", "expect"):
            raise TypeError("uzel plánu je {nodeId, kind: step|expect, …}")
    return plan


def evaluate(item: dict, observe: dict) -> tuple[bool | None, str | None]:
    """Očekávání plánu → (ok, důvod); `ok` None = neověřeno."""
    check, value = item.get("check"), item.get("value")
    if check not in BROWSER_CHECKS:
        return None, f"neověřeno: kontrolu {check or 'bez druhu'} prohlížeč neověří"
    if not isinstance(value, str) or not value:
        return None, f"neověřeno: kontrola {check} nemá hodnotu"
    if check == "path":
        return (True, None) if observe["path"](value) else (False, f"cesta není {normalize_path(value)}")
    return (True, None) if observe["visible"](value) else (False, f"na stránce chybí „{value}“")


def node_result(node_id: str, ok: bool | None, reason: str | None = None) -> dict:
    result = {"nodeId": node_id, "ok": ok}
    if ok is not True:
        result["reason"] = short_reason(reason or "neznámá chyba")
    return result


def walk(plan: dict, act, observe: dict, log) -> list[dict]:
    """Přehraje uzly plánu v pořadí; po neprošlém kroku zbytek označí jako neověřený."""
    results, stopped = [], None
    for item in plan["nodes"]:
        if stopped:
            results.append(node_result(item["nodeId"], None, f"nepřehráno: krok {stopped} neprošel"))
            continue
        ok, reason = act(item) if item["kind"] == "step" else evaluate(item, observe)
        if item["kind"] == "step" and not ok:
            ok, stopped = False, item["nodeId"]
        log(f"{item['nodeId']}: {'ok' if ok else 'neověřeno: ' + str(reason) if ok is None else 'selhal: ' + str(reason)}")
        results.append(node_result(item["nodeId"], ok, reason))
    return results


def unopened(plan: dict, reason: str, log) -> list[dict]:
    """Stránka plánu se neotevřela: první uzel neprošel s důvodem, zbytek je nepřehraný."""
    log(f"{plan['nodes'][0]['nodeId']}: selhal: {reason}")
    first, *rest = plan["nodes"]
    return [node_result(first["nodeId"], False, reason),
            *(node_result(item["nodeId"], None, "nepřehráno: stránka se neotevřela") for item in rest)]


def build_run(plan: dict, results: list[dict]) -> dict:
    return {"schema": RUN_SCHEMA, "pageId": plan["pageId"], "workflowVersionId": plan["workflowVersionId"],
            "digest": plan["digest"], "nodes": results}


def run_passed(run: dict) -> bool:
    """Stejně jako server bez znalosti kroků: žádný uzel neprošel s `ok: false`."""
    return all(item["ok"] is not False for item in run["nodes"])

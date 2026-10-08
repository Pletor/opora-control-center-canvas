"""Structured reported evidence; references are validated, never fetched or asserted verified.

Důkaz je **deklarovaný** (hlásí ho agent nebo člověk); server ho nespouští ani nestahuje.
Proto (upgrade-opora #31): `[task]` karta a karta s kontrolami nesmí tests/merge odbýt
jako not_applicable, výsledek testů lze doložit lokálním během bez odkazu (`checksRun`
s exitCode 0, `logUrl` volitelný) a N/A od agenta potvrzuje vždy člověk (ne autonomie).
"""

from datetime import datetime

from backend.canvas.design_metadata import validate_design
from backend.canvas.graph import valid_id

KINDS = ("tests", "review", "merge")
STATUSES = ("pending", "passed", "failed", "not_applicable")


def evidence_json_schema():
    def record(fields):
        return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}
    text = {"type": "string", "maxLength": 4000}
    link = {"type": "string", "maxLength": 2048}
    proof = record({"status": {"type": "string", "enum": list(STATUSES)}, "url": link, "note": text})
    return record({**{kind: proof for kind in KINDS}, "checksRun": {
        "type": "array", "maxItems": 200, "items": record({
            "checkId": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,80}$"}, "command": text,
            "exitCode": {"type": "integer", "minimum": -2147483648, "maximum": 2147483647},
            "logUrl": link, "at": {"type": "string", "format": "date-time"},
        })}})


def _text(value, limit, label):
    if not isinstance(value, str) or "\0" in value or len(value) > limit:
        raise ValueError(f"Neplatné pole důkazu {label}.")


def _url(value):
    validate_design({"artifactUrl": value, "version": "evidence"})


def validate_evidence(value):
    if not isinstance(value, dict) or set(value) != {*KINDS, "checksRun"}:
        raise ValueError("Evidence musí mít tests, review, merge a checksRun.")
    for key in KINDS:
        item = value[key]
        if not isinstance(item, dict) or set(item) != {"status", "url", "note"} or item["status"] not in STATUSES:
            raise ValueError(f"Neplatný důkaz {key}: status, url, note.")
        _text(item["note"], 4000, "note")
        _text(item["url"], 2048, "url")
        if item["url"]:
            _url(item["url"])
        # Testy lze doložit lokálním během v checksRun (viz evidence_ready); review a merge odkazem.
        if item["status"] in ("passed", "failed") and not item["url"] and key != "tests":
            raise ValueError(f"Výsledek {key} vyžaduje odkaz na důkaz.")
        if item["status"] == "not_applicable" and not item["note"].strip():
            raise ValueError(f"Nevztahující se {key} vyžaduje zdůvodnění.")
    runs = value["checksRun"]
    if not isinstance(runs, list) or len(runs) > 200:
        raise ValueError("checksRun musí být pole nejvýše 200 kontrol.")
    seen = set()
    for run in runs:
        if not isinstance(run, dict) or set(run) != {"checkId", "command", "exitCode", "logUrl", "at"}:
            raise ValueError("Kontrola vyžaduje checkId, command, exitCode, logUrl a at.")
        if not valid_id(run["checkId"]) or run["checkId"] in seen:
            raise ValueError("Kontroly musí mít jedinečná checkId.")
        seen.add(run["checkId"])
        _text(run["command"], 4000, "command")
        if not run["command"].strip() or type(run["exitCode"]) is not int or not -2147483648 <= run["exitCode"] <= 2147483647:
            raise ValueError("Kontrola vyžaduje příkaz a celočíselný exitCode.")
        _text(run["logUrl"], 2048, "logUrl")
        if run["logUrl"]:
            _url(run["logUrl"])
        try:
            if not isinstance(run["at"], str) or len(run["at"]) > 40 or datetime.fromisoformat(run["at"]).tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("Čas kontroly musí být ISO 8601 s časovou zónou.") from None


def needs_real_tests(node):
    """`[task]` karta nebo karta s předepsanými kontrolami staví kód: testy a merge nejsou N/A."""
    return bool(node) and (bool(node.get("checks")) or node.get("name", "").startswith("[task] "))


def evidence_ready(value, node=None):
    if value is None:
        return False
    validate_evidence(value)
    if needs_real_tests(node) and any(value[key]["status"] == "not_applicable" for key in ("tests", "merge")):
        return False
    if value["tests"]["status"] == "passed" and not value["tests"]["url"] and not value["checksRun"]:
        return False
    return (all(value[key]["status"] in ("passed", "not_applicable") for key in KINDS)
            and all(run["exitCode"] == 0 for run in value["checksRun"])
            and (bool(value["checksRun"]) or value["tests"]["status"] == "not_applicable"))

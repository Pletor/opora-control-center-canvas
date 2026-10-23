"""Strop předávky v zadání (`assignment.handoff`, docs/oporahub-executions.md „Předávka v zadání“).

Čisté funkce bez služby. Vstupem jsou úplné položky předchůdců a toků do oblasti, už seřazené od
nejbližší a nejnovější. Každá položka má úrovně: 0 je úplná (jen pro porovnání), 1 je výchozí
(limity polí), 2–4 postupně méně textu. Když balíček přeroste `CAP_BYTES`, zeštíhluje se od konce
seznamu (nejvzdálenější a nejstarší první); teprve potom se celé položky přesunou do `omitted`.
Co se proti úrovni 0 zkrátí nebo vypustí, je v `trimmed`/`omitted` s ukazatelem `full`, odkud si to
agent dočte celé. Stejný vstup dá vždy stejné bajty.
"""
import json

CAP_BYTES = 8192
VERSION = 1
ALL = 10**9  # úroveň 0: bez limitu
START, LAST = 1, 4
# Limity po úrovních 0–4 (None = pole se vynechá).
SUMMARY = (ALL, 800, 400, 200, 120)
NOTES = (ALL, 160, 60, None, None)
EVIDENCE_ITEMS = (ALL, 3, 0, 0, 0)
DECISIONS = (ALL, 8, 5, 3, 0)
DECISION_TEXT = (ALL, 240, 240, 120, None)
DECISION_DETAIL = (True, True, False, False, False)
CHECKS = (ALL, 6, 6, 0, 0)
CHECK_SUMMARY = (ALL, 80, None, None, None)
REPORT = (ALL, 400, 240, 120, None)
FLOW_SUMMARY = (ALL, 240, None, None, None)
LENS_DETAIL = (True, True, True, True, False)


def size(value):
    """Bajty tak, jak je posílá API (kompaktní JSON v UTF-8)."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def clip(text, limit):
    flat = " ".join(str(text or "").split())
    if not flat or limit is None:
        return None
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _decision(item, level):
    if isinstance(item, str):
        return clip(item, DECISION_TEXT[level])
    if not isinstance(item, dict):
        return None
    text = clip(item.get("text"), DECISION_TEXT[level])
    if not DECISION_DETAIL[level] or text is None:
        return text
    shaped = {"text": text}
    if item.get("why"):
        shaped["why"] = clip(item["why"], DECISION_TEXT[level])
    for key in ("alternatives", "evidence"):
        values = [clip(value, 120 if level else ALL) for value in (item.get(key) or [])[:EVIDENCE_ITEMS[level]]
                  if isinstance(value, str)]
        if values:
            shaped[key] = values
    for key in ("scope", "agent"):
        if isinstance(item.get(key), str):
            shaped[key] = clip(item[key], 80 if level else ALL)
    return shaped


def _step(item, level):
    step = {"id": item["stepId"], "status": item["status"]}
    evidence = item.get("evidence") or {}
    short = {"notes": clip(evidence.get("notes"), NOTES[level]),
             "checks": [clip(value, 80 if level else ALL) for value in (evidence.get("checks") or [])[:EVIDENCE_ITEMS[level]]],
             "commits": [value[:12] if level else value for value in (evidence.get("commits") or [])[:EVIDENCE_ITEMS[level]]]}
    short = {key: value for key, value in short.items() if value}
    if short:
        step["evidence"] = short
    return step


def _drop_empty(shaped):
    return {key: value for key, value in shaped.items() if value not in (None, [], {})}


def card(entry, level):
    """Položka předchůdce na úrovni 0–4."""
    result = entry.get("result") or {}
    shaped = {"cardId": entry["cardId"], "title": entry["title"], "executionId": entry.get("executionId"),
              "resultStatus": entry["resultStatus"], "summary": clip(result.get("summary"), SUMMARY[level])}
    steps = result.get("stepResults") or []
    if level < LAST:
        shaped["stepResults"] = [_step(item, level) for item in steps]
    elif steps:
        shaped["steps"] = {"done": sum(item["status"] == "done" for item in steps), "total": len(steps)}
    shaped["checks"] = [_drop_empty({"name": item.get("name"), "status": item.get("status"),
                                     "summary": clip(item.get("summary"), CHECK_SUMMARY[level])})
                        for item in (result.get("checks") or [])[:CHECKS[level]]]
    shaped["decisions"] = [value for value in (_decision(item, level) for item in entry.get("decisions", [])[:DECISIONS[level]])
                           if value]
    shaped["pr"] = entry.get("pr")
    lens = entry["lens"]
    shaped["lens"] = {"endpoint": lens["endpoint"], "stored": lens["stored"],
                      **({key: lens[key] for key in ("title", "url", "current") if lens.get(key) is not None}
                         if LENS_DETAIL[level] else {})}
    report = entry.get("edgeReport") or {}
    shaped["edgeReport"] = clip(report.get("handoff"), REPORT[level]) or clip(report.get("summary"), REPORT[level])
    return _drop_empty(shaped)


def flow(entry, level):
    """Zpráva toku `flow`, který vede do oblasti karty (jen pro první kartu oblasti)."""
    return _drop_empty({"edgeId": entry["edgeId"], "fromArea": entry["fromArea"],
                        "handoff": clip(entry.get("handoff"), REPORT[level]),
                        "summary": clip(entry.get("summary"), FLOW_SUMMARY[level]),
                        "sentAt": entry.get("sentAt")})


def _shape(entry, level):
    return (card if "cardId" in entry else flow)(entry, level)


def _key(entry):
    return entry.get("cardId") or entry["edgeId"]


def _omitted(entry):
    """Vynechaná položka: jen id a druh; cestu k datům dává šablona ve `fullParams`."""
    return {"id": _key(entry), "kind": "card" if "cardId" in entry else "flow"}


def _cost(sizes):
    return sum(sizes) + max(len(sizes) - 1, 0)  # položky seznamu + čárky (kompaktní JSON)


def build(cards, flows, full_params):
    """`assignment.handoff`: deterministický balíček do `CAP_BYTES` (včetně vlastních metadat).

    Zeštíhluje se po kolech: v každém kole dostanou položky od konce seznamu o úroveň méně textu,
    dokud se balíček nevejde; po posledním kole se celé položky od konce přesouvají do `omitted`."""
    entries = [*cards, *flows]
    whole = [_shape(entry, 0) for entry in entries]
    cache = {}

    def at(index, level):
        """(tvar, záznam trimmed nebo None, jejich bajty) položky na úrovni; počítá se jednou."""
        if (index, level) not in cache:
            item = _shape(entries[index], level)
            fields = sorted(key for key in whole[index] if whole[index][key] != item.get(key))
            note = {"id": _key(entries[index]), "fields": fields, "full": entries[index]["full"]} if fields else None
            cache[index, level] = (item, note, size(item), size(note) if note else None)
        return cache[index, level]

    def assemble(levels, kept, exact=False):
        rows = [at(index, levels[index]) for index in range(kept)]
        lists = {"predecessors": [row for index, row in enumerate(rows) if "cardId" in entries[index]],
                 "areaFlows": [row for index, row in enumerate(rows) if "edgeId" in entries[index]],
                 "trimmed": [row for row in rows if row[1]]}
        omitted = [_omitted(entry) for entry in entries[kept:]]
        value = {"version": VERSION, "capBytes": CAP_BYTES, "fullParams": full_params,
                 "predecessors": [row[0] for row in lists["predecessors"]], "areaFlows": [row[0] for row in lists["areaFlows"]],
                 "trimmed": [row[1] for row in lists["trimmed"]], "omitted": omitted}
        if exact:
            return measured(value)
        skeleton = size({**value, "predecessors": [], "areaFlows": [], "trimmed": [], "bytes": 10**6})
        return skeleton + _cost([row[2] for row in lists["predecessors"]]) + _cost([row[2] for row in lists["areaFlows"]])             + _cost([row[3] for row in lists["trimmed"]])

    levels, kept = [START] * len(entries), len(entries)
    for target in range(START + 1, LAST + 1):  # kola zeštíhlení, vždy od konce
        for index in reversed(range(len(entries))):
            if assemble(levels, kept) <= CAP_BYTES:
                break
            levels[index] = max(levels[index], target)
    while kept and assemble(levels, kept) > CAP_BYTES:  # celé položky do omitted, od konce
        kept -= 1
    value = assemble(levels, kept, exact=True)
    omitted = value["omitted"]
    while value["bytes"] > CAP_BYTES and omitted:  # krajní případ (stovky předchůdců): zbytek jen počtem,
        omitted = omitted[:-1]                     # cestu dávají vazby `next` v grafu
        value = measured({**value, "omitted": omitted, "omittedMore": len(entries) - kept - len(omitted)})
    return value


def measured(value):
    """Doplní `bytes`; číslo je samo součástí balíčku, proto se ustálí opakováním."""
    value = {**value, "bytes": 0}
    for _ in range(3):
        value["bytes"] = size(value)
    return value

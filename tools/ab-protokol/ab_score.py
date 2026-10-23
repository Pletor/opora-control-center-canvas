"""Hodnoticí rubrika (definovaná předem) a výpočet skóre z naměřených dat obou variant."""
from __future__ import annotations

import json
from collections import Counter

from ab_meter import markers

# Váhy kritérií; součet 100. Pořadí = pořadí v tabulce výsledků.
RUBRIC = [
    ("K1", "Předání kontextu další kartě", 25,
     "podíl značek předchozí karty (rozhodnutí, předávka, výsledky kroků, kontroly, PR, Lens), které agent další karty najde v tom, co v kroku kontext skutečně přečte"),
    ("K2", "Co člověk vidí a ověří", 20,
     ("podíl 8 ověřitelných faktů v lidském pohledu (stav po krocích, commit u kroku strojově, kontroly vázané na commit, "
      "PR se sledovaným stavem, Lens, oddělení tvrzení od ověření, živý průběh, dohledatelné rozhodnutí)")),
    ("K3", "Odolnost proti poruchám", 20,
     "podíl bezpečně zvládnutých poruch (souběh claimu, zápis bez oprávnění, změna zadání během práce, pád agenta, opakované odeslání)"),
    ("K4", "Náklad agenta", 10, "7 b. bajty, které agenti (vykonavatel, recenzent, office) přečtou na kartu + 3 b. počet jejich volání; lepší varianta plný počet, horší poměrem"),
    ("K5", "Náklad člověka", 5, "počet lidských volání na kartu (bez založení dat); lepší plný počet, horší poměrem"),
    ("K6", "% hotovo ve třech úrovních", 10,
     "jde každou úroveň (agent tvrdí / kód existuje / potvrzeno člověkem) spočítat ze strukturovaných dat? strukturovaně 1, jen z volného textu 0,5"),
    ("K7", "PR a PR Lens", 10, "5 b. PR připojený strukturovaně se stavem z GitHubu, 5 b. Lens skutečně uložený u karty"),
]
FACTS = ["stav po krocích", "commit u kroku strojově", "kontroly vázané na commit", "PR se sledovaným stavem",
         "Lens u karty", "tvrzení odděleno od ověření", "živý průběh během práce", "rozhodnutí dohledatelné ke kartě"]


def transfer(sim):
    """Pro každou dvojici (karta k → k+1): které značky karty k agent k+1 přečetl v kroku kontext."""
    cards = sim.fix["cards"]
    rows = []
    for k in range(len(cards) - 1):
        text = sim.meter.read_text(cards[k + 1]["id"], "kontext")
        mark = markers(k)
        commits = sim.outcome.get(cards[k]["id"], {}).get("commits", [])
        found = {
            "rozhodnutí": mark["decision"] in text,
            "předávka": mark["handoff"] in text,
            "výsledky kroků": mark["step"] in text or any(c in text for c in commits),
            "kontroly": mark["check"] in text,
            "PR": mark["pr"] in text or f"\"number\": {100 + k}" in text or f"\"number\":{100 + k}" in text,
            "Lens": mark["lens"] in text,
        }
        rows.append({"from": k, "to": k + 1, "found": found, "score": sum(found.values()) / len(found)})
    return rows


def cost(sim):
    # Bez založení dat a bez měřicích čtení harnessu; plán (návrh a přijetí kroků) se počítá.
    calls = [c for c in sim.meter.calls if (c.card != "setup" or c.phase == "plan") and c.phase not in ("mereni", "porucha")]
    by_actor = Counter(c.actor for c in calls)
    agentish = [c for c in calls if c.actor in ("agent", "planner", "reviewer", "office")]
    context = [c for c in calls if c.actor == "agent" and c.phase == "kontext"]
    n = len(sim.fix["cards"])
    briefs = sum(1 for c in calls if c.actor in ("agent", "reviewer") and c.path.endswith("/node-brief"))
    return {
        "calls": len(calls), "byActor": dict(by_actor),
        "agentCalls": len(agentish), "agentCallsPerCard": round(len(agentish) / n, 1),
        "agentReadBytes": sum(c.response_bytes for c in agentish),
        "agentReadBytesPerCard": round(sum(c.response_bytes for c in agentish) / n),
        "topReads": _top(agentish),
        "contextBytesPerCard": round(sum(c.response_bytes for c in context) / n),
        "agentWriteBytes": sum(c.request_bytes for c in agentish),
        "humanCallsPerCard": round(by_actor.get("human", 0) / n, 1),
        "nodeBriefReads": briefs,
        "errors": [f"{c.method} {c.path} {c.status}" for c in calls if c.status >= 400],
    }


def _top(calls, limit=6):
    total = Counter()
    count = Counter()
    for c in calls:
        key = f"{c.method} {c.path}"
        total[key] += c.response_bytes
        count[key] += 1
    return [f"{key} ×{count[key]}: {size} B" for key, size in total.most_common(limit)]


def live_extrapolation(sim, fix):
    """Kolik by agent četl na živých datech ample: počet čtení node-brief × skutečná velikost briefu karty."""
    sizes = {k: v["nodeBriefBytes"] for k, v in fix["live"].items()}
    total = 0
    for c in sim.meter.calls:
        if c.path.endswith("/node-brief") and c.actor in ("agent", "reviewer") and c.card in sizes:
            total += sizes[c.card]
    return total


def ratio(mine, other, lower_is_better=True):
    if mine == other:
        return 1.0
    best = min(mine, other) if lower_is_better else max(mine, other)
    return best / mine if lower_is_better else mine / best


def score(results):
    """`results[opt]` = {transfer, cost, facts, scenarios, levels, pr} → body podle rubriky."""
    out = {}
    a, b = results["A"], results["B"]
    for opt, me, other in (("A", a, b), ("B", b, a)):
        k1 = sum(r["score"] for r in me["transfer"]) / max(len(me["transfer"]), 1)
        k2 = sum(1 for v in me["facts"].values() if v) / len(FACTS)
        weights = {True: 1.0, "partial": 0.5, False: 0.0}
        k3 = sum(weights[s["safe"]] for s in me["scenarios"]) / len(me["scenarios"])
        k4 = (7 * ratio(me["cost"]["agentReadBytesPerCard"], other["cost"]["agentReadBytesPerCard"])
              + 3 * ratio(me["cost"]["agentCallsPerCard"], other["cost"]["agentCallsPerCard"])) / 10
        k5 = ratio(me["cost"]["humanCallsPerCard"], other["cost"]["humanCallsPerCard"])
        k6 = sum(me["levels"].values()) / 3
        k7 = (0.5 if me["pr"]["structured"] else 0) + (0.5 if me["pr"]["lens"] else 0)
        parts = dict(zip([r[0] for r in RUBRIC], (k1, k2, k3, k4, k5, k6, k7)))
        points = {key: round(parts[key] * weight, 1) for key, _, weight, _ in RUBRIC}
        out[opt] = {"parts": parts, "points": points, "total": round(sum(points.values()), 1)}
    return out


def table(results, scores):
    lines = ["| Kritérium | Váha | A: starý protokol | B: OporaHub v2 |", "|---|---:|---:|---:|"]
    for key, name, weight, _ in RUBRIC:
        lines.append(f"| {key} {name} | {weight} | {scores['A']['points'][key]} | {scores['B']['points'][key]} |")
    lines.append(f"| **Celkem** | **100** | **{scores['A']['total']}** | **{scores['B']['total']}** |")
    return "\n".join(lines)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=1, default=str)

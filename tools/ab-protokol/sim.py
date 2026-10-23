"""A/B simulace protokolu agentů OPORA: starý protokol (A) proti OporaHubu v2 (B).

Spuštění z kořene repozitáře:  uv run python tools/ab-protokol/sim.py [--json výsledky.json]

Obě varianty běží proti skutečnému backendu (`create_app`) na dočasné datové složce se třemi
kartami zkopírovanými z projektu ample (fixtures/ample-3-karty.json). Agenti jsou skriptovaní,
deterministicky, bez volání modelu. Nic se nezapisuje do živé aplikace ani do P:/opora-data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ab_meter import final_cleanup, fixture, isolated_env, markers, sweep_previous
from ab_score import (
    FACTS,
    RUBRIC,
    cost,
    dump,
    live_extrapolation,
    score,
    table,
    transfer,
)


def legacy_facts(sim, scenarios):
    from ab_legacy import SCOPE

    card = sim.fix["cards"][0]
    state = sim.meter.where(card["id"], "mereni").call("human", "GET", "/api/desktop-v3/state", params=SCOPE).json()["state"]
    node = state["nodes"][card["id"]]
    evidence = node.get("evidence") or {}
    merge = evidence.get("merge") or {}
    checks = evidence.get("checksRun") or []
    decision = next((d for d in state["decisions"] if markers(0)["decision"] in d["text"]), None)
    crash = next(s for s in scenarios if s["name"].startswith("pád"))
    values = [
        all(b["state"]["status"] == "met" for b in node["blocks"]),
        any("commits" in b or "commit" in b["state"] for b in node["blocks"]),
        any("headSha" in c or "commit" in c for c in checks),
        any(key in merge for key in ("mergeSha", "observedAt", "bindingId")),
        "lens" in node or "lens" in evidence,
        any(key in merge for key in ("observedAt", "observedBy", "verifiedBy")),
        crash["safe"] is True,
        bool(decision) and decision.get("nodeId") == card["id"],
    ]
    return dict(zip(FACTS, values))


def hub_facts(sim, scenarios):
    card = sim.fix["cards"][0]
    m, s = sim.meter.where(card["id"], "mereni"), sim.scope
    state = m.call("human", "GET", "/api/oporahub/agent-state", params=s).json()
    entry = next(c for c in state["cards"] if c["nodeId"] == card["id"])
    execution = sim.executions[card["id"]]
    results = m.call("human", "GET", f"/api/oporahub/executions/{execution}/results", params=s).json()
    result = (results.get("results") or [{}])[0].get("result") or {}
    link = m.call("human", "GET", f"/api/oporahub/executions/{execution}/pull-request", params=s,
                  headers={"X-Opora-Actor": "agent; name=sim-reviewer"}, expect=None)
    lens = m.call("reviewer", "GET", "/api/oporahub/review-lens", params={**s, "nodeId": card["id"]}).json()
    desk = m.call("human", "GET", "/api/desktop-v3/state", params=s).json()["state"]
    crash = next(x for x in scenarios if x["name"].startswith("pád"))
    head = sim.outcome[card["id"]]["commits"][-1]
    values = [
        all(i["status"] == "done" for i in (entry.get("steps") or {}).get("items", [])),
        all(sr.get("evidence", {}).get("commits") for sr in result.get("stepResults", [])) and bool(result.get("stepResults")),
        (result.get("selfChecks") or {}).get("headSha") == head,
        link.status_code == 200 and link.json().get("state") == "merged",
        head in json.dumps(lens),
        {"steps", "merged", "human_close"} <= set(entry.get("dod") or {}),
        crash["safe"] is True,
        any(markers(0)["decision"] in d["text"] for d in desk["decisions"]),
    ]
    return dict(zip(FACTS, values))


def levels_score(level_rows):
    """K6: každá úroveň 1 (strukturovaně), 0,5 (jen volný text), 0 (nejde spočítat)."""
    code = 1.0 if "strukturované" in level_rows[0]["codeSource"] else 0.5
    return {"agent tvrdí": 1.0, "kód existuje": code, "potvrzeno člověkem": 1.0}


def run():
    import ab_scenarios
    from ab_hub import Hub
    from ab_legacy import Legacy

    fix = fixture()
    scenarios = ab_scenarios.run_all()
    out = {}
    for name, cls in (("A", Legacy), ("B", Hub)):
        sim = cls(fix=fix)
        try:
            sim.run()
            cards = fix["cards"]
            level_rows = [sim.levels(c) for c in cards]
            facts = legacy_facts(sim, scenarios["A"]) if name == "A" else hub_facts(sim, scenarios["B"])
            first = sim.outcome[cards[0]["id"]]
            out[name] = {
                "outcome": sim.outcome, "transfer": transfer(sim), "cost": cost(sim), "facts": facts,
                "scenarios": scenarios[name], "levelRows": level_rows, "levels": levels_score(level_rows),
                "pr": {"structured": name == "B" and first.get("pr") == 200, "lens": facts["Lens u karty"],
                       "lensStatus": first.get("lens"), "lensDetail": first.get("lensDetail", "")},
                "liveNodeBriefBytes": live_extrapolation(sim, fix),
            }
        finally:
            sim.close()
    plus = Hub(fix=fix, predecessors=True)
    try:
        plus.run()
        out["B+"] = {"transfer": transfer(plus), "cost": cost(plus)}
    finally:
        plus.close()
    return out, score(out)


def report(results, scores):
    a, b = results["A"], results["B"]
    lines = ["# A/B protokol agentů — výsledky simulace", "", table(results, scores), "",
             "## Náklad", "", "| Metrika | A | B |", "|---|---:|---:|"]
    for key, label in (("agentCallsPerCard", "volání agentů / karta"), ("agentReadBytesPerCard", "bajty přečtené agenty / karta"),
                       ("contextBytesPerCard", "z toho krok kontext / karta"),
                       ("agentReadBytes", "bajty přečtené agenty celkem"), ("agentWriteBytes", "bajty zapsané agenty"),
                       ("humanCallsPerCard", "lidská volání / karta"), ("nodeBriefReads", "čtení node-brief")):
        lines.append(f"| {label} | {a['cost'][key]} | {b['cost'][key]} |")
    lines.append(f"| node-brief na živých datech ample (čtení × skutečná velikost) | {a['liveNodeBriefBytes']} | {b['liveNodeBriefBytes']} |")
    lines += ["", "Největší čtení agentů:", ""]
    for opt in ("A", "B"):
        lines.append(f"- {opt}: " + "; ".join(results[opt]["cost"]["topReads"]))
    lines += ["", "## Předání kontextu (karta k → k+1)", "", "| Varianta | Přechod | Nalezeno |", "|---|---|---|"]
    for opt in ("A", "B"):
        for row in results[opt]["transfer"]:
            got = ", ".join(f"{k} {'ano' if v else 'ne'}" for k, v in row["found"].items())
            lines.append(f"| {opt} | {row['from']}→{row['to']} | {got} |")
    for row in results["B+"]["transfer"]:
        got = ", ".join(f"{k} {'ano' if v else 'ne'}" for k, v in row["found"].items())
        lines.append(f"| B+ (agent dočte předchůdce) | {row['from']}→{row['to']} | {got} |")
    plus = results["B+"]["cost"]
    note = (f"B+ stojí {plus['agentCallsPerCard']} volání agentů / kartu a {plus['agentReadBytesPerCard']} B / kartu "
            f"(B: {b['cost']['agentCallsPerCard']} a {b['cost']['agentReadBytesPerCard']} B). Do skóre nevstupuje, "
            "je to důkaz pro cílový návrh.")
    lines += ["", note, "", "## Co člověk vidí", "", "| Fakt | A | B |", "|---|---|---|"]
    for fact in FACTS:
        lines.append(f"| {fact} | {'ano' if a['facts'][fact] else 'ne'} | {'ano' if b['facts'][fact] else 'ne'} |")
    lines += ["", "## Poruchy", "", "| Varianta | Porucha | Bezpečné | Detail |", "|---|---|---|---|"]
    for opt in ("A", "B"):
        for s in results[opt]["scenarios"]:
            lines.append(f"| {opt} | {s['name']} | {s['safe']} | {s['detail']} |")
    lines += ["", "## Rubrika", ""] + [f"- **{k} {n}** ({w}): {d}" for k, n, w, d in RUBRIC]
    winner = "A" if scores["A"]["total"] > scores["B"]["total"] else "B"
    lines += ["", f"**Vítěz podle rubriky: {winner}** ({scores[winner]['total']} : {scores['B' if winner == 'A' else 'A']['total']})"]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="kam uložit úplná naměřená data")
    args = parser.parse_args(argv)
    sweep_previous()
    with isolated_env():
        try:
            results, scores = run()
        finally:
            final_cleanup()
    if args.json:
        Path(args.json).write_text(dump({"results": results, "scores": scores}), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report(results, scores))
    return results, scores


if __name__ == "__main__":
    main()

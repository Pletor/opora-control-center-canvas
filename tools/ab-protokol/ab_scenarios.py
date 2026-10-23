"""Poruchové scénáře: souběh, změna zadání během práce, pád agenta, opakované odeslání.

Každý scénář běží na vlastní čerstvé dočasné instanci. Výsledek je `{name, safe, detail}`:
`safe` = protokol zachoval data a nedovolil tichý chybný zápis.
"""
from __future__ import annotations

from ab_hub import Hub
from ab_legacy import SCOPE, Legacy


def _status(response):
    return response.status_code


# --- A ---------------------------------------------------------------------------------------------
def legacy_concurrency():
    sim = Legacy()
    try:
        card = sim.fix["cards"][0]
        sim.context(0, card)
        m = sim.meter.where(card["id"], "porucha")
        second = m.call("agent2", "POST", "/api/desktop-v3/lease", expect=None,
                        body={**SCOPE, "nodeId": card["id"], "op": "claim", "owner": "sim-worker-2", "ttlSeconds": 900})
        space = m.call("agent2", "GET", "/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": card["id"]}).json()
        overwrite = m.call("agent2", "POST", "/api/desktop-v3/agent-workspace", expect=None, body={
            **SCOPE, "nodeId": card["id"], "expectedRevision": space["revision"], "by": "agent",
            "sections": {"handoff": "cizí agent bez lease přepsal předávku"}})
        return [
            {"name": "souběh: druhý claim téže karty", "safe": _status(second) == 409, "detail": f"lease → {_status(second)}"},
            {"name": "souběh: zápis předávky bez oprávnění", "safe": _status(overwrite) != 200,
             "detail": f"agent-workspace bez lease → {_status(overwrite)} (prostor agenta lease nehlídá)"},
        ]
    finally:
        sim.close()


def legacy_stale_spec():
    sim = Legacy()
    try:
        card = sim.fix["cards"][0]
        ctx = sim.context(0, card)
        todos = sim.plan(0, card, ctx)
        brief = sim.meter.call("agent", "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]}).json()
        ctx["contextVersion"] = brief["outputContract"]["request"]["contextVersion"]
        sim.work(0, card, ctx, todos, stop_after=1)
        m = sim.meter.where(card["id"], "porucha")
        spec = m.call("human", "GET", "/api/node-spec", params={**SCOPE, "node": card["id"]}).json()
        m.call("human", "POST", "/api/node-spec", body={**SCOPE, "node": card["id"], "expected_revision": spec["revision"],
                                                        "fields": {**spec["fields"], "goal": spec["fields"]["goal"] + " ZMĚNA"}})
        sim._state()
        output = {"schema": "opora.agent-output/1", "blocks": [], "reports": [], "done": {"proposed": False, "note": ""},
                  "decisions": []}
        response = m.call("agent", "POST", "/api/desktop-v3/agent-output", expect=None, headers={"X-Opora-Lease": ctx["token"]},
                          body={**SCOPE, "nodeId": card["id"], "expectedRevision": sim.revision,
                                "contextVersion": ctx["contextVersion"], "agent": "sim-worker", "output": output})
        state = sim._state("human")["state"]["nodes"][card["id"]]
        kept = sum(1 for b in state["blocks"] if b["state"]["status"] == "met")
        return [{"name": "změna zadání během práce", "safe": _status(response) == 409,
                 "detail": f"agent-output se starým otiskem → {_status(response)}; hotové bloky v kartě zůstaly: {kept} "
                           "(ale byly hlášené proti starému zadání a nikdo je neoznačí)"}]
    finally:
        sim.close()


def legacy_crash():
    from backend.editor.agent_memory import card_leases

    sim = Legacy()
    real = card_leases.time.time
    try:
        card = sim.fix["cards"][1]
        first = sim.fix["cards"][0]
        sim.run(crash_card=1, crash_after=2)
        offset = [0.0]
        card_leases.time.time = lambda: real() + offset[0]
        offset[0] = 1000.0  # lease (900 s) vypršel
        m = sim.meter.where(card["id"], "porucha")
        again = m.call("agent2", "POST", "/api/desktop-v3/lease", expect=None,
                       body={**SCOPE, "nodeId": card["id"], "op": "claim", "owner": "sim-worker-2", "ttlSeconds": 900})
        brief = m.call("agent2", "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]}).json()
        met = [b["number"] for b in brief["blocks"] if b["state"]["status"] == "met"]
        seen_log = "KROK-1-2" in (brief.get("agentWorkspace") or {}).get("log", "")
        return [{"name": "pád agenta po 2 z 4 kroků", "safe": _status(again) == 200 and len(met) == 2 and seen_log,
                 "detail": f"nový lease → {_status(again)}; nový agent vidí hotové bloky {met} a log kroků: {seen_log}; "
                           f"první karta potvrzena: {sim.outcome.get(first['id'], {}).get('accepted')}"}]
    finally:
        card_leases.time.time = real
        sim.close()


def legacy_replay():
    sim = Legacy()
    try:
        card = sim.fix["cards"][0]
        ctx = sim.context(0, card)
        m = sim.meter.where(card["id"], "porucha")
        output = {"schema": "opora.agent-output/1", "blocks": [], "reports": [], "done": {"proposed": False, "note": ""},
                  "decisions": ["ROZHODNUTI-replay"]}
        body = {**SCOPE, "nodeId": card["id"], "expectedRevision": sim.revision, "contextVersion": ctx["contextVersion"],
                "agent": "sim-worker", "output": output}
        first = m.call("agent", "POST", "/api/desktop-v3/agent-output", body=body, headers={"X-Opora-Lease": ctx["token"]}, expect=None)
        second = m.call("agent", "POST", "/api/desktop-v3/agent-output", body=body, headers={"X-Opora-Lease": ctx["token"]}, expect=None)
        decisions = [d for d in sim._state("human")["state"]["decisions"] if "ROZHODNUTI-replay" in d["text"]]
        return [{"name": "opakované odeslání výsledku", "safe": ("partial" if _status(second) == 409 else True) if len(decisions) == 1 else False,
                 "detail": f"1. → {_status(first)}, 2. → {_status(second)} (bez idempotence: agent nepozná, "
                           f"zda první prošel); rozhodnutí uloženo {len(decisions)}×"}]
    finally:
        sim.close()


# --- B ---------------------------------------------------------------------------------------------
def hub_concurrency():
    sim = Hub()
    try:
        sim.plan()
        card = sim.fix["cards"][0]
        ctx = sim.context(0, card)
        m = sim.meter.where(card["id"], "porucha")
        second = sim.context(0, card, actor="agent2")
        legacy = m.call("agent2", "POST", "/api/desktop-v3/agent-output", expect=None, body={
            **sim.scope, "nodeId": card["id"], "expectedRevision": 0, "agent": "sim-worker-2",
            "output": {"schema": "opora.agent-output/1", "blocks": [], "reports": [], "done": {"proposed": True, "note": ""},
                       "decisions": []}})
        return [
            {"name": "souběh: druhý claim téže karty", "safe": "refused" in second,
             "detail": f"druhý claim → {second.get('refused')} (první běh {ctx['record']['executionId'][:8]})"},
            {"name": "souběh: zápis předávky bez oprávnění", "safe": _status(legacy) != 200,
             "detail": f"starý agent-output na kartu v běhu → {_status(legacy)}"},
        ]
    finally:
        sim.close()


def hub_stale_spec():
    sim = Hub()
    try:
        sim.plan()
        card = sim.fix["cards"][0]
        ctx = sim.context(0, card)
        commits, _ = sim.work(0, card, ctx, stop_after=1)
        m, s = sim.meter.where(card["id"], "porucha"), sim.scope
        context = m.call("human", "GET", "/api/oporahub/changesets/context", params=s).json()
        doc = next(d for d in context["documents"] if d["nodeId"] == card["id"])
        steps = [dict(step) for step in doc["fields"]["steps"]]
        steps[1]["title"] = steps[1]["title"] + " ZMĚNA"
        proposal = m.call("human", "POST", "/api/oporahub/changesets", body={
            **s, "subject": "Změna kroku s2", "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "changes": [{"nodeId": card["id"], "expectedRevision": doc["revision"], "fields": {**doc["fields"], "steps": steps}}]}).json()
        m.call("human", "POST", f"/api/oporahub/changesets/{proposal['id']}/accept", body={**s, "expectedAcceptedHead": context["acceptedHead"]})
        record = ctx["record"]
        beat = m.call("agent", "POST", f"/api/oporahub/executions/{record['executionId']}/heartbeat", expect=None,
                      body={**s, "token": record["token"], "epoch": record["epoch"], "ttlSeconds": 900})
        result = sim.report(0, card, ctx, commits)
        return [{"name": "změna zadání během práce", "safe": _status(beat) == 409 and _status(result) == 409,
                 "detail": f"heartbeat → {_status(beat)}, výsledek → {_status(result)}; krok s1 (nezměněný) se po novém "
                           "claimu musí nahlásit znovu, s2 začíná znovu"}]
    finally:
        sim.close()


def hub_crash():
    sim = Hub()
    try:
        sim.run(crash_card=1, crash_after=2)
        card = sim.fix["cards"][1]
        m = sim.meter.where(card["id"], "porucha")
        state = m.call("human", "GET", "/api/oporahub/agent-state", params=sim.scope).json()
        entry = next(c for c in state["cards"] if c["nodeId"] == card["id"])
        second = sim.context(1, card, actor="agent2")
        done = (entry.get("steps") or {}).get("done", 0)
        return [{"name": "pád agenta po 2 z 4 kroků", "safe": done == 2,
                 "detail": f"Canvas vidí hotových kroků: {done}/4 (2 commity existují jen ve větvi); karta drží "
                           f"běh do vypršení TTL, druhý claim → {second.get('refused', 'ok')}; po vypršení začíná od "
                           f"{(entry.get('steps') or {}).get('current')}"}]
    finally:
        sim.close()


def hub_replay():
    sim = Hub()
    try:
        sim.plan()
        card = sim.fix["cards"][0]
        ctx = sim.context(0, card)
        commits, _ = sim.work(0, card, ctx)
        first = sim.report(0, card, ctx, commits)
        second = sim.report(0, card, ctx, commits)
        return [{"name": "opakované odeslání výsledku", "safe": first.status_code == 200 and second.json() == first.json(),
                 "detail": f"1. → {first.status_code}, 2. → {second.status_code}, stejné potvrzení: {second.json() == first.json()}"}]
    finally:
        sim.close()


def run_all():
    out = {"A": [], "B": []}
    for fn in (legacy_concurrency, legacy_stale_spec, legacy_crash, legacy_replay):
        out["A"].extend(fn())
    for fn in (hub_concurrency, hub_stale_spec, hub_crash, hub_replay):
        out["B"].extend(fn())
    return out


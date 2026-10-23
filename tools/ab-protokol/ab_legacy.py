"""Varianta A: starý protokol, jak ho agenti používají dnes (lease, node-brief, block, agent-output).

Skriptovaný agent (bez LLM) projde každou kartu stejně jako skutečný agent podle
`.claude/skills/opora-control-center/references/legacy.md`: frontier → lease → node-brief →
kroky jako úkoly bloků → práce s commitem po kroku → stav bloku a prostor agenta po kroku →
`agent-output` → release → review → lidské potvrzení `done.confirmed`.
"""
from __future__ import annotations

import re

from ab_meter import Meter, Repo, block_id, cleanup, fixture, markers, new_app, seed, tmpdir

SCOPE = {"project": "draft", "workspace": "draft"}
SHA_IN_TEXT = re.compile(r"\b[0-9a-f]{40}\b")


class Legacy:
    option = "A"

    def __init__(self, root=None, fix=None):
        self.root = root or tmpdir("ab-legacy-")
        self.fix = fix or fixture()
        self.app, self.client = new_app(self.root / "data")
        self.meter = Meter(self.client, self.option)
        self.repo = Repo(self.root / "repo")
        self.revision = 0
        self.outcome = {}
        seed(self.meter, SCOPE, self.fix)

    def close(self):
        self.client.__exit__(None, None, None)
        self.app.state.service.close()
        cleanup(self.root)

    # --- pomocné ----------------------------------------------------------------------------------
    def _rev(self, response):
        value = response.json()
        self.revision = value.get("revision", self.revision)
        return value

    def _state(self, actor="agent"):
        return self._rev(self.meter.call(actor, "GET", "/api/desktop-v3/state", params=SCOPE))

    def _outgoing(self, card):
        return [edge for edge in self.fix["edges"] if edge["source"] == card["id"]]

    # --- tok jedné karty -------------------------------------------------------------------------
    def context(self, index, card, actor="agent"):
        m = self.meter.where(card["id"], "kontext")
        m.call(actor, "GET", "/api/desktop-v3/frontier", params=SCOPE)
        lease = m.call(actor, "POST", "/api/desktop-v3/lease", body={**SCOPE, "nodeId": card["id"], "op": "claim",
                                                                     "owner": "sim-worker", "ttlSeconds": 900}).json()
        brief = m.call(actor, "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]}).json()
        space = m.call(actor, "GET", "/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": card["id"]}).json()
        self.revision = brief["outputContract"]["request"]["expectedRevision"]
        return {"token": lease["token"], "brief": brief, "space": space["revision"],
                "contextVersion": brief["outputContract"]["request"]["contextVersion"]}

    def plan(self, index, card, ctx):
        """Kroky = bloky karty; agent si k nim zapíše úkoly `{id,text,assignee,done}` (nikdo je nepřijímá)."""
        m = self.meter.where(card["id"], "plan")
        lease = {"X-Opora-Lease": ctx["token"]}
        todos = {}
        for j, block in enumerate(card["blocks"]):
            body = {**SCOPE, "nodeId": card["id"], "expectedRevision": self.revision,
                    "op": {"kind": "todo", "blockId": block_id(card, j),
                           "todo": {"kind": "add", "text": f"{markers(index)['step']}{j + 1}: {block['title']}",
                                    "assignee": "sim-worker"}}}
            value = self._rev(m.call("agent", "POST", "/api/desktop-v3/block", body=body, headers=lease))
            todos[j] = value["block"]["todos"][-1]["id"]
        return todos

    def work(self, index, card, ctx, todos, stop_after=None):
        m = self.meter.where(card["id"], "prace")
        lease = {"X-Opora-Lease": ctx["token"]}
        commits, log = [], []
        for j, block in enumerate(card["blocks"]):
            if stop_after is not None and j >= stop_after:
                return commits, False
            step = f"s{j + 1}"
            commit = self.repo.commit(index, step, block["title"])
            commits.append(commit)
            note = f"{markers(index)['step']}{j + 1} hotovo, commit {commit}, {markers(index)['check']} passed"
            patch = {"state": {"status": "met", "condition": block["condition"], "onMet": {"kind": "none", "targetId": "", "note": ""},
                               "onUnmet": {"kind": "none", "targetId": "", "note": ""}, "note": note}}
            self._rev(m.call("agent", "POST", "/api/desktop-v3/block", headers=lease, body={
                **SCOPE, "nodeId": card["id"], "expectedRevision": self.revision,
                "op": {"kind": "update", "blockId": block_id(card, j), "patch": patch}}))
            self._rev(m.call("agent", "POST", "/api/desktop-v3/block", headers=lease, body={
                **SCOPE, "nodeId": card["id"], "expectedRevision": self.revision,
                "op": {"kind": "todo", "blockId": block_id(card, j), "todo": {"kind": "toggle", "id": todos[j]}}}))
            log.append(note)
            saved = m.call("agent", "POST", "/api/desktop-v3/agent-workspace", body={
                **SCOPE, "nodeId": card["id"], "expectedRevision": ctx["space"], "by": "agent",
                "sections": {"log": "\n".join(log)}}).json()
            ctx["space"] = saved["revision"]
            if j == 0:
                m.call("agent", "POST", "/api/desktop-v3/lease", body={**SCOPE, "nodeId": card["id"], "op": "heartbeat",
                                                                       "token": ctx["token"], "ttlSeconds": 900})
        return commits, True

    def report(self, index, card, ctx, commits):
        m = self.meter.where(card["id"], "hlaseni")
        mark = markers(index)
        output = {
            "schema": "opora.agent-output/1",
            "blocks": [{"blockId": block_id(card, j), "status": "met",
                        "note": f"{mark['step']}{j + 1}: commit {commits[j]}"} for j in range(len(card["blocks"]))],
            "reports": [{"edgeId": edge["id"], "log": "\n".join(f"{mark['step']}{j + 1} {c}" for j, c in enumerate(commits)),
                         "summary": f"Karta {index} hotová.", "handoff": f"{mark['handoff']}: naváž na rozhraní z kroku s1.",
                         "improvements": "", "errors": ""} for edge in self._outgoing(card)],
            "done": {"proposed": True, "note": f"Kroky hotové, {mark['check']} zelená, PR {mark['pr']}"},
            "decisions": [f"{mark['decision']}: originál se ukládá pod klíčem sha256."],
            "evidence": {"tests": {"status": "passed", "url": "", "note": f"{mark['check']}: uv run pytest -q"},
                         "review": {"status": "pending", "url": "", "note": ""},
                         "merge": {"status": "pending", "url": mark["pr"], "note": f"{mark['lens']} v popisu PR"},
                         "checksRun": [{"checkId": "unit", "command": "uv run pytest -q", "exitCode": 0, "logUrl": "",
                                        "at": "2026-10-23T10:00:00+00:00"}]},
            "touched": [f"src/card{index}_s{j + 1}.py" for j in range(len(commits))],
        }
        self._state()
        body = {**SCOPE, "nodeId": card["id"], "expectedRevision": self.revision, "contextVersion": ctx["contextVersion"],
                "agent": "sim-worker", "output": output}
        response = m.call("agent", "POST", "/api/desktop-v3/agent-output", body=body, headers={"X-Opora-Lease": ctx["token"]},
                          expect=None)
        if response.status_code == 409 and "contextVersion" in response.text:
            # Úkoly kroků zapsané v plánu změnily otisk zadání: agent musí znovu číst celý brief.
            self.outcome.setdefault("selfConflicts", []).append(card["id"])
            brief = m.call("agent", "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]}).json()
            body.update(expectedRevision=brief["outputContract"]["request"]["expectedRevision"],
                        contextVersion=brief["outputContract"]["request"]["contextVersion"])
            response = m.call("agent", "POST", "/api/desktop-v3/agent-output", body=body,
                              headers={"X-Opora-Lease": ctx["token"]}, expect=None)
        m.call("agent", "POST", "/api/desktop-v3/lease", body={**SCOPE, "nodeId": card["id"], "op": "release", "token": ctx["token"]})
        return response

    def review(self, index, card):
        """Starý protokol nemá kanál review mimo pipeline; recenzent čte výsledky a píše do prostoru agenta."""
        m = self.meter.where(card["id"], "review")
        m.call("reviewer", "GET", "/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": card["id"]})
        m.call("reviewer", "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]})
        space = m.call("reviewer", "GET", "/api/desktop-v3/agent-workspace", params={**SCOPE, "nodeId": card["id"]}).json()
        m.call("reviewer", "POST", "/api/desktop-v3/agent-workspace", body={
            **SCOPE, "nodeId": card["id"], "expectedRevision": space["revision"], "by": "agent",
            "sections": {"fixes": f"REVIEW karta {index}: bez blokátoru (neváže se na commit ani PR)."}})
        # Po merge doplní důkazy review a merge (opora_closure.py): nový lease, brief kvůli revizi, agent-output.
        mark = markers(index)
        lease = m.call("agent", "POST", "/api/desktop-v3/lease", body={**SCOPE, "nodeId": card["id"], "op": "claim",
                                                                       "owner": "sim-closure", "ttlSeconds": 300}).json()
        brief = m.call("agent", "GET", "/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": card["id"]}).json()
        request = brief["outputContract"]["request"]
        evidence = {"tests": {"status": "passed", "url": "", "note": f"{mark['check']}: uv run pytest -q"},
                    "review": {"status": "passed", "url": mark["pr"], "note": "review bez blokátoru"},
                    "merge": {"status": "passed", "url": mark["pr"], "note": "sloučeno"},
                    "checksRun": [{"checkId": "unit", "command": "uv run pytest -q", "exitCode": 0, "logUrl": "",
                                   "at": "2026-10-23T11:00:00+00:00"}]}
        closure = m.call("agent", "POST", "/api/desktop-v3/agent-output", headers={"X-Opora-Lease": lease["token"]}, expect=None,
                         body={**SCOPE, "nodeId": card["id"], "expectedRevision": request["expectedRevision"],
                               "contextVersion": request["contextVersion"], "agent": "sim-closure",
                               "output": {"schema": "opora.agent-output/1", "blocks": [], "reports": [],
                                          "done": {"proposed": True, "note": "Důkazy review a merge doplněny."},
                                          "decisions": [], "evidence": evidence}})
        m.call("agent", "POST", "/api/desktop-v3/lease", body={**SCOPE, "nodeId": card["id"], "op": "release",
                                                               "token": lease["token"]})
        return closure

    def accept(self, index, card):
        m = self.meter.where(card["id"], "prijeti")
        m.call("human", "GET", "/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": card["id"]})
        current = self._state("human")
        node = current["state"]["nodes"][card["id"]]
        node["done"] = {**node.get("done", {}), "confirmed": True, "by": "human", "at": "2026-10-23T12:00:00+00:00",
                        "note": "Přijato člověkem."}
        return m.call("human", "POST", "/api/desktop-v3/state", expect=None,
                      body={**SCOPE, "expectedRevision": current["revision"], "state": current["state"]})

    # --- měření ----------------------------------------------------------------------------------
    def levels(self, card):
        """% hotovo ve třech úrovních z toho, co protokol skutečně uložil."""
        state = self.meter.where(card["id"], "mereni").call("human", "GET", "/api/desktop-v3/state", params=SCOPE).json()
        node = state["state"]["nodes"][card["id"]]
        blocks = node.get("blocks", [])
        total = len(blocks) or 1
        claimed = sum(1 for b in blocks if b["state"]["status"] == "met")
        # kód existuje: SHA jen ve volném textu poznámky bloku → regex nad textem
        shas = [SHA_IN_TEXT.findall(b["state"].get("note", "") or "") for b in blocks]
        code = sum(1 for found in shas if found and all(self.repo.exists(s) for s in found))
        human = total if node.get("done", {}).get("confirmed") else 0
        return {"claimed": claimed / total, "code": code / total, "human": human / total, "perStepHuman": False,
                "codeSource": "regex ve volném textu block.state.note"}

    def run(self, crash_card=None, crash_after=None):
        for index, card in enumerate(self.fix["cards"]):
            ctx = self.context(index, card)
            todos = self.plan(index, card, ctx)
            commits, finished = self.work(index, card, ctx, todos,
                                          stop_after=crash_after if crash_card == index else None)
            if not finished:
                self.outcome[card["id"]] = {"crashed": True, "commits": commits}
                return self
            reported = self.report(index, card, ctx, commits)
            closure = self.review(index, card)
            accepted = self.accept(index, card)
            self.outcome[card["id"]] = {"reported": reported.status_code, "closure": closure.status_code,
                                        "closureDetail": closure.text[:300] if closure.status_code != 200 else "",
                                        "accepted": accepted.status_code,
                                        "acceptedDetail": accepted.text[:300] if accepted.status_code != 200 else "",
                                        "commits": commits, "lastCommit": commits[-1]}
        return self


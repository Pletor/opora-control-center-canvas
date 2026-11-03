"""Varianta B: OporaHub v2 (přijaté zadání s kroky, executions, stepResults, PR, Lens, agent-state).

Skriptovaný agent (bez LLM) jde podle `backend/brain/seed/opora-control-center/skills/opora-control-center/references/hub-loop.md`
a podle toho, co dělá agent-office (`src/server/opora/execution-*.ts`, `pull-request-handoff.ts`,
`pr-lens.ts`). GitHub je jediná simulovaná část: čtení PR je nahrazené deterministickou odpovědí
a sloučení PR je zapsané jako pozorování rekonciliace, stejně jako v backendových testech.
"""
from __future__ import annotations

from ab_github import REPOSITORY, FakeGitHub, managed_project, merged
from ab_meter import Meter, Repo, cleanup, fixture, markers, new_app, seed, tmpdir


def _steps(card):
    steps = []
    for j, block in enumerate(card["blocks"]):
        steps.append({"id": f"s{j + 1}", "order": j + 1, "title": block["title"][:200],
                      "acceptance": [(block["condition"] or block["title"])[:1000]],
                      "dependsOn": [f"s{j}"] if j else [], "kind": "code"})
    return steps


class Hub:
    option = "B"

    def __init__(self, root=None, fix=None, predecessors=False):
        self.predecessors = predecessors
        self.root = root or tmpdir("ab-hub-")
        self.fix = fix or fixture()
        self.repo = Repo(self.root / "upstream")
        self.scope = managed_project(self.root, self.repo, self.fix["cards"][0]["id"])
        self.app, self.client = new_app(self.root / "data")
        self.service = self.app.state.service
        self.meter = Meter(self.client, self.option)
        self.restore = FakeGitHub.install()
        self.outcome = {}
        self.executions = {}
        seed(self.meter, self.scope, self.fix)

    def close(self):
        self.restore()
        self.client.__exit__(None, None, None)
        self.app.state.service.close()
        cleanup(self.root)

    # --- plán: jeden návrh změny zadání pro všechny karty, člověk ho přijme --------------------------
    def plan(self):
        m, s = self.meter.where("setup", "plan"), self.scope
        context = m.call("human", "GET", "/api/oporahub/changesets/context", params=s).json()
        baseline = m.call("human", "POST", "/api/oporahub/baselines", body={
            **s, "subject": "Výchozí zadání", "expectedAcceptedHead": None,
            "expectedGraphDigest": context["graphDigest"], "expectedSpecificationsVersion": context["specificationsVersion"]}).json()
        context = m.call("planner", "GET", "/api/oporahub/changesets/context", params=s).json()
        documents = {item["nodeId"]: item for item in context["documents"]}
        proposal = m.call("planner", "POST", "/api/oporahub/changesets", body={
            **s, "subject": "Kroky karet 1.3, 1.5, 1.6", "parentRevision": context["acceptedHead"],
            "expectedGraphDigest": context["graphDigest"],
            "changes": [{"nodeId": card["id"], "expectedRevision": documents[card["id"]]["revision"],
                         "fields": {**documents[card["id"]]["fields"], "steps": _steps(card)}} for card in self.fix["cards"]]}).json()
        m.call("human", "GET", f"/api/oporahub/changesets/{proposal['id']}", params=s)
        accepted = m.call("human", "POST", f"/api/oporahub/changesets/{proposal['id']}/accept",
                          body={**s, "expectedAcceptedHead": baseline["id"]}).json()
        self.outcome["acceptedHead"] = accepted["id"]
        return accepted

    # --- tok jedné karty -------------------------------------------------------------------------
    def context(self, index, card, actor="agent"):
        m, s = self.meter.where(card["id"], "kontext"), self.scope
        if self.predecessors:
            self.read_predecessors(card, actor)
        state = m.call(actor, "GET", "/api/oporahub/agent-state", params=s).json()
        action = next((a for a in state.get("actions", []) if a.get("verb") == "claim" and a.get("targetId") == card["id"]), None)
        entry = next((c for c in state.get("cards", []) if c["nodeId"] == card["id"]), {})
        if not action or action.get("status") != "ready":
            return {"refused": (action or {}).get("blockReason") or "no_claim_action", "blockedBy": entry.get("blockedBy")}
        version = 2
        context = m.call(actor, "POST", "/api/oporahub/executions/context",
                         body={**s, "nodeId": card["id"], "contextProtocolVersion": 2}, expect=None)
        if context.status_code != 200 or not context.json().get("available", True):
            version = 1
            context = m.call(actor, "GET", "/api/oporahub/executions/context", params={**s, "nodeId": card["id"]})
        value = context.json()
        claim = {**s, "nodeId": card["id"], "expectedAcceptedHead": value["acceptedHead"],
                 "expectedContextVersion": value["contextVersion"], "requestId": f"claim-{index}-{actor}", "ttlSeconds": 900}
        if version == 2:
            claim["contextProtocolVersion"] = 2
        response = m.call(actor, "POST", "/api/oporahub/executions/claim", body=claim, expect=None)
        if response.status_code != 200:
            return {"refused": response.json().get("code", response.status_code), "detail": response.text[:300]}
        record = response.json()
        assignment = m.call(actor, "GET", f"/api/oporahub/executions/{record['executionId']}/assignment", params=s,
                            headers={"X-Opora-Execution-Token": record["token"]}).json()
        return {"record": record, "assignment": assignment, "contextVersion": version}

    def read_predecessors(self, card, actor):
        """Varianta B+: agent si sám dočte běhy předchůdců (data v OporaHubu jsou, jen je zadání nenese)."""
        m, s = self.meter, self.scope
        for edge in self.fix["edges"]:
            if edge["target"] != card["id"]:
                continue
            listing = m.call(actor, "GET", "/api/oporahub/executions", params={**s, "nodeId": edge["source"]}).json()
            for item in listing.get("executions", [])[:1]:
                m.call(actor, "GET", f"/api/oporahub/executions/{item['executionId']}/results", params=s)
                m.call(actor, "GET", f"/api/oporahub/executions/{item['executionId']}/pull-request", params=s, expect=None)
            m.call(actor, "GET", "/api/oporahub/review-lens", params={**s, "nodeId": edge["source"]})

    def work(self, index, card, ctx, stop_after=None):
        m, s, record = self.meter.where(card["id"], "prace"), self.scope, ctx["record"]
        commits = []
        for j, block in enumerate(card["blocks"]):
            if stop_after is not None and j >= stop_after:
                return commits, False
            commits.append(self.repo.commit(index, f"s{j + 1}", block["title"]))
            if j == 0:
                m.call("agent", "POST", f"/api/oporahub/executions/{record['executionId']}/heartbeat",
                       body={**s, "token": record["token"], "epoch": record["epoch"], "ttlSeconds": 900})
        return commits, True

    def report(self, index, card, ctx, commits):
        m, s, record, mark = self.meter.where(card["id"], "hlaseni"), self.scope, ctx["record"], markers(index)
        result = {
            "summary": f"Karta {index}: {len(commits)}/{len(commits)} kroků. {mark['decision']}: originál pod klíčem sha256. "
                       f"{mark['handoff']}: naváž na rozhraní z kroku s1.",
            "artifacts": [], "evidence": [{"name": f"{mark['check']} uv run pytest -q", "status": "passed"}],
            "selfChecks": {"headSha": commits[-1], "checks": [
                {"name": "tests", "command": "uv run pytest -q", "exitCode": 0, "status": "passed", "summary": mark["check"]},
                {"name": "build", "command": "npm run build", "exitCode": 0, "status": "passed", "summary": "built"}]},
            "stepResults": [{"stepId": f"s{j + 1}", "status": "done",
                             "evidence": {"notes": f"{mark['step']}{j + 1} hotovo", "checks": [f"{mark['check']}"],
                                          "commits": [c]}} for j, c in enumerate(commits)],
        }
        response = m.call("agent", "POST", f"/api/oporahub/executions/{record['executionId']}/results", expect=None,
                          body={**s, "token": record["token"], "epoch": record["epoch"], "requestId": f"result-{index}",
                                "result": result})
        return response

    def office(self, index, card, ctx, commits):
        """agent-office: otevře PR, připojí ho k běhu a pošle PR Lens (pull-request-handoff.ts, pr-lens.ts)."""
        m, s, record, mark = self.meter.where(card["id"], "pr"), self.scope, ctx["record"], markers(index)
        number = 100 + index
        FakeGitHub.heads[number] = commits[-1]
        link = m.call("office", "POST", f"/api/oporahub/executions/{record['executionId']}/pull-request", expect=None,
                      body={**s, "token": record["token"], "epoch": record["epoch"], "requestId": f"link-{index}",
                            "repository": REPOSITORY, "number": number, "headRef": f"work/card-{number}", "headSha": commits[-1]})
        lens = m.call("office", "POST", "/api/oporahub/review-jobs/lens", expect=None, body={
            **s, "executionId": record["executionId"], "token": record["token"], "epoch": record["epoch"],
            "lens": {"prNumber": number, "headSha": commits[-1], "validatedAt": "2026-10-23T10:30:00+00:00",
                     "spec": {"kind": "graph", "title": mark["lens"], "nodes": [], "edges": []}}})
        return link, lens

    def review(self, index, card, ctx):
        """Úlohy review jsou ve výchozí konfiguraci vypnuté (brána = ochrana větve na GitHubu)."""
        m, s, record = self.meter.where(card["id"], "review"), self.scope, ctx["record"]
        m.call("reviewer", "GET", f"/api/oporahub/executions/{record['executionId']}/results", params=s)
        m.call("reviewer", "GET", "/api/oporahub/review-lens", params={**s, "nodeId": card["id"]})
        m.call("reviewer", "POST", "/api/oporahub/review-jobs/claim", body={**s, "requestId": f"slot-{index}"}, expect=None)

    def merge(self, index, link):
        """GitHub ohlásí sloučení; smyčka uzavření běhu zapíše plán zpět (jako backendové testy)."""
        return merged(self.service, self.scope, index, link)

    def accept(self, index, card):
        m, s = self.meter.where(card["id"], "prijeti"), self.scope
        state = m.call("human", "GET", "/api/oporahub/agent-state", params=s).json()
        entry = next(c for c in state["cards"] if c["nodeId"] == card["id"])
        current = m.call("human", "GET", "/api/desktop-v3/state", params=s).json()
        node = current["state"]["nodes"][card["id"]]
        node["done"] = {**node.get("done", {}), "confirmed": True, "by": "human", "at": "2026-10-23T12:00:00+00:00",
                        "note": "Přijato člověkem."}
        response = m.call("human", "POST", "/api/desktop-v3/state", expect=None,
                          body={**s, "expectedRevision": current["revision"], "state": current["state"]})
        return response, entry.get("dod")

    # --- měření ----------------------------------------------------------------------------------
    def levels(self, card):
        state = self.meter.where(card["id"], "mereni").call("human", "GET", "/api/oporahub/agent-state", params=self.scope).json()
        entry = next(c for c in state["cards"] if c["nodeId"] == card["id"])
        steps = entry.get("steps") or {}
        total = steps.get("total") or 1
        claimed = steps.get("done", 0)
        code = 0
        for item in steps.get("items", []):
            execution = item.get("executionId")
            if item["status"] != "done" or not execution:
                continue
            results = self.meter.call("human", "GET", f"/api/oporahub/executions/{execution}/results", params=self.scope).json()
            found = [c for r in results.get("results", []) for sr in (r.get("result") or {}).get("stepResults", [])
                     if sr["stepId"] == item["id"] for c in sr.get("evidence", {}).get("commits", [])]
            if found and all(self.repo.exists(c) for c in found):
                code += 1
        dod = entry.get("dod") or {}
        human = total if dod.get("human_close") else 0
        return {"claimed": claimed / total, "code": code / total, "human": human / total, "perStepHuman": False,
                "codeSource": "stepResults[].evidence.commits (strukturované)", "dod": dod}

    def run(self, crash_card=None, crash_after=None):
        self.plan()
        for index, card in enumerate(self.fix["cards"]):
            ctx = self.context(index, card)
            if "refused" in ctx:
                self.outcome[card["id"]] = {"claimRefused": ctx}
                return self
            self.executions[card["id"]] = ctx["record"]["executionId"]
            commits, finished = self.work(index, card, ctx, stop_after=crash_after if crash_card == index else None)
            if not finished:
                self.outcome[card["id"]] = {"crashed": True, "commits": commits}
                return self
            reported = self.report(index, card, ctx, commits)
            link, lens = self.office(index, card, ctx, commits)
            self.review(index, card, ctx)
            merged = self.merge(index, link.json()) if link.status_code == 200 else None
            accepted, dod = self.accept(index, card)
            self.outcome[card["id"]] = {
                "contextProtocol": ctx["contextVersion"], "reported": reported.status_code,
                "reportedDetail": reported.text[:300] if reported.status_code != 200 else "",
                "pr": link.status_code, "prDetail": link.text[:300] if link.status_code != 200 else "",
                "lens": lens.status_code, "lensDetail": lens.text[:300] if lens.status_code != 200 else "",
                "merge": merged, "accepted": accepted.status_code,
                "acceptedDetail": accepted.text[:300] if accepted.status_code != 200 else "", "dodBeforeClose": dod,
                "commits": commits}
        return self

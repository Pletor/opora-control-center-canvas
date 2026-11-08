"""Výzkum a duel srdce přes skutečnou aplikaci (docs/brain-heart.md §3c, §3d): nástroj srdce píše do schránky zadání
tokenem srdce, strany a soudci duelu jsou různí aktéři. Model ani `npx` se nespouští: `_execute` je falešný; citace
výzkumníka ověřuje kód proti místnímu serveru."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.brain_opora.heart import command, opora_heart, opora_research, research_digest
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

HERO = ("<html><body><section><h1>Zahrada</h1><p>Hero sekce s nadpisem a tlačítkem Začít vede na kontakt.</p>"
        + "<p>Další obsah stránky o zahradě. </p>" * 30 + "</section></body></html>").encode("utf-8")
DIGEST = {"verdict": "feasible", "confidence": "medium",
          "layers": {"fe": {"essence": "Hero podle vzoru", "recommended": "Komponenta Hero",
                            "options": [{"approach": "Statická stránka", "pros": "rychlejší", "cons": "", "facts": ["f1"]}],
                            "risks": []}},
          "hypotheses": [], "next": "plan", "nextWhy": "Vzor je doložený.",
          "slices": [{"layer": "fe", "title": "Hero sekce", "why": "první dojem", "facts": ["f1"]}]}


class _Site(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/hero" else 404)
        self.end_headers()
        self.wfile.write(HERO if self.path == "/hero" else b"")

    def log_message(self, *args):
        pass


def claude_json(result, cost):
    return json.dumps({"type": "result", "is_error": False, "result": result, "total_cost_usd": cost})


class FakeClaude:
    """Stůl: výzkumník (`findings`) a destilace (`digest`); duel: strany pevné texty, soudci straně A drtivě."""

    def __init__(self, findings=(), digest=None):
        self.findings, self.digest, self.lines, self.prompts = list(findings), digest, [], []

    def __call__(self, argv, cwd, env, timeout=None, input_text=None):
        self.lines.append(argv)
        self.prompts.append(input_text)
        assert "OPORA_HEART_TOKEN" not in env and "OPORA_BASE_URL" not in env
        if "--allowedTools" in argv:
            return 0, claude_json(json.dumps({"findings": self.findings}), 0.05), "", False
        if input_text.startswith("Jsi syntetik výzkumu"):
            return 0, claude_json(json.dumps(self.digest) if self.digest else "Nevím.", 0.01), "", False
        if "Jsi nezávislý soudce" in input_text:
            ids = re.search(r"těchto výměn: ([^\n]+)\.", input_text).group(1).split(", ")
            scores = [{"turnId": turn, "strength": 8, "supports": "A"} for turn in ids]
            return 0, claude_json("Hodnocení: " + json.dumps({"scores": scores}), 0.01), "", False
        side = re.search(r"Hájíš stranu (A|B)", input_text).group(1)
        answer = {"claim": f"Strana {side}: osvědčené řešení.", "grill": f"Otázka strany {side}?",
                  "answer": f"Odpověď strany {side}.", "synthesis": "Spojit obojí."}
        return 0, claude_json(json.dumps(answer), 0.01), "", False


@pytest.fixture
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def heart(tmp_path, monkeypatch):
    """Aplikace se zapnutou bránou a `opora_heart.call` přes TestClient s tokenem srdce a jménem aktéra."""
    for key, value in {"OPORA_PROJECT": "draft", "OPORA_WORKSPACE": "draft"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("OPORA_SOURCE_ROOT", raising=False)
    brain = tmp_path / "brain"
    command.write_config(brain, command.HeartSkills("P\n", {}, {}))
    monkeypatch.setattr(opora_heart, "DILNA", brain / "dilna")
    monkeypatch.setattr(research_digest, "find_claude", lambda: "claude")
    monkeypatch.setattr(opora_research, "find_browser", lambda: "C:/chrome.exe")
    with TestClient(create_app(tmp_path / "app"), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        client.cookies.clear()  # srdce nemá doklad UI

        def call(method, path, body=None, query=None, actor="heart"):
            headers = {**HEADERS, tokens.HEADER: token, "X-Opora-Actor": f"agent; name={actor}"}
            response = client.request(method, path, params=query, json=body, headers=headers)
            if response.status_code >= 400:
                payload = response.json()
                raise opora_heart.Failure({"error": str(payload.get("error") or payload.get("detail")),
                                           "code": payload.get("code") or f"http_{response.status_code}"})
            return response.json()

        monkeypatch.setattr(opora_heart, "call", call)
        yield client, call, brain


def run(fake, monkeypatch, argv):
    monkeypatch.setattr(opora_heart, "_execute", fake)
    return opora_heart.run(opora_heart.parser().parse_args(argv))


def test_research_map_keeps_all_facts_and_replay_does_not_duplicate(heart):
    _client, call, _brain = heart
    args = opora_heart.parser().parse_args(["research", "--question", "Login behavior?", "--title", "Login",
                                          "--topic", "Login", "--topic", "Logic", "--question-id", "pq_1"])
    facts = [{"id": f"f{i}", "claim": f"Finding {i}", "layer": "be", "source": "https://example.org/login",
              "quote": "exact quoted source " * 300, "verified": "verified"} for i in range(12)]
    payload = opora_research.opora_research_map.batch({"digest": DIGEST, "facts": facts}, "vf_import", args,
                                                    "2026-11-08T12:00:00Z")
    saved = call("POST", "/api/research", {**SCOPE, **payload})
    assert call("POST", "/api/research", {**SCOPE, **payload}) == saved
    headers = call("GET", "/api/research", query=SCOPE)
    assert len(headers["cards"]) == 14 and len(headers["edges"]) == 14
    assert all("content" not in card and "sources" not in card for card in headers["cards"])
    [option] = [card for card in saved["cards"] if card["kind"] == "option"]
    assert option["verification"]["status"] == "inference" and option["title"] == "Statická stránka"
    assert any(edge["toId"] == option["id"] and edge["relation"] == "supports" for edge in headers["edges"])
    for card, fact in zip((card for card in saved["cards"] if card["kind"] == "finding"), facts, strict=True):
        detail = call("GET", f"/api/research/cards/{card['id']}", query=SCOPE)
        assert json.loads(detail["card"]["content"]) == fact
        assert detail["card"]["sources"][0]["quote"] == fact["quote"]
        assert detail["card"]["refs"]["questionIds"] == ["pq_1"]
        assert len(detail["history"]) == 1


def test_research_writes_the_vault_and_a_duel_reaches_a_decision(heart, monkeypatch, site):
    client, call, brain = heart
    findings = [{"claim": "Hero má nadpis a tlačítko", "kind": "fact", "source": f"{site}/hero",
                 "quote": "Hero sekce s nadpisem a tlačítkem Začít"},
                {"claim": "Komponenta už je", "source": "src/Hero.tsx:3", "quote": "export function Hero"}]
    fake = FakeClaude(findings, DIGEST)
    done = run(fake, monkeypatch, ["research", "--question", "Jak udělat hero?", "--title", "Hero",
                                   "--target", f"{site}/hero", "--layer", "fe"])
    assert (done["verdict"], done["confidence"], done["next"], done["facts"]) == ("feasible", "medium", "plan", "1/2")
    assert done["layers"] == ["fe: Hero podle vzoru → Komponenta Hero"] and done["slices"] == ["Hero sekce"]
    assert "claimed" not in done and done["out"] == f"dilna/out/research/{done['fragmentId']}.json"
    gather = next(line for line in fake.lines if "--allowedTools" in line)
    assert gather[gather.index("--mcp-config") + 1] == str((brain / "dilna" / "rea-mcp.json").resolve())
    assert "Jak udělat hero?" in fake.prompts[0] and f"{site}/hero" in fake.prompts[0]
    fragment = call("GET", "/api/brief-vault/fragment", query={**SCOPE, "id": done["fragmentId"]})
    research = fragment["details"]["research"]
    assert (research["verdict"], research["status"], [e["url"] for e in research["evidence"]]) == (
        "feasible", "done", [f"{site}/hero"])
    assert research["approach"].startswith("Další krok: plan – Vzor je doložený.") and fragment["fragment"]["by"] == "heart"
    saved = json.loads((brain / "dilna" / "out" / "research" / f"{done['fragmentId']}.json").read_text(encoding="utf-8"))
    assert saved["digest"]["next"] == "plan" and [f["verified"] for f in saved["facts"]] == ["verified", "unreachable"]
    assert (brain / "dilna" / "data" / "research" / done["fragmentId"] / "gather" / "q1.json").is_file()

    # Nic ověřeného a destilace bez JSON: unverified, `ask`; kořen „Výzkum srdce“ se nezaloží podruhé.
    failed = run(FakeClaude(), monkeypatch, ["research", "--question", "Jde to offline?", "--title", "Offline"])
    assert (failed["verdict"], failed["next"], failed["facts"]) == ("unverified", "ask", "0/0")
    roots = [r for r in call("GET", "/api/brief-vault", query=SCOPE)["roots"] if r["title"] == opora_research.ROOT_TITLE]
    assert len(roots) == 1

    fake = FakeClaude()
    result = run(fake, monkeypatch, ["duel", "--subject", done["fragmentId"], "--a", "Hero podle vzoru.",
                                     "--b", "Statická stránka bez komponent."])
    assert result["outcome"] == "keep" and result["probability"] <= 0.40 and result["subCalls"] == 9
    assert all(line[line.index("--model") + 1] == "haiku" and "--allowedTools" not in line for line in fake.lines)
    duel = call("GET", "/api/brief-vault/duel", query={**SCOPE, "id": result["duelId"]})["duel"]
    assert duel["status"] == "decided" and duel["decision"]["outcome"] == "keep"
    assert {(t["side"], t["by"]) for t in duel["turns"]} == {
        ("B", "heart"), ("A", "srdce-obhajce-a"), ("B", "srdce-obhajce-b")}
    assert {s["judge"] for s in duel["scores"]} == {"srdce-soudce-1", "srdce-soudce-2"}
    assert [t["kind"] for t in duel["turns"]].count("grill") == 4 and "skipped" not in result

    runs = [json.loads(line) for line in (brain / "dilna" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["script"], r["subCalls"], r["subCostUsd"]) for r in runs] == [
        ("research", 2, 0.06), ("research", 2, 0.06), ("duel", 9, 0.09)]

    text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
    section = text.split("VÝZKUM:")[1]
    assert f"- duel Duel: Statická stránka bez komponent. ({result['duelId']}) · keep · p " in section
    assert f"- výzkum Hero ({done['fragmentId']}) · feasible/medium · next plan · done" in section
    assert f"- výzkum Offline ({failed['fragmentId']}) · unverified · next ask · done" in section


def test_duel_sides_cannot_be_the_same_actor_on_both_sides(heart):
    """Pojistka serveru: aktér strany B (srdce) nesmí hájit A ani soudit; token srdce jména neslévá."""
    _client, call, _brain = heart
    root = opora_research.heart_root(opora_heart, SCOPE)
    opened = call("POST", "/api/brief-vault", {**SCOPE, "op": "duel-open", "subject": {"kind": "fragment", "id": root},
                                               "incumbent": {"text": "A"}, "challenger": {"text": "B"},
                                               "scopeNodeId": ""})
    with pytest.raises(opora_heart.Failure):
        call("POST", "/api/brief-vault", {**SCOPE, "op": "duel-turn", "fragmentId": opened["fragment"]["id"],
                                          "expectedRevision": opened["fragment"]["revision"], "side": "A",
                                          "kind": "claim", "text": "A je lepší."})


def test_research_for_a_requirement_spends_its_cap_and_then_refuses_without_running(heart, monkeypatch):
    """Výslech, řez 2 (docs/navrhy/2026-10-30-vyslech-srdce.md §8): `research --requirement` čerpá strop požadavku,
    cena jde do `intake_briefs.cost_usd`; vyčerpaný strop odmítne dřív, než se spustí stůl."""
    from backend.brain_opora.determinism import brief_setting
    from backend.brain_opora.determinism.test_brief import add
    from database.repositories.intake_briefs import IntakeBriefs

    client, _, _ = heart
    service = client.app.state.service
    brief_setting.write(service, {"project": "draft", "enabled": True, "researchUsd": 0.1})
    db = service.db_for("draft")
    with db:
        add(db, "rq_1", ["fix_for_milestone"], area=None)
    argv = ["research", "--question", "Co metriky potřebují?", "--title", "Metriky", "--requirement", "rq_1"]
    first = run(FakeClaude(), monkeypatch, argv)
    assert first["brief"] == {"requirement": "rq_1", "spentUsd": 0.06, "capUsd": 0.1, "leftUsd": 0.04}
    assert run(FakeClaude(), monkeypatch, argv)["brief"]["spentUsd"] == 0.12  # strop se hlídá před stolem
    stored = IntakeBriefs(db).get("rq_1")
    assert stored["costUsd"] == 0.12 and [item["fragmentId"] for item in stored["research"]] == [
        first["fragmentId"], stored["research"][1]["fragmentId"]] and stored["status"] == "research"
    fake = FakeClaude()
    with pytest.raises(opora_heart.Failure) as refused:
        run(fake, monkeypatch, argv)
    assert refused.value.payload["code"] == "brief_research_spent" and fake.lines == []
    plain = run(FakeClaude(), monkeypatch, argv[:-2])  # bez --requirement jako dřív
    assert "brief" not in plain and IntakeBriefs(db).get("rq_1")["costUsd"] == 0.12

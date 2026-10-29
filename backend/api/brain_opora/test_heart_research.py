"""Výzkum a duel srdce přes skutečnou aplikaci (docs/brain-heart.md §3c): nástroj srdce píše do schránky zadání
tokenem srdce, strany a soudci duelu jsou různí aktéři. Model ani `npx` se nespouští: `_execute` je falešný."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.brain_opora.heart import command, opora_heart, opora_research
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

FOUND = {"verdict": "feasible", "confidence": "medium", "approach": "Převzít vzor z Hero.",
         "evidence": [{"source": "https://example.com/hero", "quote": "hero sekce"},
                      {"source": "src/Hero.tsx:3", "quote": "export function Hero"}],
         "alternatives": [{"approach": "Statická stránka", "why": "rychlejší"}]}


def claude_json(result, cost):
    return json.dumps({"type": "result", "is_error": False, "result": result, "total_cost_usd": cost})


class FakeClaude:
    """Výzkumník odpoví `researcher`; pod-volání duelu: strany pevné texty, soudci straně A drtivě."""

    def __init__(self, researcher):
        self.researcher, self.lines, self.prompts = researcher, [], []

    def __call__(self, argv, cwd, env, timeout=None, input_text=None):
        self.lines.append(argv)
        self.prompts.append(input_text)
        assert "OPORA_HEART_TOKEN" not in env and "OPORA_BASE_URL" not in env
        if "--allowedTools" in argv:
            return 0, claude_json(self.researcher, 0.05), "", False
        if "Jsi nezávislý soudce" in input_text:
            ids = re.search(r"těchto výměn: ([^\n]+)\.", input_text).group(1).split(", ")
            scores = [{"turnId": turn, "strength": 8, "supports": "A"} for turn in ids]
            return 0, claude_json("Hodnocení: " + json.dumps({"scores": scores}), 0.01), "", False
        side = re.search(r"Hájíš stranu (A|B)", input_text).group(1)
        answer = {"claim": f"Strana {side}: osvědčené řešení.", "grill": f"Otázka strany {side}?",
                  "answer": f"Odpověď strany {side}.", "synthesis": "Spojit obojí."}
        return 0, claude_json(json.dumps(answer), 0.01), "", False


@pytest.fixture
def heart(tmp_path, monkeypatch):
    """Aplikace se zapnutou bránou a `opora_heart.call` přes TestClient s tokenem srdce a jménem aktéra."""
    for key, value in {"OPORA_PROJECT": "draft", "OPORA_WORKSPACE": "draft"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("OPORA_SOURCE_ROOT", raising=False)
    brain = tmp_path / "brain"
    command.write_config(brain)
    monkeypatch.setattr(opora_heart, "DILNA", brain / "dilna")
    monkeypatch.setattr(opora_research, "find_claude", lambda: "claude")
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


def test_research_writes_the_vault_and_a_duel_reaches_a_decision(heart, monkeypatch):
    client, call, brain = heart
    fake = FakeClaude("Zde výsledek:\n" + json.dumps(FOUND))
    done = run(fake, monkeypatch, ["research", "--question", "Jak udělat hero?", "--title", "Hero",
                                   "--target", "https://example.com/hero"])
    assert (done["verdict"], done["confidence"], done["alternatives"]) == ("feasible", "medium", ["Statická stránka"])
    assert done["approach"].startswith("Převzít vzor z Hero.") and "claimed" not in done
    researcher = fake.lines[0]
    assert researcher[researcher.index("--mcp-config") + 1] == str((brain / "dilna" / "rea-mcp.json").resolve())
    assert "Jak udělat hero?" in fake.prompts[0] and "https://example.com/hero" in fake.prompts[0]
    fragment = call("GET", "/api/brief-vault/fragment", query={**SCOPE, "id": done["fragmentId"]})
    research = fragment["details"]["research"]
    assert (research["verdict"], research["status"], len(research["evidence"])) == ("feasible", "done", 1)
    assert "src/Hero.tsx:3" in research["approach"] and fragment["fragment"]["by"] == "heart"

    # Neplatná odpověď výzkumníka: unverified se začátkem odpovědi; kořen „Výzkum srdce“ se nezaloží podruhé.
    failed = run(FakeClaude("Nevím, nenašel jsem nic."), monkeypatch,
                 ["research", "--question", "Jde to offline?", "--title", "Offline"])
    assert failed["verdict"] == "unverified" and failed["approach"].startswith("Výzkumník nevrátil platný JSON: Nevím")
    roots = [r for r in call("GET", "/api/brief-vault", query=SCOPE)["roots"] if r["title"] == opora_research.ROOT_TITLE]
    assert len(roots) == 1

    fake = FakeClaude("")
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
        ("research", 1, 0.05), ("research", 1, 0.05), ("duel", 9, 0.09)]

    text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
    section = text.split("VÝZKUM:")[1]
    assert f"- duel Duel: Statická stránka bez komponent. ({result['duelId']}) · keep · p " in section
    assert f"- výzkum Hero ({done['fragmentId']}) · feasible/medium · done" in section
    assert f"- výzkum Offline ({failed['fragmentId']}) · unverified · done" in section


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

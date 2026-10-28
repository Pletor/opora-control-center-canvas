"""Recept skillu „Stavba stránky“ end-to-end: headless agent s plnou autonomií v lokálním projektu bez GitHubu.

Prochází přesně příkazy ze SKILL.md (sekce „Recept: stavba stránky“) nad skutečným backendem (TestClient místo
sítě, `test_opora_hub.bridge`): mapa a karty dávkou → `act` propose_graph → `act` accept → claim → kroky →
výsledek → commit → `local-merge` → `check-run` → doklad cesty → `act` close_card. Žádný krok nesmí vrátit chybu
a agent nepotřebuje vlastního HTTP klienta. Člověk jen založí projekt a zapne autonomii.
Druhá část hlídá nové chybové zprávy: neplatné tělo = 422 s polem, tvarem a příkladem (exit 6), krok „brzy“ = hint.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import opora_api
import opora_hub
import opora_write
from test_opora_hub import ORIGIN, bridge

STEPS = [
    {"id": "s1", "order": 1, "title": "Sekce hero vykreslí nadpis a perex", "kind": "code",
     "files": ["src/pages/pribeh/Hero.tsx"], "dependsOn": [],
     "acceptance": ['kořen nese data-opora-section="hero"', "npm run build projde"]},
    {"id": "s2", "order": 2, "title": "Vzhled podle site.feel stránky", "kind": "design",
     "files": ["src/pages/pribeh/hero.css"], "dependsOn": ["s1"],
     "acceptance": ["barvy a typografie odpovídají feel: klidná, přírodní", "kontrast textu ≥ 4.5:1"]},
    {"id": "s3", "order": 3, "title": "Přístupnost a prázdný stav", "kind": "code",
     "files": ["src/pages/pribeh/Hero.tsx"], "dependsOn": ["s2"],
     "acceptance": ["jediný h1, alt u obrázku, ovladatelné klávesnicí", "bez dat ukáže srozumitelný prázdný stav"]},
    {"id": "s4", "order": 4, "title": "Testy kritérií karty", "kind": "test",
     "files": ["src/pages/Pribeh.test.tsx"], "dependsOn": ["s3"],
     "acceptance": ["test ověří h1 v [data-opora-section=hero]", "npm test projde"]},
]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def agent(tmp_path, monkeypatch):
    """Lokální Git projekt bez vzdáleného repa; člověk ho založí a zapne plnou autonomii, dál jen agent."""
    from fastapi.testclient import TestClient

    import backend.conftest  # noqa: F401  (lidská UI session pro TestClient, vypnuté smyčky na pozadí)
    from backend.app.factory import create_app
    from backend.canvas.test_opora_folder_repository import checkout

    monkeypatch.setenv(opora_hub.STATE_DIR_ENV, str(tmp_path / "hub"))
    monkeypatch.setenv(opora_write.AGENT_ENV, "stavitel-e2e")
    monkeypatch.setenv(opora_write.BASE_ENV, ORIGIN)
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        repo = checkout(tmp_path, origin=None)
        created = client.post("/api/local-project", headers={"origin": ORIGIN},
                              json={"path": str(repo), "name": "Zelený balkon", "confirmed": True})
        assert created.status_code == 200, created.text
        project = created.json()["id"]
        switched = client.post("/api/project-settings/agent-autonomy", headers={"origin": ORIGIN},
                               json={"project": project, "full": True})
        assert switched.status_code == 200, switched.text
        monkeypatch.setattr(opora_write, "_open", bridge(client))
        yield {"project": project, "workspace": "draft", "repo": repo, "tmp": tmp_path}


def scope(agent):
    return ["--project", agent["project"], "--workspace", agent["workspace"]]


def hub(capsys, agent, *argv):
    code = opora_hub.main([*argv, *scope(agent)])
    captured = capsys.readouterr()
    assert code == 0, (argv, captured.err)
    return json.loads(captured.out)


def api(capsys, *argv):
    code = opora_api.main(list(argv))
    out = json.loads(capsys.readouterr().out)
    return code, out


def site_plan(digest):
    """Mapa a karty jednou dávkou: aplikace s cestou, stránka s feel a sekcí, komponenta s kroky."""
    return {"digest": digest, "plan": {"nodes": [
        {"ref": "web", "kind": "sector", "parent": None, "name": "Web Zelený balkon",
         "site": {"kind": "application", "environments": [{"name": "local", "host": "127.0.0.1:5173"}],
                  "journeys": [{"id": "zacit", "name": "Z menu k příběhu",
                                "steps": [{"id": "vstup", "page": "nav"},
                                          {"id": "pribeh", "page": "pribeh",
                                           "via": {"do": "click", "text": "Příběh"}}]}]}},
        {"ref": "pribeh", "kind": "node", "parent": "web", "name": "Příběh",
         "site": {"kind": "page", "path": "/pribeh", "goal": "Začátečník uvěří, že to zvládne.",
                  "feel": "klidná, přírodní", "navLabel": "Příběh",
                  "sections": [{"id": "hero", "role": "hero", "name": "Úvod", "intent": "Proč zůstat a číst."}]}},
        {"ref": "hero", "kind": "node", "parent": "pribeh", "name": "Sekce hero", "card": {"section": "hero"},
         "spec": {"goal": "Úvod příběhu s nadpisem a perexem.", "non_goals": "Další sekce.",
                  "acceptance": "Sekce hero je přístupná, odpovídá feel a má test.", "steps": STEPS}},
    ], "edges": [], "decisions": [{"text": "Stránka je statická React komponenta; texty v kódu.", "node": "pribeh"}]}}


def test_page_recipe_runs_end_to_end_without_a_single_error(agent, capsys):
    project, repo = agent["project"], agent["repo"]
    # 1. Mapa a karty: jedna dávka (nejdřív --dry-run). Krok cesty ukazuje na stránku jejím ref.
    code, view = api(capsys, "GET", "/api/view", *scope(agent))
    assert code == 0, view
    draft = agent["tmp"] / "drafts" / "plan.json"  # koncept mimo repozitář projektu
    draft.parent.mkdir()
    draft.write_text(json.dumps(site_plan(view["result"]["digest"]), ensure_ascii=False), "utf-8")
    for extra in (["--dry-run"], []):
        code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json-file", str(draft), *extra])
        out = json.loads(capsys.readouterr().out)
        assert code == 0 and out["ok"], out
        assert not [item for item in out["result"]["warnings"] if item["rule"] == "journey.broken"], out
    card = out["result"]["refs"]["hero"]

    # 2. Přijatý graf plánu: první ready akce je propose_graph, pak accept s přesným tělem v preconditions.
    state = hub(capsys, agent, "state", "--fresh")
    assert state["ready"][0]["verb"] == "propose_graph", state["ready"]
    proposed = hub(capsys, agent, "act", "--action-id", state["ready"][0]["id"])
    assert proposed["ok"] and proposed["next"]["verb"] == "accept", proposed
    accepted = hub(capsys, agent, "act", "--action-id", proposed["next"]["id"])
    assert accepted["result"]["graphManifestId"] and accepted["next"]["verb"] == "claim", accepted

    # 3. Převzetí a neměnné zadání s kroky.
    action = hub(capsys, agent, "pick", "--verb", "claim", "--target", card)
    lease = hub(capsys, agent, "claim", "--action-id", action["id"])
    execution = lease["executionId"]
    assignment = hub(capsys, agent, "assignment", "--execution", execution)
    assert [item["id"] for item in assignment["steps"]] == ["s1", "s2", "s3", "s4"]

    # 4. Kroky: práce v repu, commit po kroku, krok hned do OPORY.
    page = repo / "src" / "pages" / "pribeh"
    page.mkdir(parents=True)
    for item in STEPS:
        (page / f"{item['id']}.txt").write_text(item["title"], "utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", item["title"])
        sha = git(repo, "rev-parse", "HEAD")
        done = hub(capsys, agent, "step", "--execution", execution, "--step-id", item["id"], "--status", "done",
                   "--notes", item["title"], "--commit", sha, "--check", "npm test")
        assert done["status"] == "done", done

    # 5. Výsledek běhu = přijetí karty (dod.card_acceptance).
    result = agent["tmp"] / "drafts" / "result.json"
    result.write_text(json.dumps({
        "summary": "Sekce hero hotová; 4/4 kroky.", "decisions": ["Styl sekce v hero.css podle feel stránky."],
        "selfChecks": {"headSha": sha, "checks": [{"name": "tests", "command": "npm test", "exitCode": 0,
                                                    "status": "passed", "summary": "4 passed"}]},
        "stepResults": [{"stepId": item["id"], "status": "done", "evidence": {"notes": item["title"], "commits": [sha]}}
                        for item in STEPS]}, ensure_ascii=False), "utf-8")
    hub(capsys, agent, "results", "--execution", execution, "--result-file", str(result))
    dod = hub(capsys, agent, "state", "--card", card)["cards"][0]["dod"]
    assert dod["gate"] == "local" and dod["steps"] and dod["card_acceptance"], dod

    # 6. local-merge sloučeného commitu, 7. kontroly na tomto commitu.
    merged = hub(capsys, agent, "local-merge", "--execution", execution, "--commit", sha)
    assert merged["state"] == "merged" and merged["planWrittenBack"] is True, merged
    code, run = api(capsys, "POST", "/api/check-run", *scope(agent),
                    "--json", json.dumps({"scope": card, "status": "green", "sha": sha}))
    assert code == 0, run

    # 8. Cesta: doklad přehrání (v testu místo tools/journey_run.py, který potřebuje prohlížeč).
    code, plan = api(capsys, "GET", "/api/project-architecture/journey-plan", "--query", f"project={project}",
                     "--query", "journey=zacit")
    assert code == 0, plan
    evidence = {"schema": "opora.journey-run/1", "applicationId": plan["result"]["applicationId"],
                "journeyId": "zacit", "planDigest": plan["result"]["digest"],
                "command": "uv run python tools/journey_run.py --journey zacit", "at": "2099-01-01T00:00:00Z",
                "segments": [{"from": item["from"], "to": item["to"], "ok": True}
                             for item in plan["result"]["segments"]]}
    code, recorded = api(capsys, "POST", "/api/project-architecture/journey-runs", "--query", f"project={project}",
                         "--json", json.dumps(evidence))
    assert code == 0, recorded

    # 9. Uzavření karty: s plnou autonomií je close_card pro agenta ready.
    state = hub(capsys, agent, "state", "--fresh", "--card", card)
    assert state["cards"][0]["dod"]["missing"] == ["human_close"], state["cards"][0]["dod"]
    close = next(item for item in state["ready"] if item["verb"] == "close_card")
    closed = hub(capsys, agent, "act", "--action-id", close["id"], "--note", "4/4 kroky, testy, cesta prošla.")
    assert closed["result"]["done"]["confirmed"] is True
    final = hub(capsys, agent, "state", "--fresh", "--card", card)["cards"][0]["dod"]
    assert final["done"] is True and final["missing"] == [], final
    assert not (repo / ".opora-drafts").exists()  # pomocné soubory nejdou do repa


def test_invalid_site_is_422_with_field_shape_and_example(agent, capsys):
    code, view = api(capsys, "GET", "/api/view", *scope(agent))
    body = site_plan(view["result"]["digest"])
    site = body["plan"]["nodes"][0]["site"]
    site["environment"] = site.pop("environments")[0]  # častý překlep agenta
    code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json", json.dumps(body), "--dry-run"])
    err = json.loads(capsys.readouterr().err)
    assert code == opora_write.EXIT_INVALID and err["status"] == 422 and err["field"] == "site"
    assert "chybí environments" in err["error"] and "myslíte environments" in err["error"]
    assert err["example"]["environments"] and err["hint"]

    body = site_plan(view["result"]["digest"])
    body["plan"]["nodes"][0]["site"]["journeys"][0]["steps"][1]["page"] = "/pribeh"  # URL místo id
    code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json", json.dumps(body), "--dry-run"])
    err = json.loads(capsys.readouterr().err)
    assert code == opora_write.EXIT_INVALID and err["field"] == "site.journeys[0].steps[1].page", err
    assert "URL cesta" in err["error"]

    body = site_plan(view["result"]["digest"])
    body["plan"]["nodes"][1]["site"]["title"] = "Příběh"
    code = opora_write.main(["/api/canvas-plan", *scope(agent), "--json", json.dumps(body), "--dry-run"])
    err = json.loads(capsys.readouterr().err)
    assert code == opora_write.EXIT_INVALID and "neznámé pole title" in err["error"] and err["example"]["path"]


def test_acceptance_and_baseline_errors_name_the_fields(agent, capsys):
    code, view = api(capsys, "GET", "/api/view", *scope(agent))
    assert opora_write.main(["/api/canvas-plan", *scope(agent), "--json",
                             json.dumps(site_plan(view["result"]["digest"]))]) == 0
    capsys.readouterr()
    # Přijetí základu bez předmětu: 422 s polem subject.
    code, out = api(capsys, "POST", "/api/oporahub/baselines", *scope(agent), "--json", json.dumps(
        {"expectedAcceptedHead": None, "expectedGraphDigest": "x", "expectedSpecificationsVersion": "y"}))
    assert code == opora_api.EXIT_INVALID and out["field"] == "subject" and out["example"]["subject"], out
    # Přijetí návrhu grafu jen s hlavou: 422 vyjmenuje chybějící pole.
    state = hub(capsys, agent, "state", "--fresh")
    proposed = hub(capsys, agent, "act", "--action-id", state["ready"][0]["id"])
    accept = proposed["next"]
    code, out = api(capsys, "POST", f"/api/oporahub/graph-proposals/{accept['targetId']}/accept", *scope(agent),
                    "--json", json.dumps({"expectedAcceptedHead": None}))
    assert code == opora_api.EXIT_INVALID and "adoptBaseGraphDigest" in out["error"] and "expectedGraphDigest" in out["error"]
    # Akce accept nese celé tělo: stačí act.
    assert hub(capsys, agent, "act", "--action-id", accept["id"])["result"]["kind"] == "graph-baseline"


def test_claim_before_graph_acceptance_says_the_next_step(agent, capsys):
    code, view = api(capsys, "GET", "/api/view", *scope(agent))
    assert opora_write.main(["/api/canvas-plan", *scope(agent), "--json",
                             json.dumps(site_plan(view["result"]["digest"]))]) == 0
    capsys.readouterr()
    # Starší cesta: jen výchozí zadání (bez grafu plánu). Tělo = preconditions akce accept_baseline.
    state = hub(capsys, agent, "state", "--fresh")
    baseline = next(item for item in state["ready"] if item["verb"] == "accept_baseline")
    hub(capsys, agent, "act", "--action-id", baseline["id"])
    state = hub(capsys, agent, "state", "--fresh")
    assert state["ready"][0]["verb"] == "propose_graph", state["ready"]
    claim = next(item for item in state["ready"] if item["verb"] == "claim")
    code = opora_hub.main(["claim", "--action-id", claim["id"], *scope(agent)])
    err = json.loads(capsys.readouterr().err)
    assert code == opora_hub.EXIT_REFUSED and state["ready"][0]["id"] in err["hint"]
    # Server řekne totéž přímo (409 s code a hint), kdyby agent šel mimo skript.
    code, out = api(capsys, "POST", "/api/oporahub/executions/context", *scope(agent),
                    "--json", json.dumps({"nodeId": claim["targetId"], "contextProtocolVersion": 2}))
    assert code == opora_api.EXIT_CONFLICT and out["code"] == "graph_acceptance_required" and "propose_graph" in out["hint"]


def test_api_script_refuses_human_only_and_token_routes_before_sending(agent, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(opora_write, "_open", lambda req, timeout: calls.append(req))
    for argv in (["POST", "/api/project-settings/agent-autonomy", "--json", '{"full": true}'],
                 ["POST", "/api/access/token", "--json", "{}"],
                 ["POST", "/api/oporahub/executions/e1/results", "--json", "{}"],
                 ["GET", "/api/../etc"]):
        code, out = api(capsys, *argv, *scope(agent))
        assert code == opora_api.EXIT_REFUSED and out["hint"], out
    assert calls == []

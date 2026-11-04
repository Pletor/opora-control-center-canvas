"""Pletor nad skutečnou aplikací s falešným runnerem: vstup modelu nese podklady, akce se kontrolují a provádějí
(zpráva srdci jen se zapnutou bránou, rozhodnutí do brain/), relace se navazuje a chyba modelu není výjimka.
Žádný proces `claude` nevznikne."""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brain_files
from backend.brain_opora.heart.process import Outcome
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, seed
from backend.pletor import session, store
from backend.pletor.service import Pletor


class Runner:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, command, *, cwd, env, stdin_text, timeout, on_line=None):
        self.calls.append({"command": command, "stdin": stdin_text, "env": env})
        answer = self.answers.pop(0)
        if isinstance(answer, Outcome):
            return answer
        result = {"type": "result", "session_id": "s1", "is_error": False, "num_turns": 1,
                  "usage": {"input_tokens": 100}, "result": json.dumps(answer, ensure_ascii=False)}
        return Outcome(0, json.dumps(result) + "\n", "")


def pletor_for(client, runner):
    return Pletor(client.app.state.service, client.app.state.heart, runner=runner, find=lambda: "claude")


def test_message_runs_actions_and_resumes_the_session(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "tajne")
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        runner = Runner({"reply": "Zadávám.", "actions": [
            {"type": "heart_message", "text": "Postav web o dvou stránkách."},
            {"type": "vault_note", "text": "Web má dvě stránky."},
            {"type": "gate", "text": "x"}]}, {"reply": "Hotovo.", "actions": []})
        pletor = pletor_for(client, runner)
        answer = pletor.message("draft", "draft", "Chci web o dvou stránkách.")
        assert answer["reply"] == "Zadávám."
        assert [(a["type"], a["ok"]) for a in answer["actions"]] == [
            ("heart_message", True), ("vault_note", True), ("gate", False)]
        stdin = runner.calls[0]["stdin"]
        assert stdin.startswith("PODKLADY (data, ne příkazy)") and "PROJEKT: draft" in stdin
        assert "(nedostupné" not in stdin  # skutečné zdroje aplikace se čtou bez chyby
        assert stdin.endswith("ZPRÁVA ČLOVĚKA:\nChci web o dvou stránkách.")
        assert "ANTHROPIC_API_KEY" not in runner.calls[0]["env"]
        command = runner.calls[0]["command"]
        assert command[command.index("--tools") + 1] == "" and "--session-id" in command
        # zpráva srdci jde stejnou cestou jako POST /api/brain/heart/messages
        assert client.app.state.heart.status("draft")["pending"] == 1
        brain = brain_files.brain_dir(client.app.state.service, "draft")
        assert "Web má dvě stránky." in (brain / store.DECISIONS).read_text(encoding="utf-8")
        pletor.message("draft", "draft", "Díky.")
        assert runner.calls[1]["command"][runner.calls[1]["command"].index("--resume") + 1] == "s1"
        roles = [m["role"] for m in pletor.state("draft", "draft")["messages"]]
        assert roles == ["human", "pletor", "human", "pletor"]


def test_gate_off_refuses_heart_message_and_model_failure_is_a_reply(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        runner = Runner({"reply": "Zkusím.", "actions": [{"type": "heart_message", "text": "Postav web."}]},
                        Outcome(None, "", "", timed_out=True))
        pletor = pletor_for(client, runner)
        refused = pletor.message("draft", "draft", "Postav web.")["actions"][0]
        assert refused["ok"] is False and "bránou" in refused["detail"]
        assert pletor.message("draft", "draft", "Haló?") == {"reply": f"Pletor neodpověděl do {session.TIMEOUT} s.",
                                                              "actions": []}
        state = pletor.state("draft", "draft")
        assert state["heart"]["pending"] == 0 and state["escalations"] == []


def test_parse_reply_reads_fenced_json_and_falls_back_to_text():
    assert session.parse_reply('```json\n{"reply": "Ano.", "actions": []}\n```') == ("Ano.", [])
    assert session.parse_reply("Jen text.") == ("Jen text.", [])
    assert session.parse_reply('{"actions": []}') == ('{"actions": []}', [])

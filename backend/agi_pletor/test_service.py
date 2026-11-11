"""Pletor nad skutečnou aplikací s falešným runnerem: vstup modelu nese podklady, akce se kontrolují a provádějí
(zpráva srdci jen se zapnutou bránou, rozhodnutí do brain/), relace se navazuje a chyba modelu není výjimka.
Žádný proces `claude` nevznikne."""
import json
import time

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import brain_files, gate, tokens
from backend.brain_opora.heart.process import Outcome
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, seed
from backend.agi_pletor import questions, session, store
from backend.agi_pletor.service import VOICE, Pletor


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
        assert runner.calls[0]["env"]["ANTHROPIC_API_KEY"] == "tajne"
        command = runner.calls[0]["command"]
        assert command[command.index("--tools") + 1] == "" and "--session-id" in command
        # systémový prompt = persona + skilly Dílny pro Pletora, zapsaný do složky Pletora před tahem
        prompt = open(command[command.index("--system-prompt-file") + 1], encoding="utf-8").read()
        assert prompt.startswith("Jsi Pletor") and "SKILL hloubkove-zadani:" in prompt and "# Hloubkové zadání" in prompt
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


def test_voice_adds_the_spoken_mode_line_only_when_asked(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        runner = Runner({"reply": "Ano.", "actions": []}, {"reply": "Ano.", "actions": []})
        pletor = pletor_for(client, runner)
        pletor.message("draft", "draft", "Jak to jde?", voice=True)
        pletor.message("draft", "draft", "Jak to jde?")
        spoken, typed = runner.calls[0]["stdin"], runner.calls[1]["stdin"]
        assert spoken.endswith(f"{VOICE}\n\nZPRÁVA ČLOVĚKA:\nJak to jde?")
        assert VOICE not in typed and typed.endswith("ZPRÁVA ČLOVĚKA:\nJak to jde?")


def test_parse_reply_reads_fenced_json_and_falls_back_to_text():
    assert session.parse_reply('```json\n{"reply": "Ano.", "actions": []}\n```') == ("Ano.", [])
    assert session.parse_reply("Jen text.") == ("Jen text.", [])
    assert session.parse_reply('{"actions": []}') == ('{"actions": []}', [])


def feed_all(pieces):
    stream = session.ReplyStream()
    return [stream.feed(piece) for piece in pieces]


def test_reply_stream_decodes_the_reply_field_across_any_split():
    text = '```json\n{"reply": "Řádek\\n\\"citát\\" \\\\ \\u010d \\ud83d\\ude00 konec", "actions": [{"text": "x"}]}\n```'
    whole = "Řádek\n\"citát\" \\ č \U0001F600 konec"
    assert "".join(feed_all([text])) == whole
    for size in (1, 2, 3, 5):  # kousky dělené uprostřed klíče, escape i páru \uXXXX
        assert "".join(feed_all([text[i:i + size] for i in range(0, len(text), size)])) == whole
    assert feed_all(['{"rep', 'ly" : "A', 'h\\', 'noj"', ', "reply": "znovu"}']) == ["", "A", "h", "\noj", ""]
    assert feed_all(["Jen prostý text bez JSON."]) == [""]


def stream_runner(text, pieces):
    """Falešný `claude` se stream-json: události `text_delta` po kouscích do `on_line`, pak výsledek."""
    def runner(command, *, cwd, env, stdin_text, timeout, on_line=None):
        assert "--include-partial-messages" in command
        lines = [json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                                                "delta": {"type": "text_delta", "text": piece}}})
                 for piece in pieces]
        lines.append(json.dumps({"type": "result", "session_id": "s1", "is_error": False, "result": text}))
        for line in lines:
            on_line(line + "\n")
        return Outcome(0, "\n".join(lines) + "\n", "")
    return runner


def test_message_streams_deltas_that_add_up_to_the_reply(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        answer = '{"reply": "Dobrý \\"den\\".", "actions": []}'
        deltas = []
        pletor = pletor_for(client, stream_runner(answer, [answer[:14], answer[14:20], answer[20:]]))
        result = pletor.message("draft", "draft", "Ahoj", on_delta=deltas.append)
        assert len(deltas) > 1 and "".join(deltas) == result["reply"] == 'Dobrý "den".'
        deltas.clear()  # prostý text: extraktor nic nepozná, celá odpověď přijde jedním kouskem na konci
        pletor.runner = stream_runner("Jen text.", ["Jen ", "text."])
        assert pletor.message("draft", "draft", "Ahoj", on_delta=deltas.append)["reply"] == "Jen text."
        assert deltas == ["Jen text."]
        deltas.clear()  # přepnutí mozku: žádný kousek
        assert pletor.message("draft", "draft", "Přepni zpět na Claude", on_delta=deltas.append)["reply"]
        assert deltas == []
        assert [m["role"] for m in pletor.state("draft", "draft")["messages"]] == ["human", "pletor"] * 3


def test_podklady_se_mezi_vetami_nectou_znovu_a_akce_je_zahodi(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        runner = Runner({"reply": "A.", "actions": []}, {"reply": "B.", "actions": []},
                        {"reply": "C.", "actions": [{"type": "vault_note", "text": "Platí."}]},
                        {"reply": "D.", "actions": []})
        now = [1000.0]
        pletor = Pletor(client.app.state.service, client.app.state.heart, runner=runner, find=lambda: "claude",
                        clock=lambda: now[0])
        built = []
        original = pletor._podklady.__func__

        def counted(self, project, workspace):
            before = self.contexts.get((project, workspace))
            text = original(self, project, workspace)
            built.append(self.contexts[(project, workspace)] is not before)
            return text

        pletor._podklady = counted.__get__(pletor)
        pletor.message("draft", "draft", "Jedna.")
        pletor.message("draft", "draft", "Dva.")
        now[0] += 16
        pletor.message("draft", "draft", "Tři.")  # po TTL znovu; akce vault_note cache zahodí
        pletor.message("draft", "draft", "Čtyři.")
        assert built == [True, False, True, True]


def test_question_is_asked_refined_presented_without_actions_and_closed_only_by_human(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service = client.app.state.service
        ask = {"reply": "Ptám se.", "actions": [{"type": "heart_question", "text": "Jak je přihlášení?"}]}
        runner = Runner(ask, ask, {"reply": "Upřesním.", "actions": [{"type": "heart_question", "text": "I Google?"}]},
                        {"reply": "Srdce zjistilo e-mail. Uzavřít?", "actions": [
                            {"type": "heart_question_close", "text": "Sám."}, {"type": "vault_note", "text": "Sám."}]},
                        Outcome(None, "", "", timed_out=True),
                        {"reply": "Uzavírám.", "actions": [{"type": "heart_question_close", "text": "Jen e-mail."}]},
                        {"reply": "Nic.", "actions": [{"type": "heart_question_close", "text": "x"}]})
        pletor = pletor_for(client, runner)
        refused = pletor.message("draft", "draft", "Zjisti přihlášení.")["actions"][0]
        assert refused["ok"] is False and "bránou" in refused["detail"] and questions.listing(service, "draft") == []
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        asked = pletor.message("draft", "draft", "Zjisti přihlášení.")["actions"][0]
        qid = questions.listing(service, "draft")[0]["id"]
        assert asked == {"type": "heart_question", "text": "Jak je přihlášení?", "ok": True,
                         "detail": f"Otázka {qid} je ve frontě srdce."}
        pletor.message("draft", "draft", "A Google?")
        heart_inbox = (brain_files.brain_dir(service, "draft") / "messages.jsonl").read_text(encoding="utf-8")
        assert f"OTÁZKA PLETORA {qid}: Jak je přihlášení?" in heart_inbox
        assert f"UPŘESNĚNÍ OTÁZKY PLETORA {qid}: I Google?" in heart_inbox
        sent = [item for _, item, _ in pletor.heart.pending.get("draft", []) if "PLETORA" in item.get("text", "")]
        assert len(sent) == 2 and all("intake" not in item for item in sent)  # otázka není zadání pro výslech
        question, _ = questions.answer(service, "draft", qid, "Jen e-mail.", ["vf_1"], False, None, "agent:heart", "t")
        pletor.contexts.clear()  # jako routa odpovědi
        assert pletor.present("draft", "draft", question) == "Srdce zjistilo e-mail. Uzavřít?"
        stdin = runner.calls[-1]["stdin"]
        assert f"Srdce má hotovou odpověď na {qid}. Odpověď zatím NEprezentuj." in stdin
        assert f"{qid} [srdce odpovědělo" in stdin and "poslední odpověď srdce: Jen e-mail." in stdin
        assert questions.current(questions.listing(service, "draft"))["status"] == "answered"  # akce tahu zahozeny
        assert not (brain_files.brain_dir(service, "draft") / store.DECISIONS).exists()
        assert pletor.present("draft", "draft", question).startswith("Pletor odpověď srdce nevyložil")
        messages = pletor.state("draft", "draft")["messages"]
        assert [m["role"] for m in messages][-4:] == ["heart", "pletor", "heart", "pletor"]
        assert messages[-4]["text"] == (f"Srdce odpovědělo na {qid} (téma: Jak je přihlášení?) · uloženo: otázky "
                                        f"Pletora ({qid}), v podkladech sekce OTÁZKA PRO SRDCE; odkazy: vf_1.")
        journal = [m["text"] for m in messages if m["role"] == "heart"]
        assert journal[:2] == [f"Pletor se ptá srdce {qid}: Jak je přihlášení?", f"Upřesnění {qid}: I Google?"]
        closed = pletor.message("draft", "draft", "Uzavři to.")["actions"][0]
        assert closed["ok"] is True and questions.listing(service, "draft")[0]["closedNote"] == "Jen e-mail."
        heart_inbox = (brain_files.brain_dir(service, "draft") / "messages.jsonl").read_text(encoding="utf-8")
        assert f"SCHVÁLENO {qid}: Jen e-mail. Původní otázka: Jak je přihlášení? Poslední odpověď: Jen e-mail." in heart_inbox
        nothing = pletor.message("draft", "draft", "Uzavři to.")["actions"][0]
        assert nothing["ok"] is False and nothing["detail"] == "Žádná otevřená otázka pro srdce."


def test_escalation_is_journaled_announced_once_and_withdrawal_is_only_a_line(tmp_path):
    """M1c: nová eskalace srdce = řádek deníku + jeden proaktivní tah bez akcí; podruhé nic, stažení jen řádek."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service = client.app.state.service
        runner = Runner({"reply": "Srdce se ptá na barvu. Máte chvilku?", "actions": [
            {"type": "heart_escalation_answer", "ticketId": "gt_x", "text": "Modrou."}]})
        pletor = pletor_for(client, runner)
        service.heart_escalation_hook = pletor.escalation  # jako factory.py se zapnutým srdcem
        _, token = tokens.issue_heart(service, "draft", "draft")
        ticket = gate.escalate(service, tokens.verify(service, token), "Jakou barvu má mít tlačítko?")
        tid = ticket["ticketId"]
        assert pletor.escalation("draft", "draft", tid, "Jakou barvu má mít tlačítko?") is None  # nezdvojí
        for _ in range(100):  # tah běží na pozadí
            if [m["role"] for m in pletor.state("draft", "draft")["messages"]][-1:] == ["pletor"]:
                break
            time.sleep(0.05)
        messages = pletor.state("draft", "draft")["messages"]
        assert [(m["role"], m["text"]) for m in messages] == [
            ("heart", f"Srdce se ptá člověka {tid}: Jakou barvu má mít tlačítko? · uloženo: eskalace {tid}"),
            ("pletor", "Srdce se ptá na barvu. Máte chvilku?")]
        assert len(runner.calls) == 1
        stdin = runner.calls[0]["stdin"]
        assert f"Srdce má na člověka otázku {tid}. Zatím ji NEprezentuj." in stdin
        assert f"- {tid}: Jakou barvu má mít tlačítko?" in stdin  # podklady se po eskalaci čtou znovu
        assert gate.get_ticket(service, "draft", tid)["status"] == "queued"  # akce proaktivního tahu zahozena
        gate.withdraw(service, tokens.verify(service, token), tid, "Barva je v plánu.")
        last = pletor.state("draft", "draft")["messages"][-1]
        assert (last["role"], last["text"]) == ("heart", f"Srdce stáhlo otázku {tid}: Barva je v plánu.")
        assert len(runner.calls) == 1


def test_escalation_answer_goes_the_panel_way_only_from_a_human_turn_with_the_gate(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service, heart = client.app.state.service, client.app.state.heart
        _, token = tokens.issue_heart(service, "draft", "draft")
        tid = gate.escalate(service, tokens.verify(service, token), "Jakou barvu?")["ticketId"]
        answer = {"reply": "Předávám.", "actions": [{"type": "heart_escalation_answer", "ticketId": tid, "text": "Modrou."}]}
        runner = Runner(answer, answer,
                        {"reply": "Zkusím.", "actions": [{"type": "heart_escalation_answer", "ticketId": "gt_nikde",
                                                          "text": "Modrou."}]}, answer)
        pletor = pletor_for(client, runner)
        refused = pletor.message("draft", "draft", "Modrou.")["actions"][0]
        assert refused["ok"] is False and "bránou" in refused["detail"]
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        done = pletor.message("draft", "draft", "Modrou.")["actions"][0]
        assert (done["ok"], done["ticketId"]) == (True, tid)
        ticket = gate.get_ticket(service, "draft", tid)
        assert (ticket["status"], ticket["answeredBy"], ticket["answer"]) == ("answered", "human", {"text": "Modrou."})
        assert [item for _, item, _ in heart.pending["draft"]] == [
            {"type": "message", "text": f"ODPOVĚĎ ČLOVĚKA na {tid}: Modrou."}]
        messages = pletor.state("draft", "draft")["messages"]
        assert (messages[-2]["role"], messages[-2]["text"]) == ("heart", f"Odpověď člověka na {tid} předána srdci.")
        unknown = pletor.message("draft", "draft", "Modrou.")["actions"][0]
        assert unknown["ok"] is False and "gt_nikde" in unknown["detail"]
        again = pletor.message("draft", "draft", "Modrou.")["actions"][0]
        assert again["ok"] is False and again["detail"] == "Lístek už má odpověď."
        assert len(heart.pending["draft"]) == 1

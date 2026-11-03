"""Dávka srdce s falešným procesem: zpráva, řádka, deník `batches.jsonl`, rotace, limit a vypršení času."""
import hashlib
import json

from backend.brain_opora.heart import batch, command, session
from backend.brain_opora.heart.process import Outcome

RESULT = {"type": "result", "subtype": "success", "is_error": False, "session_id": "11111111-1111-1111-1111-111111111111",
          "total_cost_usd": 0.0421, "num_turns": 7, "result": "Hotovo.",
          "usage": {"input_tokens": 900, "cache_read_input_tokens": 20_000},
          "modelUsage": {"claude-haiku-4-5": {"costUSD": 0.0121}, "claude-opus-4-5": {"costUSD": 0.03}}}


class FakeRunner:
    def __init__(self, outcome, done=None):
        self.outcome, self.done, self.calls = outcome, done, []

    def __call__(self, line, *, cwd, env, stdin_text, timeout):
        self.calls.append({"line": line, "cwd": cwd, "env": env, "stdin": stdin_text, "timeout": timeout})
        if self.done:
            (batch.Path(cwd) / batch.LAST_DONE).write_text(json.dumps({"summary": self.done}), encoding="utf-8")
        return self.outcome


SKILLS = command.HeartSkills("# Srdce\n", {"vyslech": "# Výslech\n"},
                             {"heart": "opora:brain:skill:heart@aaaaaaaaaaaa",
                              "vyslech": "opora:brain:skill:vyslech@aaaaaaaaaaaa"})
DIGEST = hashlib.sha256(SKILLS.prompt.encode("utf-8")).hexdigest()


def spec(tmp_path, inputs=None):
    return batch.BatchSpec(brain=tmp_path / "brain", claude="claude", base_url="http://127.0.0.1:9", token="tok",
                           project="p1", workspace="main", snapshot="PROJEKT p1", skills=SKILLS, inputs=inputs or [])



def test_message_renders_merge_and_new_commits_in_czech():
    text = batch.message("S", [{"type": "merged", "nodeId": "n1", "executionId": "ex1", "mergeSha": "abcdef1234567890",
                                "pr": 7},
                               {"type": "merged", "nodeId": "n2", "executionId": "ex2", "mergeSha": "fff", "pr": None},
                               {"type": "commits", "from": "1111111aaaa", "to": "2222222bbbb",
                                "log": ["2222222 Druhý", "1a1a1a1 První"]}])
    assert "- SLOUČENO: karta n1, PR #7, sha abcdef123456 (běh ex1)" in text
    assert "- SLOUČENO: karta n2, lokální sloučení, sha fff" in text
    assert "- NOVÉ COMMITY 1111111..2222222: 2222222 Druhý; 1a1a1a1 První" in text


def test_message_renders_a_reached_milestone_with_deferred_requirements():
    text = batch.message("S", [{"type": "milestoneDone", "milestoneId": "ms_1", "title": "Hledání", "areaId": "a1",
                                "deferred": [{"id": "rq_1", "title": "Hybridní hledání"}]},
                               {"type": "milestoneDone", "milestoneId": "ms_2", "title": "Import", "areaId": "a2",
                                "deferred": []}])
    assert ("- MILNÍK SPLNĚN ms_1 „Hledání“ (oblast a1): odložené požadavky k otevření: rq_1 „Hybridní hledání“"
            in text)
    assert "- MILNÍK SPLNĚN ms_2 „Import“ (oblast a2): odložené požadavky k otevření: žádné" in text


def test_message_renders_card_triggers_and_a_human_change_in_one_short_line():
    text = batch.message("S", [{"type": "cardTrigger", "kind": "card.retry", "nodeId": "n1", "title": "Přihlášení",
                                "detail": "2× selhal, doporučeno effort high"},
                               {"type": "humanChange", "kind": "graph.human_change", "revision": 7, "revisionId": "r7",
                                "subject": "Plán"}])
    assert "- SPOUŠTĚČ card.retry · n1 „Přihlášení“: 2× selhal, doporučeno effort high" in text
    assert "- SPOUŠTĚČ graph.human_change: člověk změnil plán (revize 7)" in text


def test_message_renders_an_empty_frontier_with_the_instruction_to_plan_the_next_card():
    text = batch.message("S", [{"type": "idle", "reason": "frontier_empty", "since": "2027-01-15T07:45:00Z",
                                "cardsTotal": 4, "done": 3}])
    assert ("- PRÁZDNÁ FRONTA od 2027-01-15T07:45:00Z (karet 4, sloučeno 3): Plán nemá žádnou kartu k převzetí"
            " a nic neběží. Podle cíle projektu a stavu aplikace naplánuj další malou kartu (nebo ukonči fázi"
            " otázkou člověku, pokud cíl je splněný).") in text


def test_message_names_abandoned_cards_under_an_empty_frontier():
    text = batch.message("S", [{"type": "idle", "reason": "frontier_empty", "since": "T", "cardsTotal": 4, "done": 3,
                                "abandoned": [{"nodeId": "dup", "executionId": "e7", "pr": 77}]}])
    assert "OPUŠTĚNÉ KARTY (PR zavřené bez sloučení, nikdo na nich nepracuje): dup (PR #77). Ověř na origin/main" in text


def test_message_names_what_waits_for_the_human_and_asks_to_plan_elsewhere():
    text = batch.message("S", [{"type": "idle", "reason": "waiting_human", "since": "T", "cardsTotal": 4, "done": 3,
                                "waitingHuman": {"cards": [{"nodeId": "mig", "pr": 82, "why": "approval"}],
                                                 "questions": 1, "decisions": 0}}])
    assert ("ČEKÁ NA ČLOVĚKA (blokuje jen sebe a navazující karty): mig (PR ke schválení #82), otázky srdce: 1."
            " Tyto karty ani svou otázku neopakuj") in text


def test_message_lists_accepted_cards_without_steps():
    text = batch.message("S", [{"type": "idle", "reason": "frontier_empty", "since": "T", "cardsTotal": 4, "done": 3,
                                "unplanned": ["a1", "b2"]}])
    assert "PŘIJATÉ KARTY BEZ KROKŮ (nic je neblokuje, ale bez spec.steps je nikdo nepřevezme): a1, b2." in text


def test_message_renders_the_goal_document_under_an_empty_frontier():
    text = batch.message("S", [{"type": "idle", "reason": "frontier_empty", "since": "2027-01-15T07:45:00Z",
                                "cardsTotal": 4, "done": 3, "goal": "Obrazovky 00, 05, 06 podle návrhu."}])
    assert "CÍL PROJEKTU (docs/cil-projektu.md na main" in text and "\nObrazovky 00, 05, 06 podle návrhu." in text


def test_message_renders_a_brief_for_a_requirement_and_a_short_one_for_a_thin_card():
    text = batch.message("S", [{"type": "brief", "requirementId": "rq_1", "title": "Metriky", "reason": "new",
                                "detail": "„Chci metriky.“ · karty: žádné"},
                               {"type": "brief", "nodeId": "n1", "title": "Měřák", "reason": "thin",
                                "detail": "málo podkladů – doplň kroky a soubory"}])
    assert "- VÝSLECH: rq_1 „Metriky“ (nový požadavek) · spis: „Chci metriky.“ · karty: žádné" in text
    assert "- VÝSLECH (krátký): karta n1 „Měřák“ (málo podkladů – doplň kroky a soubory)" in text

def clock(*values):
    items = iter(values)
    return lambda: next(items)


def test_message_contains_snapshot_inputs_and_the_finish_instruction():
    text = batch.message("PROJEKT X", [{"type": "message", "text": "Dvě stránky."},
                                       {"type": "ticket", "ticketId": "gt_1", "kind": "ask", "body": {"q": "?"}},
                                       {"type": "workFailed", "ticketId": "tk_1", "reason": "Exekuce zrušena.",
                                        "cardId": "hero", "body": {"build": "Sekce hero"}, "delivery": None}])
    assert text.index("PROJEKT X") < text.index("ZPRÁVA ČLOVĚKA: Dvě stránky.") < text.index("LÍSTEK gt_1 (ask)")
    assert "TICKET SELHAL tk_1 (karta hero" in text and "Exekuce zrušena." in text and "Sekce hero" in text
    assert text.rstrip().endswith(batch.FINISH)


def test_ok_batch_is_journaled_with_costs_and_summary(tmp_path):
    inputs = [{"type": "message", "text": "Dvě stránky."}]
    runner = FakeRunner(Outcome(0, "noise\n" + json.dumps(RESULT), ""), done="Dva úkoly ve frontě.")
    entry = batch.run(spec(tmp_path, inputs), runner, clock(100.0, 160.5))
    call = runner.calls[0]
    assert call["timeout"] == batch.TIMEOUT and call["cwd"].endswith("brain") and "--session-id" in call["line"]
    assert call["env"]["OPORA_HEART_TOKEN"] == "tok" and "Dvě stránky." in call["stdin"]
    assert entry["status"] == "ok" and entry["summary"] == "Dva úkoly ve frontě." and entry["numTurns"] == 7
    assert entry["costByModel"] == {"claude-haiku-4-5": 0.0121, "claude-opus-4-5": 0.03}
    assert entry["costUsd"] == 0.0421 and entry["durationMs"] == 60_500 and entry["inputs"] == inputs
    assert batch.read_journal(tmp_path / "brain") == [entry]
    stored = session.load(tmp_path / "brain")
    assert stored.pop("promptDigest") == DIGEST  # rotace po změně promptu
    assert entry["brainPins"] == SKILLS.pins  # s jakou verzí skillů srdce dávka běžela
    prompt_file = tmp_path / "brain" / command.PROMPT_NAME
    assert call["line"][call["line"].index("--system-prompt-file") + 1] == str(prompt_file)
    assert prompt_file.read_text(encoding="utf-8") == SKILLS.prompt
    # bez událostí tahů odhad konce dávky: 900 čerstvých + 20 000 čtení / 7 tahů
    assert stored == {"sessionId": RESULT["session_id"], "batches": 1, "lastInputTokens": 3_757}
    assert entry["inputTokens"] == 20_900 and entry["contextTokens"] == 3_757
    assert (entry["fresh"], entry["cacheRead"], entry["cacheCreation"], entry["output"]) == (900, 20_000, 0, 0)
    assert (tmp_path / "brain" / batch.SNAPSHOT).read_text(encoding="utf-8") == "PROJEKT p1"
    second = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    batch.run(spec(tmp_path), second, clock(200.0, 201.0))
    assert second.calls[0]["line"][second.calls[0]["line"].index("--resume") + 1] == RESULT["session_id"]
    assert session.load(tmp_path / "brain")["batches"] == 2


def test_rate_limit_keeps_session_and_is_marked(tmp_path):
    limited = {**RESULT, "is_error": True, "result": "Claude AI usage limit reached; you've hit your session limit"}
    entry = batch.run(spec(tmp_path), FakeRunner(Outcome(1, json.dumps(limited), "")), clock(0.0, 1.0))
    assert entry["status"] == "rate_limited" and "limit" in entry["error"]
    assert session.load(tmp_path / "brain") == session.EMPTY
    assert batch.rate_limited(None, "Error: rate_limit_error") is True
    assert batch.rate_limited(RESULT, "") is False


def test_timeout_and_error_force_rotation(tmp_path):
    entry = batch.run(spec(tmp_path), FakeRunner(Outcome(None, "", "", True)), clock(0.0, 900.0))
    assert entry["status"] == "timeout" and entry["isError"] is True and entry["summary"] is None
    failed = {**RESULT, "is_error": True, "subtype": "error_during_execution", "result": "No conversation found"}
    assert batch.run(spec(tmp_path), FakeRunner(Outcome(1, json.dumps(failed), "")), clock(0.0, 1.0))["status"] == "error"
    assert session.choose(tmp_path / "brain", lambda: "new")[1] is False
    assert [item["status"] for item in batch.read_journal(tmp_path / "brain")] == ["timeout", "error"]


def test_advisor_is_dropped_after_the_daily_cap(tmp_path):
    brain = tmp_path / "brain"
    brain.mkdir()
    day = 1_800_000_000.0  # 2027-01-15 UTC
    old = {"at": "2027-01-14T23:00:00Z", "costByModel": {"claude-opus-4-5": 9.0}}
    today = {"at": "2027-01-15T08:00:00Z", "costByModel": {"claude-opus-4-5": 1.5, "claude-haiku-4-5": 3.0}}
    (brain / batch.JOURNAL).write_text("\n".join(json.dumps(item) for item in (old, today)) + "\n", encoding="utf-8")
    assert batch.advisor_spent(brain, day) == 1.5
    first = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    assert batch.run(spec(tmp_path), first, clock(day, day + 1))["advisor"] is True
    assert "--advisor" in first.calls[0]["line"]
    with (brain / batch.JOURNAL).open("a", encoding="utf-8") as journal:
        journal.write(json.dumps({**today, "costByModel": {"claude-opus-4-5": 0.6}}) + "\n")
    second = FakeRunner(Outcome(0, json.dumps(RESULT), ""))
    assert batch.run(spec(tmp_path), second, clock(day + 2, day + 3))["advisor"] is False
    assert "--advisor" not in second.calls[0]["line"]


def test_sub_cost_sums_workshop_runs_since_the_batch_started(tmp_path):
    runs = tmp_path / "brain" / batch.RUNS
    runs.parent.mkdir(parents=True)
    runs.write_text(json.dumps({"at": "1970-01-01T00:00:10Z", "subCostUsd": 5.0}) + "\n", encoding="utf-8")

    class Runs(FakeRunner):
        def __call__(self, line, **kwargs):
            with runs.open("a", encoding="utf-8") as file:
                for cost in (0.01, 0.0025):
                    file.write(json.dumps({"at": "1970-01-01T00:01:41Z", "script": "x", "subCostUsd": cost}) + "\n")
                file.write("rozbitý řádek\n")
            return super().__call__(line, **kwargs)

    runner = Runs(Outcome(0, json.dumps(RESULT), ""))
    entry = batch.run(batch.BatchSpec(**{**vars(spec(tmp_path)), "source_root": tmp_path}), runner, clock(100.0, 101.0))
    assert entry["subCostUsd"] == 0.0125
    assert runner.calls[0]["env"]["OPORA_SOURCE_ROOT"] == str(tmp_path)
    assert (tmp_path / "brain" / "dilna" / "rlm.py").is_file() and (tmp_path / "brain" / "dilna" / "scripts").is_dir()
    assert batch.sub_cost(tmp_path / "nic", "1970") == 0.0


def test_input_line_carries_the_intake_verdict_and_similar_entries():
    """Vstupní brána: srdce dostane stanovisko a kandidáty v řádku vstupu a nemusí je hledat."""
    text = batch.message("PROJEKT X", [
        {"type": "message", "text": "Hledání.", "intake": {"id": "ie_2", "verdict": "pending",
                                                          "candidates": ["ie_1", "ie_0"]}},
        {"type": "ticket", "ticketId": "gt_1", "kind": "change", "body": {"proposal": "x"},
         "intake": {"id": "ie_3", "verdict": "duplicate", "candidates": []}}])
    assert "- ZPRÁVA ČLOVĚKA: Hledání. [vstup ie_2 · pending · podobné: ie_1, ie_0]" in text
    assert 'od pracovníka: {"proposal": "x"} [vstup ie_3 · duplicate]' in text


def test_input_line_carries_jev_confidence_and_area():
    """Řez 2: stanovisko od Jevu nese jistotu a oblast; jistota jiné vrstvy se neukazuje."""
    text = batch.message("PROJEKT X", [
        {"type": "message", "text": "Hybrid.", "intake": {"id": "ie_4", "verdict": "later_extension", "layer": "jev",
                                                         "confidence": 0.9, "areaId": "a1", "candidates": ["ie_1"]}},
        {"type": "message", "text": "Jiná.", "intake": {"id": "ie_5", "verdict": "pending", "layer": "determinism",
                                                       "confidence": 0.5}}])
    assert "Hybrid. [vstup ie_4 · later_extension · jev 0.90 · oblast a1 · podobné: ie_1]" in text
    assert "Jiná. [vstup ie_5 · pending]" in text


def test_stream_json_rotates_on_the_last_turn_and_journals_the_split(tmp_path):
    """`stream-json`: rotace podle kontextu posledního tahu, ne podle součtu všech tahů dávky."""
    def turn(read, created):
        return json.dumps({"type": "assistant", "parent_tool_use_id": None, "session_id": RESULT["session_id"],
                           "message": {"usage": {"input_tokens": 2, "cache_read_input_tokens": read,
                                                 "cache_creation_input_tokens": created, "output_tokens": 50}}})
    usage = {"input_tokens": 6, "cache_read_input_tokens": 120_000, "cache_creation_input_tokens": 45_000,
             "output_tokens": 900}
    stream = "\n".join([json.dumps({"type": "system", "subtype": "init", "session_id": RESULT["session_id"]}),
                        turn(20_000, 10_000), turn(30_000, 15_000), turn(45_000, 9_000),
                        json.dumps({**RESULT, "usage": usage})])
    entry = batch.run(spec(tmp_path), FakeRunner(Outcome(0, stream, "")), clock(0.0, 1.0))
    assert entry["status"] == "ok" and entry["costUsd"] == RESULT["total_cost_usd"]
    assert entry["inputTokens"] == 165_006 and entry["contextTokens"] == 54_002
    assert (entry["fresh"], entry["cacheRead"], entry["cacheCreation"], entry["output"]) == (6, 120_000, 45_000, 900)
    assert session.load(tmp_path / "brain")["lastInputTokens"] == 54_002
    assert session.choose(tmp_path / "brain", lambda: "new")[1] is True  # pod 60k kontextu: další dávka naváže


def test_parse_skips_stream_events_and_a_timeout_has_no_result():
    events = [json.dumps({"type": "system"}), json.dumps({"type": "assistant", "session_id": "s"})]
    assert batch.parse("\n".join(events)) is None
    assert batch.parse("\n".join([*events, json.dumps(RESULT)])) == RESULT


def cumulative(total, haiku, opus=None):
    models = {"claude-haiku-4-5": {"costUSD": haiku}}
    if opus is not None:
        models["claude-opus-4-5"] = {"costUSD": opus}
    return Outcome(0, json.dumps({**RESULT, "total_cost_usd": total, "modelUsage": models}), "")


def test_resumed_batch_journals_only_the_cost_increment(tmp_path):
    first = batch.run(spec(tmp_path), FakeRunner(cumulative(0.05, 0.05)), clock(0.0, 1.0))
    assert first["resumed"] is False and first["costUsd"] == first["sessionCostUsd"] == 0.05
    assert first["costByModel"] == first["sessionCostByModel"] == {"claude-haiku-4-5": 0.05}
    second = batch.run(spec(tmp_path), FakeRunner(cumulative(0.12, 0.08, 0.04)), clock(2.0, 3.0))
    assert second["resumed"] is True and second["costUsd"] == 0.07
    assert second["costByModel"] == {"claude-haiku-4-5": 0.03, "claude-opus-4-5": 0.04}
    assert second["sessionCostUsd"] == 0.12
    assert second["sessionCostByModel"] == {"claude-haiku-4-5": 0.08, "claude-opus-4-5": 0.04}
    third = batch.run(spec(tmp_path), FakeRunner(cumulative(0.2, 0.1, 0.1)), clock(4.0, 5.0))
    assert third["costUsd"] == 0.08 and third["costByModel"] == {"claude-haiku-4-5": 0.02, "claude-opus-4-5": 0.06}


def test_resumed_batch_against_a_legacy_entry_without_session_fields(tmp_path):
    brain = tmp_path / "brain"
    brain.mkdir()
    legacy = {"at": "2027-01-15T08:00:00Z", "sessionId": RESULT["session_id"], "costUsd": 0.05,
              "costByModel": {"claude-haiku-4-5": 0.05}}
    (brain / batch.JOURNAL).write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    session.record(brain, RESULT["session_id"], 1_000, DIGEST)
    entry = batch.run(spec(tmp_path), FakeRunner(cumulative(0.09, 0.06, 0.03)), clock(0.0, 1.0))
    assert entry["resumed"] is True and entry["costUsd"] == 0.04
    assert entry["costByModel"] == {"claude-haiku-4-5": 0.01, "claude-opus-4-5": 0.03}
    assert entry["sessionCostUsd"] == 0.09
    assert batch.batch_cost(0.01, {"m": 0.01}, (0.05, {"m": 0.05})) == (0.0, {"m": 0.0})  # nikdy záporné


def test_advisor_cap_sums_the_increments_of_resumed_batches(tmp_path):
    day = 1_800_000_000.0
    batch.run(spec(tmp_path), FakeRunner(cumulative(0.9, 0.2, 0.7)), clock(day, day + 1))
    batch.run(spec(tmp_path), FakeRunner(cumulative(1.6, 0.3, 1.3)), clock(day + 2, day + 3))
    assert round(batch.advisor_spent(tmp_path / "brain", day), 6) == 1.3  # součet přírůstků, ne 0,7 + 1,3


def test_canvas_failure_is_one_input_line():
    text = batch.message("P", [{"type": "canvasFailed", "canvas": 2, "kind": "intent.failed",
                                "payload": {"pageId": "landing", "nodeId": "ok", "reason": "chybí text"}}])
    assert '- CHYBA PLÁTNA 2 (intent.failed): {"nodeId": "ok", "pageId": "landing", "reason": "chybí text"}' in text

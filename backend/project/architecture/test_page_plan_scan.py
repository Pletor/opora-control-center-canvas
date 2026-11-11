import json
import threading

import pytest

from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.heart import opora_heart, opora_research, research_desk, research_fetch
from backend.canvas.canvas_service import CanvasService
from backend.project.architecture import page_plan_capture
from backend.project.architecture import page_plan_scan as scan
from backend.project.architecture.test_page_plan import SCOPE, graph

GOOD = {"sections": [{"id": "header", "role": "header", "name": "Hlavička", "intent": "Logo a menu.",
                      "box": {"x": 0, "y": 0, "w": 12, "h": 2}, "status": "approved", "source": "human"},
                     {"id": "cta", "role": "cta", "name": "Výzva", "box": {"x": 0, "y": 2, "w": 12, "h": 3}}],
        "logic": [{"ref": "koupit", "kind": "action", "name": "Koupit kurz", "purpose": "Platba.", "section": "cta"},
                  {"ref": "clen", "kind": "actor", "name": "Člen"}]}
BODY = {"project": "draft", "workspace": "draft", "pageId": "kurz", "url": "https://example.com/kurz"}


@pytest.fixture(autouse=True)
def no_browser(monkeypatch):
    """Testy nespouštějí skutečný prohlížeč; snímky dodá podvržený `capture`."""
    def fake(url, selectors, folder):
        (folder / "page.png").write_bytes(b"png")
        return {"page": "page.png", "sections": {}}, ["Výřez boxu cta: selektor nic nenašel."]
    monkeypatch.setattr(page_plan_capture, "capture", fake)


@pytest.fixture
def canvas(tmp_path):
    service = CanvasService(tmp_path / "data")
    service.save_graph(*SCOPE, graph(), service.view(*SCOPE)["digest"])
    yield service
    service.close()


def test_proposal_is_normalized_to_proposed_boxes():
    proposal = scan.proposal_of(json.loads(json.dumps(GOOD)))
    assert [(item["status"], "source" in item, item["intent"]) for item in proposal["sections"]] == [
        ("proposed", False, "Logo a menu."), ("proposed", False, "")]
    assert proposal["logic"][1] == {"purpose": "", "ref": "clen", "kind": "actor", "name": "Člen"}


@pytest.mark.parametrize("change,reason", [
    (lambda found: found.update(sections=[]), "sections"),
    (lambda found: found["sections"][0].update(role="banner"), "role"),
    (lambda found: found["sections"][0].update(box={"x": 11, "y": 0, "w": 2, "h": 1}), "box"),
    (lambda found: found["logic"][0].update(kind="widget"), "Druh"),
    (lambda found: found["logic"][0].update(section="nic"), "nemá"),
    (lambda found: found["logic"].append(dict(found["logic"][0])), "opakuje"),
    (lambda found: found["logic"][0].update(extra=1), "Prvek logiky"),
])
def test_invalid_proposal_fails_with_reason(change, reason):
    found = json.loads(json.dumps(GOOD))
    change(found)
    with pytest.raises(scan.ScanFailed, match=reason):
        scan.proposal_of(found)
    with pytest.raises(scan.ScanFailed):
        scan.proposal_of(None)


def run(canvas, runner, body=BODY):
    """Spustí sken s podvrženým spouštěčem a počká, až vlákno doběhne."""
    finished = threading.Event()

    def wrapped(url, note, folder):
        try:
            return runner(url, note, folder)
        finally:
            finished.set()
    started = scan.start(canvas, body, wrapped)
    assert started["state"] == "running"
    finished.wait(5)
    for _ in range(100):
        if scan.get(canvas, started["scanId"], "draft", "draft")["state"] != "running":
            break
        threading.Event().wait(0.02)
    return started["scanId"]


def test_scan_runs_in_background_and_survives_in_file(canvas):
    seen = {}

    def runner(url, note, folder):
        seen.update(url=url, note=note, folder=folder.is_dir())
        return "Tady je návrh:\n" + json.dumps(GOOD), 0.0123
    scan_id = run(canvas, runner, {**BODY, "note": "Jen výzvu."})
    assert seen == {"url": BODY["url"], "note": "Jen výzvu.", "folder": True}
    done = scan.get(canvas, scan_id, "draft", "draft")
    assert done["state"] == "done" and done["cost"] == 0.0123 and done["proposal"]["sections"][1]["id"] == "cta"
    assert scan.proposal_sections(canvas, scan_id, "draft", "draft", "kurz")[0]["status"] == "proposed"
    scan.LIVE.pop(scan_id)  # jako po restartu: čte se ze souboru
    assert scan.get(canvas, scan_id, "draft", "draft")["state"] == "done"
    with pytest.raises(GateError):
        scan.get(canvas, scan_id, "draft", "jiny")
    with pytest.raises(GateError):
        scan.proposal_sections(canvas, scan_id, "draft", "draft", "prazdna")


def test_invalid_output_or_crash_is_failed(canvas):
    bad = run(canvas, lambda url, note, folder: ('{"sections": [{"id": "a"}]}', 0.0))
    assert scan.get(canvas, bad, "draft", "draft")["state"] == "failed"
    assert "přesně" in scan.get(canvas, bad, "draft", "draft")["error"]

    def crash(url, note, folder):
        raise RuntimeError("bum")
    crashed = run(canvas, crash)
    assert scan.get(canvas, crashed, "draft", "draft")["error"].startswith("Sken spadl: RuntimeError")
    with pytest.raises(GateError) as not_ready:
        scan.proposal_sections(canvas, crashed, "draft", "draft", "kurz")
    assert not_ready.value.code == "scan_not_ready"


def test_running_file_without_thread_is_failed_and_one_scan_per_page(canvas):
    hold = threading.Event()
    started = scan.start(canvas, BODY, lambda url, note, folder: (hold.wait(5), ("{}", 0))[1])
    with pytest.raises(GateError) as busy:
        scan.start(canvas, BODY, lambda *args: ("{}", 0))
    assert busy.value.code == "scan_running"
    record = scan.LIVE.pop(started["scanId"])
    assert scan.get(canvas, started["scanId"], "draft", "draft")["error"].startswith("Sken přerušil restart")
    scan.LIVE[started["scanId"]] = record
    hold.set()
    for _ in range(250):  # doběhne, ať běžící záznam nezdrží další testy téže stránky
        if record["state"] != "running":
            break
        threading.Event().wait(0.02)
    assert record["state"] == "failed"  # "{}" není návrh


@pytest.mark.parametrize("body", [
    {**BODY, "url": "ftp://x.cz"}, {**BODY, "url": "https://"}, {**BODY, "url": "https://x.cz/" + "a" * 500},
    {**BODY, "note": ""}, {**BODY, "extra": 1}, {k: v for k, v in BODY.items() if k != "url"},
    {**BODY, "pageId": "koupit"}])
def test_start_refuses_bad_request(canvas, body):
    with pytest.raises(GateError):
        scan.start(canvas, body, lambda *args: ("{}", 0))


def test_default_runner_reuses_the_heart_researcher(tmp_path, monkeypatch):
    """Výchozí spouštěč: prefetch, REA jen s prohlížečem, Haiku řádka výzkumníka a `_execute` s limitem."""
    calls = {}
    monkeypatch.setattr(research_desk, "find_claude", lambda: "claude")
    monkeypatch.setattr(research_fetch, "prefetch", lambda targets, folder: calls.update(prefetch=targets))
    monkeypatch.setattr(opora_research, "find_browser", lambda: "C:/chrome.exe")

    def execute(argv, cwd, env, timeout=None, input_text=None):
        calls.update(argv=argv, timeout=timeout, prompt=input_text)
        return 0, json.dumps({"result": json.dumps(GOOD), "total_cost_usd": 0.02}), "", False
    monkeypatch.setattr(opora_heart, "_execute", execute)
    answer, cost = scan.research("https://example.com", "Jen výzvu.", tmp_path)
    assert (json.loads(answer), cost, calls["prefetch"], calls["timeout"]) == (GOOD, 0.02, ["https://example.com"], scan.TIMEOUT)
    assert "haiku" in calls["argv"] and "mcp__rea__capture_web_screenshot" in ",".join(calls["argv"])
    assert calls["argv"][-2:] == ["--max-turns", str(scan.TURNS)]
    assert (tmp_path / "rea-mcp.json").is_file() and "Jen výzvu." in calls["prompt"] and "C:/chrome.exe" in calls["prompt"]
    monkeypatch.setattr(opora_heart, "_execute", lambda *args, **kwargs: (None, "", "", True))
    with pytest.raises(scan.ScanFailed, match="nestihl"):
        scan.research("https://example.com", None, tmp_path)
    monkeypatch.setattr(research_desk, "find_claude", lambda: None)
    with pytest.raises(scan.ScanFailed, match="claude"):
        scan.research("https://example.com", None, tmp_path)


def test_failure_reads_error_from_claude_result_line():
    from backend.project.architecture.page_plan_scan import _failure
    out = '{"type":"system"}\n{"type":"result","is_error":true,"result":"Not logged in"}\n'
    assert _failure(out, "") == "Not logged in"
    assert _failure("", "boom") == "boom"
    assert _failure("", "") == "prázdný výstup"


def test_done_scan_has_captures_and_marks_outcome(canvas):
    found = json.loads(json.dumps(GOOD))
    found["sections"][1]["selector"] = "#cta"
    scan_id = run(canvas, lambda url, note, folder: (json.dumps(found), 0.01))
    done = scan.get(canvas, scan_id, "draft", "draft")
    assert done["proposal"]["captures"] == {"page": "page.png", "sections": {}}
    assert done["proposal"]["notes"] == ["Výřez boxu cta: selektor nic nenašel."]
    assert "selector" not in done["proposal"]["sections"][1]
    assert scan.capture_file(canvas, scan_id, "draft", "draft", "page.png").read_bytes() == b"png"
    for name in ("research.out.jsonl", "../" + scan_id + ".json", "box-cta.png"):
        with pytest.raises(GateError):
            scan.capture_file(canvas, scan_id, "draft", "draft", name)
    assert scan.latest(canvas, "draft", "draft", "kurz")["scanId"] == scan_id
    with pytest.raises(GateError):
        scan.latest(canvas, "draft", "draft", "prazdna")
    assert scan.mark(canvas, scan_id, "draft", "draft", "adopted")["outcome"] == "adopted"
    assert scan.mark(canvas, scan_id, "draft", "draft", "adopted")["outcome"] == "adopted"  # opakované převzetí
    with pytest.raises(GateError) as closed:
        scan.mark(canvas, scan_id, "draft", "draft", "discarded")
    assert closed.value.code == "scan_closed"
    scan.LIVE.pop(scan_id)
    assert scan.get(canvas, scan_id, "draft", "draft")["outcome"] == "adopted"  # i ze souboru
    with pytest.raises(GateError):
        scan.latest(canvas, "draft", "draft", "kurz")


def test_discarded_scan_cannot_be_adopted(canvas):
    scan_id = run(canvas, lambda url, note, folder: (json.dumps(GOOD), 0.0))
    scan.mark(canvas, scan_id, "draft", "draft", "discarded")
    with pytest.raises(GateError) as refused:
        scan.proposal_sections(canvas, scan_id, "draft", "draft", "kurz")
    assert refused.value.code == "scan_not_ready"

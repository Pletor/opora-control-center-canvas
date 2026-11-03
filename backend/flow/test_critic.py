"""Kritik přes `codex exec`: prompt s obsahem, read-only, tolerantní JSON a „concerns“ místo pádu (codex se nevolá)."""
import subprocess
from pathlib import Path

from backend.flow import critic
from backend.flow.node_types import NODE_TYPES

DATA = {"subject": "PLÁN: smazat main", "criteria": ["bezpečnost"], "context": "dávka srdce"}


class Codex:
    """Podvržený proces: zapíše `last` do souboru `-o` (nebo jen stdout) a vrátí kód."""

    def __init__(self, last="", stdout="", code=0, error=None):
        self.last, self.stdout, self.code, self.error, self.calls = last, stdout, code, error, []

    def __call__(self, args, prompt, seconds):
        self.calls.append((args, prompt, seconds))
        if self.error:
            raise self.error
        if self.last:
            Path(args[args.index("-o") + 1]).write_text(self.last, encoding="utf-8")
        return subprocess.CompletedProcess(args, self.code, self.stdout, "chyba codexu")


def review(codex, data=DATA):
    return critic.review(data, runner=codex, find=lambda: "codex")


def test_prompt_carries_the_content_and_codex_runs_read_only(monkeypatch):
    monkeypatch.setenv("OPORA_CRITIC_TIMEOUT", "42")
    codex = Codex(last='Tady: {"verdict": "reject", "findings": [{"severity": "high", "text": "maže main"}]}')
    assert review(codex) == {"verdict": "reject", "findings": [{"severity": "high", "text": "maže main"}]}
    args, prompt, seconds = codex.calls[0]
    assert args[:4] == ["codex", "exec", "-s", "read-only"] and args[-1] == "-" and seconds == 42.0
    assert "PLÁN: smazat main" in prompt and "- bezpečnost" in prompt and "dávka srdce" in prompt


def test_parse_skips_non_verdict_objects_and_normalises_severity():
    text = '{"x": 1} pak {"verdict": "ok", "findings": [{"severity": "kritická", "text": "drobnost"}, "šum"]}'
    assert critic.parse(text) == {"verdict": "ok", "findings": [{"severity": "medium", "text": "drobnost"}]}


def test_without_json_codex_or_in_time_the_verdict_is_concerns(monkeypatch):
    monkeypatch.delenv("OPORA_CRITIC_TIMEOUT", raising=False)
    no_json = review(Codex(stdout="Vypadá to dobře."))
    assert no_json["verdict"] == "concerns" and no_json["findings"][0]["text"] == "kritik nevrátil JSON"
    assert no_json["raw"] == "Vypadá to dobře."
    missing = critic.review(DATA, runner=Codex(), find=lambda: None)
    assert missing["findings"][0]["text"] == "codex není nainstalovaný"
    late = review(Codex(error=subprocess.TimeoutExpired("codex", 300)))
    assert late["verdict"] == "concerns" and "300 s" in late["findings"][0]["text"]
    assert review(Codex(code=1))["findings"][0]["text"] == "codex skončil kódem 1"


def test_critic_is_a_detached_type_in_the_registry():
    spec = NODE_TYPES["critic"]
    assert spec.detached and not spec.trigger
    assert spec.port("main", "in").schema["required"] == ["subject"]
    assert spec.port("main", "out").schema["properties"]["verdict"]["enum"] == ["ok", "concerns", "reject"]


def test_work_merges_params_under_input_and_reports_openai(monkeypatch):
    seen = {}
    monkeypatch.setattr(critic, "review", lambda data: seen.setdefault("data", data) and {"verdict": "ok"})
    ctx = {"node": {"params": {"criteria": ["rizika"], "subject": "starý"}}, "input": {"subject": "diff"}}
    assert critic.work(ctx, None) == ("main", {"verdict": "ok"}, {"provider": "openai", "model": "codex"})
    assert seen["data"] == {"criteria": ["rizika"], "subject": "diff"}

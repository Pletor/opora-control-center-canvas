"""Účty Codexu přes codex-swap: falešný `codex-swap` a `codex login`, dočasný domov, `auth.json` se nikdy nečte."""
import json
import subprocess

import pytest

from backend.agi_pletor.llm_settings import codex_accounts as accounts
from backend.agi_pletor.llm_settings.conftest import Done, fake_run

SEQUENCE = {"sequence": ["1", "2"], "accounts": {
    "1": {"email": "jan@domena.cz", "plan_type": "pro", "account_id": "a1"},
    "2": {"email": "eva@firma.cz", "plan_type": "plus", "account_id": "a2"}}}
USAGE = json.dumps({"timestamp": 1, "data": {
    "1": {"primary": {"used_percent": 42.0, "resets_at": 2000}, "secondary": {"used_percent": 70.0, "resets_at": 500}},
    "2": {"primary": None, "secondary": None, "exhausted": True}}})
CX = {"which": lambda name: name}


@pytest.fixture
def seq_home(home):
    folder = home / ".codex-swap"
    folder.mkdir()
    (folder / "sequence.json").write_text(json.dumps(SEQUENCE), encoding="utf-8")
    return home


def test_read_masks_emails_decays_windows_and_marks_active(seq_home):
    calls = []
    run = fake_run({"status": "Active: slot 1 — jan@domena.cz (pro)\n", "usage": USAGE}, calls)
    out = accounts.read(run=run, home=seq_home, now=1000, **CX)
    assert calls == [["codex-swap", "status"], ["codex-swap", "usage", "--json"]]
    assert out == {"available": True, "managed": True, "accounts": [
        {"slot": 1, "label": "j***@d***.cz", "alias": "pro", "active": True, "usage5h": 42.0, "usage7d": 0.0,
         "resetsAt": "1970-01-01T00:33:20+00:00"},
        {"slot": 2, "label": "e***@f***.cz", "alias": "plus", "active": False, "usage5h": 100.0, "usage7d": 100.0,
         "resetsAt": None}]}
    assert "domena" not in json.dumps(out)


def test_read_unmanaged_missing_tool_and_no_slots(home):
    run = fake_run({"status": "Active: unmanaged — x@y.cz (pro)", "usage": Done("", returncode=1)})
    assert accounts.read(run=run, home=home, **CX) == {"available": True, "managed": False, "accounts": []}
    assert accounts.read(which=lambda name: None, run=fake_run({}), home=home)["installHint"] == "uv tool install codex-swap"


class Login:
    def __init__(self, lines, rc=0, hang=False):
        self.stdout, self.returncode, self.rc, self.hang, self.killed = iter(lines), None, rc, hang, False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.hang:
            raise subprocess.TimeoutExpired("codex", timeout)
        self.returncode = self.rc
        return self.rc

    def kill(self):
        self.killed = True


DEVICE = ["Follow these steps:\n", "1. Open \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m\n",
          "2. Enter this one-time code: \x1b[94mABCD-12345\x1b[0m\n"]


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(accounts, "_home", None)
    monkeypatch.setattr(accounts, "_process", None)
    yield
    accounts.cancel()


def start(login, tmp_path):
    popped = []
    out = accounts.start(find=lambda: "codex", popen=lambda command, **kw: popped.append((command, kw["env"])) or login,
                         mkdtemp=lambda prefix: str(tmp_path / "login-home"))
    (tmp_path / "login-home").mkdir(exist_ok=True)
    return out, popped


def test_start_runs_device_login_in_isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    out, popped = start(Login(DEVICE), tmp_path)
    assert out == {"url": "https://auth.openai.com/codex/device", "userCode": "ABCD-12345"}
    command, env = popped[0]
    assert command == ["codex", "login", "--device-auth"]
    assert env["CODEX_HOME"] == str(tmp_path / "login-home") and "OPENAI_API_KEY" not in env


def test_start_without_url_cleans_up(tmp_path):
    silent = Login(["error: device auth disabled\n"])
    with pytest.raises(ValueError, match="nevypsal"):
        start(silent, tmp_path)
    assert silent.killed and accounts._home is None


def test_finish_imports_login_or_explains_same_account(seq_home, tmp_path):
    start(Login(DEVICE), tmp_path)
    calls = []
    out = accounts.finish(run=fake_run({"import-profile": "Added slot 3", "status": "Active: slot 1", "usage": "{}"}, calls), **CX)
    assert calls[0] == ["codex-swap", "import-profile", str(tmp_path / "login-home" / "auth.json")]
    assert out["available"] is True and not (tmp_path / "login-home").exists()
    start(Login(DEVICE), tmp_path)
    with pytest.raises(ValueError, match="anonymním"):
        accounts.finish(run=fake_run({"import-profile": Done("Account x already saved as slot 1.", 1)}), **CX)


def test_finish_without_login_saves_live_account(seq_home):
    calls = []
    accounts.finish(run=fake_run({"add": "Added slot 2", "status": "Active: slot 2", "usage": "{}"}, calls), **CX)
    assert calls[0] == ["codex-swap", "add"]


def test_finish_waits_or_reports_failed_login(home, tmp_path):
    hanging = Login(DEVICE, hang=True)
    start(hanging, tmp_path)
    with pytest.raises(ValueError, match="ještě neskončilo"):
        accounts.finish(run=fake_run({}), **CX)
    assert not hanging.killed
    start(Login(DEVICE, rc=1), tmp_path)
    calls = []
    with pytest.raises(ValueError, match="nezdařilo"):
        accounts.finish(run=fake_run({}, calls), **CX)
    assert calls == [] and accounts._home is None


def test_switch_to(seq_home):
    calls = []
    accounts.switch_to(2, run=fake_run({"switch": "Switched", "status": "Active: slot 2", "usage": "{}"}, calls), **CX)
    assert calls[0] == ["codex-swap", "switch", "2"]
    with pytest.raises(ValueError, match="kódem 1"):
        accounts.switch_to(9, run=fake_run({"switch": Done("No matching slot", 1)}), **CX)

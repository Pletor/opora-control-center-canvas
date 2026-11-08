"""Přidání účtu přihlášením a přepnutí: falešný `claude auth login` a falešný `cswap`, nic se nespouští."""
import json
import subprocess

import pytest

from backend.agi_pletor.llm_settings import accounts
from backend.agi_pletor.llm_settings.conftest import Done, fake_run

LIST = json.dumps({"accounts": [{"number": 1, "email": "a@b.cz", "active": False}, {"number": 2, "email": "c@d.cz", "active": True}]})
URL_LINES = ("Opening browser…\n", "If the browser did not open, visit: https://claude.com/x?code=1\n")


class Login:
    """Falešný proces `claude auth login`: vypíše adresu, pak čeká na kód."""
    def __init__(self, lines=URL_LINES, rc_after=0, hang=False):
        self.stdout, self.returncode, self.rc_after, self.hang = iter(lines), None, rc_after, hang
        self.sent, self.killed = None, False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.hang:
            raise subprocess.TimeoutExpired("claude", timeout)
        self.returncode = self.rc_after
        return self.returncode

    def communicate(self, text, timeout=None):
        if self.hang:
            raise subprocess.TimeoutExpired("claude", timeout)
        self.sent, self.returncode = text, self.rc_after
        return "", ""

    def kill(self):
        self.killed = True


@pytest.fixture(autouse=True)
def clean():
    accounts.cancel()
    yield
    accounts.cancel()


def popen_of(process, calls=None):
    def popen(command, **kwargs):
        if calls is not None:
            calls.append(command)
        return process
    return popen


CSWAP = {"which": lambda name: "cswap"}


def test_start_backs_up_current_account_and_returns_url():
    calls = []
    out = accounts.start(find=lambda: "claude", popen=popen_of(Login(), calls), run=fake_run({"add": ""}, calls), **CSWAP)
    assert out == {"url": "https://claude.com/x?code=1"}
    assert calls == [["cswap", "add"], ["claude", "auth", "login"]]


def test_finish_sends_code_adds_account_and_lists():
    calls, login = [], Login()
    accounts.start(find=lambda: "claude", popen=popen_of(login), run=fake_run({"add": ""}), **CSWAP)
    out = accounts.finish("abc123#state", run=fake_run({"add": "", "list": LIST}, calls), **CSWAP)
    assert login.sent == "abc123#state\n" and calls == [["cswap", "add"], ["cswap", "list", "--json"]]
    assert [a["label"] for a in out["accounts"]] == ["a***@b***.cz", "c***@d***.cz"]


def test_finish_without_code_waits_for_self_completed_login():
    calls, login = [], Login()
    accounts.start(find=lambda: "claude", popen=popen_of(login), run=fake_run({"add": ""}), **CSWAP)
    accounts.finish(run=fake_run({"add": "", "list": LIST}, calls), **CSWAP)
    assert login.sent is None and calls[0] == ["cswap", "add"]
    hanging = Login(hang=True)
    accounts.start(find=lambda: "claude", popen=popen_of(hanging), run=fake_run({"add": ""}), **CSWAP)
    with pytest.raises(ValueError, match="ještě neskončilo"):
        accounts.finish(run=fake_run({}), **CSWAP)
    assert not hanging.killed  # běží dál, člověk může ještě vložit kód


def test_finish_without_running_login_saves_current_account():
    calls = []
    accounts.finish(run=fake_run({"add": "", "list": LIST}, calls), **CSWAP)
    assert calls == [["cswap", "add"], ["cswap", "list", "--json"]]


def test_finish_rejects_bad_code_failed_login_and_timeout():
    with pytest.raises(ValueError, match="Kód"):
        accounts.finish("a b", run=fake_run({}), **CSWAP)
    login = Login(hang=True)
    accounts.start(find=lambda: "claude", popen=popen_of(login), run=fake_run({"add": ""}), **CSWAP)
    with pytest.raises(ValueError, match="nedokončil"):
        accounts.finish("abc12345", run=fake_run({}), **CSWAP)
    assert login.killed
    accounts.start(find=lambda: "claude", popen=popen_of(Login(rc_after=1)), run=fake_run({"add": ""}), **CSWAP)
    calls = []
    with pytest.raises(ValueError, match="odmítnut"):
        accounts.finish("abc12345", run=fake_run({}, calls), **CSWAP)
    assert calls == []  # po neúspěchu žádný `cswap add`


def test_start_without_tools_or_url():
    with pytest.raises(ValueError, match="chybí"):
        accounts.start(find=lambda: None, popen=popen_of(Login()), run=fake_run({}), **CSWAP)
    with pytest.raises(ValueError, match="nainstalovaný"):
        accounts.start(find=lambda: "claude", popen=popen_of(Login()), run=fake_run({}), which=lambda name: None)
    silent = Login(lines=("nic\n",))
    with pytest.raises(ValueError, match="nevypsal"):
        accounts.start(find=lambda: "claude", popen=popen_of(silent), run=fake_run({"add": ""}), **CSWAP)
    assert silent.killed


def test_switch_to_runs_cswap_switch_and_lists():
    calls = []
    out = accounts.switch_to(2, run=fake_run({"switch": "", "list": LIST}, calls), **CSWAP)
    assert calls == [["cswap", "switch", "2"], ["cswap", "list", "--json"]] and out["accounts"][1]["active"]
    with pytest.raises(ValueError, match="kódem 1"):
        accounts.switch_to(3, run=fake_run({"switch": Done("", returncode=1)}), **CSWAP)
    with pytest.raises(ValueError, match="slot"):
        accounts.switch_to(0, run=fake_run({}), **CSWAP)

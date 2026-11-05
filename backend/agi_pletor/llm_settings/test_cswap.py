"""cswap: jen `list --json`, maskované e-maily, nenainstalovaný nástroj, selhání příkazu."""
import json

from backend.agi_pletor.llm_settings import cswap
from backend.agi_pletor.llm_settings.conftest import Done, fake_run

LIST = {"schemaVersion": 1, "activeAccountNumber": 2, "accounts": [
    {"number": 1, "email": "jan.novak@domena.cz", "organizationName": "", "organizationUuid": "", "active": False,
     "usageStatus": "ok", "usage": {"fiveHour": {"pct": 42.0, "resetsAt": "2026-11-04T18:00:00Z"},
                                    "sevenDay": {"pct": 91.5, "resetsAt": "2026-11-08T10:00:00Z"}}},
    {"number": 2, "email": "eva@firma.co.uk", "alias": "práce", "active": True, "usageStatus": "token expired",
     "usage": None},
]}


def test_mask():
    assert cswap.mask("jan@domena.cz") == "j***@d***.cz"
    assert cswap.mask("eva@firma.co.uk") == "e***@f***.uk"
    assert cswap.mask("x@localhost") == "x***@l***"
    assert cswap.mask("práce") == "práce" and cswap.mask(None) == ""


def test_lists_accounts_read_only_and_masked():
    calls = []
    out = cswap.read(which=lambda name: "cswap", run=fake_run({"list": json.dumps(LIST)}, calls))
    assert calls == [["cswap", "list", "--json"]]
    assert out == {"available": True, "accounts": [
        {"slot": 1, "label": "j***@d***.cz", "alias": None, "active": False, "usage5h": 42.0, "usage7d": 91.5,
         "resetsAt": "2026-11-04T18:00:00Z"},
        {"slot": 2, "label": "e***@f***.uk", "alias": "práce", "active": True, "usage5h": None, "usage7d": None,
         "resetsAt": None}]}
    assert "novak" not in json.dumps(out) and "firma" not in json.dumps(out)


def test_not_installed_gives_hint_and_runs_nothing():
    calls = []
    out = cswap.read(which=lambda name: None, run=fake_run({}, calls))
    assert out == {"available": False, "reason": "claude-swap není nainstalovaný.",
                   "installHint": "uv tool install claude-swap"}
    assert calls == []


def test_failure_hides_stderr():
    out = cswap.read(which=lambda name: "cswap", run=fake_run({"list": Done('{"error": "jan@domena.cz"}', 1)}))
    assert out == {"available": False, "reason": "cswap list skončil kódem 1."}

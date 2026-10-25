import json

import pytest

from backend.library import harness_verifier_plan as plans


def test_configuration_never_accepts_worker_commands_or_unpinned_runtime(monkeypatch):
    monkeypatch.delenv("OPORA_HARNESS_VERIFIER", raising=False)
    with pytest.raises(ValueError, match="disabled"):
        plans.configuration()
    config = {"project": "draft", "workspace": "draft", "image": "node@sha256:" + "a" * 64, "maxExperiments": 10}
    for value in ({**config, "image": "node:22"}, {**config, "command": "sh"},
                  {**config, "image": "node@sha256:" + "a" * 64 + "\n"}):
        monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(value))
        with pytest.raises(ValueError): plans.configuration()
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(config))
    assert plans.configuration() == config


def test_missing_optional_resolver_is_explicit_not_a_host_fallback(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError(name=name)
    monkeypatch.setattr(plans.importlib, "import_module", missing)
    with pytest.raises(ValueError, match="unavailable"):
        plans.resolver()
    def broken(name):
        raise ModuleNotFoundError(name="another.required.module")
    monkeypatch.setattr(plans.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError): plans.resolver()


def test_corrupt_assignment_never_reaches_the_plan_resolver(monkeypatch):
    monkeypatch.setattr(plans, "resolver", lambda: pytest.fail("must refuse before resolver"))
    with pytest.raises(ValueError, match="digest"):
        plans.prepare({"assignment": {}, "assignmentDigest": "forged"}, {})


@pytest.mark.parametrize("limit", [None, True, -1, 1001, 1.5, "10"])
def test_experiment_ceiling_requires_bounded_server_integer(monkeypatch, limit):
    config = {"project": "draft", "workspace": "draft", "image": "node@sha256:" + "a" * 64, "maxExperiments": limit}
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(config))
    with pytest.raises(ValueError):
        plans.configuration()
    del config["maxExperiments"]
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(config))
    with pytest.raises(ValueError):
        plans.configuration()

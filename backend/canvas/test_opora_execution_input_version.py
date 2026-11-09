"""Schema-specific identity cannot silently downgrade combined execution inputs."""
import copy

import pytest

from backend.canvas.graph import digest
from backend.canvas.opora_execution_input_version import SCHEMA, context_version


def test_plain_legacy_and_exact_combined_snapshot():
    specification = {"scope": {"nodeId": "a"}}
    assert context_version({"specification": specification}) == digest(specification)
    scope = {"specification": {"scope": {"nodeId": "b"}}}
    scope["contextVersion"] = digest(scope["specification"])
    snapshot = {"specification": specification, "inputContextSchema": SCHEMA,
                "affectedElements": [{"scope": scope}], "researchEvidence": {"pins": []},
                "storyboards": []}
    expected = digest({"specification": digest(specification),
                       "affectedScopes": [scope["contextVersion"]],
                       "researchEvidence": snapshot["researchEvidence"], "storyboards": []})
    assert context_version(snapshot) == expected
    changed = copy.deepcopy(snapshot)
    changed["storyboards"] = [{"nodeId": "a", "revision": 2}]
    assert context_version(changed) != expected
    changed = copy.deepcopy(snapshot)
    changed["affectedElements"][0]["scope"]["specification"] = {}
    with pytest.raises(ValueError, match="scope identity"):
        context_version(changed)
    snapshot["inputContextSchema"] = "unknown"
    with pytest.raises(ValueError, match="Unknown"):
        context_version(snapshot)

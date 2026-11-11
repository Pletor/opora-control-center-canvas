"""Význam vazby (relation): známé hodnoty projdou, neznámá ne."""
import pytest

from backend.canvas.element_metadata import validate_relation


@pytest.mark.parametrize("relation", ["uses", "requires", "evidences", "shares_code"])
def test_known_relation_passes(relation):
    validate_relation({"id": "e", "source": "a", "target": "b", "relation": relation})


def test_unknown_relation_refused():
    with pytest.raises(ValueError):
        validate_relation({"id": "e", "source": "a", "target": "b", "relation": "shares"})

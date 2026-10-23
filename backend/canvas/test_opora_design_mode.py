"""Režim design karty: výchozí `brand`, změna zvýší revizi, stejný režim nic nemění, jen existující karta."""
import pytest

from backend.canvas import opora_design_mode as design_mode
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401


def test_mode_defaults_to_brand_and_each_change_raises_the_revision(world):  # noqa: F811
    service, scope, _ = world
    db = service.db_for(scope["project"])
    assert design_mode.read(db, scope["project"], scope["workspace"], "card") == design_mode.DEFAULT
    payload = {**scope, "nodeId": "card", "mode": "explore"}
    changed = design_mode.set_mode(service, payload, "human")
    assert (changed["mode"], changed["revision"], changed["by"], changed["changed"]) == ("explore", 1, "human", True)
    assert design_mode.set_mode(service, payload, "human")["changed"] is False
    back = design_mode.set_mode(service, {**payload, "mode": "brand"}, "human")
    assert (back["mode"], back["revision"]) == ("brand", 2)
    assert design_mode.read(db, scope["project"], scope["workspace"], "card")["revision"] == 2


@pytest.mark.parametrize("change", [{"mode": "other"}, {"nodeId": "missing"}, {"nodeId": "bad id!"}, {"extra": 1}])
def test_invalid_mode_change_is_refused(world, change):  # noqa: F811
    service, scope, _ = world
    with pytest.raises(ValueError):
        design_mode.set_mode(service, {**scope, "nodeId": "card", "mode": "explore", **change}, "human")

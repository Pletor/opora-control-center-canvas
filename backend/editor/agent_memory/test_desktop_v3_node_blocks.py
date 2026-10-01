"""Bloky uzlu: `actions` (pipeline z knihovny) a `rules` (pravidla uzlu) vedle fáze, kritérií a kroků."""
import copy

import pytest

from backend.editor.agent_memory.desktop_v3_state import validate_state

EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []}


def _state(node):
    state = copy.deepcopy(EMPTY)
    state["nodes"] = {"focus": node}
    return state


def _node(**overrides):
    node = {"phase": "discover", "criteria": [], "steps": [], "actions": [], "rules": []}
    node.update(overrides)
    return node


def test_legacy_node_without_blocks_is_still_valid():
    legacy = {"phase": "discover", "criteria": [], "steps": []}
    assert validate_state(_state(legacy))["nodes"]["focus"] == legacy


def test_actions_and_rules_are_accepted_with_ids_and_params():
    node = _node(
        actions=[{"id": "a1", "pipelineId": "review.pr", "label": "Review PR", "params": {"depth": "full"}}],
        rules=[{"id": "r1", "text": "Nikdy neukládat heslo v plaintextu.", "kind": "must_not"}],
    )
    assert validate_state(_state(node))["nodes"]["focus"] == node


@pytest.mark.parametrize(
    "node",
    [
        _node(actions=[{"id": "a1", "pipelineId": "", "label": "x", "params": {}}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "", "params": {}}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "x", "params": []}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "x", "params": {"k": 1}}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "x\0", "params": {}}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "x"}]),
        _node(actions=[{"id": "a1", "pipelineId": "p", "label": "x", "params": {}},
                       {"id": "a1", "pipelineId": "q", "label": "y", "params": {}}]),
        _node(rules=[{"id": "r1", "text": "x", "kind": "should"}]),
        _node(rules=[{"id": "r1", "text": "", "kind": "must"}]),
        _node(rules=[{"id": "r1", "text": "x", "kind": "must", "scope": "node"}]),
        {"phase": "discover", "criteria": [], "steps": [], "actions": []},
        {"phase": "discover", "criteria": [], "steps": [], "rules": []},
        {"phase": "discover", "criteria": [], "steps": [], "ports": []},
    ],
)
def test_invalid_blocks_are_rejected(node):
    with pytest.raises(ValueError):
        validate_state(_state(node))


def test_too_many_actions_are_rejected():
    actions = [{"id": f"a{i}", "pipelineId": "p", "label": "x", "params": {}} for i in range(201)]
    with pytest.raises(ValueError):
        validate_state(_state(_node(actions=actions)))


def test_materials_accept_upload_source_and_link():
    node = _node(
        materials=[
            {"id": "m1", "kind": "upload", "path": "a" * 32 + ".png", "caption": "návrh"},
            {"id": "m2", "kind": "source", "path": "docs/mockups/login.png", "caption": ""},
            {"id": "m3", "kind": "link", "path": "https://example.com/spec", "caption": "spec"},
        ]
    )
    assert validate_state(_state(node))["nodes"]["focus"] == node


@pytest.mark.parametrize(
    "material",
    [
        {"id": "m", "kind": "upload", "path": "../project.json", "caption": ""},
        {"id": "m", "kind": "source", "path": "../secret.png", "caption": ""},
        {"id": "m", "kind": "link", "path": "javascript:alert(1)", "caption": ""},
        {"id": "m", "kind": "pdf", "path": "x.pdf", "caption": ""},
        {"id": "m", "kind": "link", "path": "", "caption": ""},
    ],
)
def test_invalid_materials_are_rejected(material):
    with pytest.raises(ValueError):
        validate_state(_state(_node(materials=[material])))

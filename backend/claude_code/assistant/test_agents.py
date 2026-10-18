import pytest

from backend.claude_code.assistant.agents import load_agents


def test_real_agents_have_every_field():
    agents = load_agents()
    assert set(agents) == {"opora-hledac", "opora-dohledavac", "opora-zadavatel", "opora-oponent"}
    for name, agent in agents.items():
        assert name.startswith("opora-")
        assert set(agent) == {"description", "prompt", "tools", "model"}
        assert agent["description"] and agent["prompt"].strip() and agent["tools"]
        assert agent["model"] in ("haiku", "sonnet", "opus")
    assert agents["opora-hledac"]["model"] == "haiku" and "Bash" in agents["opora-hledac"]["tools"]


@pytest.mark.parametrize("content", [
    "---\nname: jiny\ndescription: d\ntools: [Read]\nmodel: haiku\n---\nTělo\n",
    "---\nname: opora-x\ndescription: d\ntools: [Read]\nmodel: gpt\n---\nTělo\n",
    "---\nname: opora-x\ndescription: d\ntools: []\nmodel: haiku\n---\nTělo\n",
    "---\nname: opora-x\ndescription: d\ntools: [Read]\nmodel: haiku\n---\n\n",
])
def test_bad_agent_file_is_refused(tmp_path, content):
    (tmp_path / "opora-x.md").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_agents(tmp_path)


def test_good_agent_file_in_tmp_path(tmp_path):
    (tmp_path / "opora-x.md").write_text(
        "---\nname: opora-x\ndescription: d\ntools: [Read, Grep]\nmodel: sonnet\n---\nTělo\n", encoding="utf-8")
    assert load_agents(tmp_path) == {"opora-x": {"description": "d", "prompt": "Tělo",
                                                 "tools": ["Read", "Grep"], "model": "sonnet"}}

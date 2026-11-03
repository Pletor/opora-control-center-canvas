"""Řádka dávky srdce: přesně §2, nastavení se zdí nad zdrojem, prostředí bez klíčů API, hledání `claude`."""
import json
import os
import uuid

import pytest

from backend.brain_opora.heart import command

SID = str(uuid.UUID(int=7))


def build(resume, source_root=None):
    return command.build_command("claude", session_id=SID, resume=resume, settings_path="s.json",
                                 mcp_path="m.json", source_root=source_root)


def test_new_session_command_matches_the_contract():
    line = build(False, "/src")
    assert line[:10] == ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", "haiku",
                         "--advisor", "opus", "--session-id"]
    pairs = {line[i]: line[i + 1] for i in range(1, len(line) - 1) if line[i].startswith("--")}
    assert pairs["--session-id"] == SID and "--resume" not in line
    assert pairs["--setting-sources"] == "project" and pairs["--settings"] == "s.json"
    assert "--strict-mcp-config" in line and pairs["--mcp-config"] == "m.json"
    assert pairs["--allowedTools"] == "Read,Grep,Glob,Bash(python opora_heart.py:*)"
    assert pairs["--permission-mode"] == "dontAsk" and pairs["--add-dir"] == "/src"
    assert pairs["--system-prompt-file"] == str(command.PROMPT_FILE) and command.PROMPT_FILE.is_file()
    assert line[-2:] == ["--max-turns", "40"]


def test_resume_and_no_source_root():
    line = build(True)
    assert line[line.index("--resume") + 1] == SID and "--session-id" not in line and "--add-dir" not in line
    with pytest.raises(ValueError):
        command.build_command("claude", session_id="", resume=False, settings_path="s", mcp_path="m")
    with pytest.raises(ValueError):
        command.build_command("claude", session_id="ne-uuid", resume=False, settings_path="s", mcp_path="m")


def test_settings_deny_writes_into_the_source_and_disable_hooks(tmp_path):
    value = command.settings(tmp_path / "src")
    root = command.rule_path(tmp_path / "src")
    assert value["disableAllHooks"] is True and root.startswith("//") and "\\" not in root
    assert {f"Edit({root}/**)", f"Write({root}/**)", "NotebookEdit", "Read(**/.env)"} <= set(value["permissions"]["deny"])
    assert value["permissions"]["allow"] == []
    settings_path, mcp_path = command.write_config(tmp_path / "brain", tmp_path / "src")
    assert json.loads(settings_path.read_text(encoding="utf-8")) == command.settings(tmp_path / "src", tmp_path / "brain")
    assert json.loads(mcp_path.read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert (tmp_path / "brain" / "opora_heart.py").read_bytes() == command.TOOL_FILE.read_bytes()
    for name in command.RESEARCH_NAMES:
        assert (tmp_path / "brain" / name).read_bytes() == (command.HEART_DIR / name).read_bytes()
    dilna = tmp_path / "brain" / "dilna"
    assert (dilna / "rlm.py").read_bytes() == command.RLM_FILE.read_bytes()
    assert all((dilna / folder).is_dir() for folder in ("data", "scripts", "out"))


def test_writes_are_allowed_only_in_workshop_scripts_and_out(tmp_path):
    brain = tmp_path / "my brain"
    permissions = command.settings(tmp_path / "src", brain)["permissions"]
    dilna = command.rule_path(brain / "dilna")
    assert permissions["allow"] == [f"Write({dilna}/scripts/**)", f"Write({dilna}/out/**)",
                                    f"Edit({dilna}/scripts/**)", f"Edit({dilna}/out/**)"]
    root = command.rule_path(brain)
    for path in (f"{root}/*.json", f"{root}/*.jsonl", f"{root}/*.py", f"{dilna}/*.py", f"{dilna}/*.jsonl",
                 f"{dilna}/data/**"):
        assert {f"Write({path})", f"Edit({path})"} <= set(permissions["deny"])
    assert "Write" in command.TOOLS.split(",") and "Edit" in command.TOOLS.split(",")
    assert "Write" not in command.ALLOWED_TOOLS and "Edit" not in command.ALLOWED_TOOLS  # povolení jen s cestou


@pytest.mark.skipif(os.name != "nt", reason="disková písmena jen na Windows")
def test_rule_path_on_windows_drive():
    assert command.rule_path("C:\\Users\\a") == "//c/Users/a"


def test_child_env_strips_api_keys_and_sets_the_heart():
    env = command.child_env(base_url="http://127.0.0.1:9", token="t", project="p", workspace="w",
                            environ={"ANTHROPIC_API_KEY": "x", "TYPESAFE_API_KEY": "y", "CELERIS_API_KEY": "z",
                                     "PATH": "/bin"})
    assert not set(command.STRIPPED) & set(env) and env["PATH"] == "/bin"
    assert (env["OPORA_BASE_URL"], env["OPORA_HEART_TOKEN"], env["OPORA_PROJECT"], env["OPORA_WORKSPACE"]) == (
        "http://127.0.0.1:9", "t", "p", "w")
    assert "OPORA_SOURCE_ROOT" not in env
    assert env["PONYTAIL_DEFAULT_MODE"] == "off"
    sourced = command.child_env(base_url="b", token="t", project="p", workspace="w", source_root="/src",
                                environ={"OPORA_SOURCE_ROOT": "/stary"})
    assert sourced["OPORA_SOURCE_ROOT"] == "/src"


def test_find_claude_prefers_exe_on_windows():
    found = {"claude.cmd": "C:/n/claude.cmd", "claude.exe": "C:/n/claude.exe"}
    assert command.find_claude(found.get, nt=True) == "C:/n/claude.exe"
    assert command.find_claude({"claude.cmd": "C:/n/claude.cmd"}.get, nt=True) == "C:/n/claude.cmd"
    assert command.find_claude({"claude": "/usr/bin/claude"}.get, nt=False) == "/usr/bin/claude"
    assert command.find_claude({}.get, nt=False) is None


def test_interrogation_skill_lands_in_brain_and_is_read_only_on_demand(tmp_path):
    """Výslech, řez 2 (docs/navrhy/2026-10-30-vyslech-srdce.md §5): skill leží v `brain/skills/`, čte ho
    `opora_heart.py skill vyslech` (i z kopie v `brain/`) a základní prompt na něj jen odkazuje."""
    import subprocess
    import sys

    from backend.brain_opora.determinism import brief

    skill = command.SKILLS_DIR / "vyslech.md"
    text = skill.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 80 and "--requirement" in text and "rozhodni z toho, co máš" in text
    for key in ("goal", "users", "parts", "acceptance", "outOfScope", "assumptions", "risks", "dependencies",
                "questions"):
        assert f'"{key}"' in text
    shape = text.split("```json\n")[1].split("```")[0]
    sample = json.loads(shape.replace("nodeId|areaId", "a0"))
    assert brief.check_synthesis(sample) is sample and brief.clarity(sample, [{"answer": "ano"}]) == []  # vzor projde kontrolou kódu (předpoklady potvrdí člověk)
    prompt = command.PROMPT_FILE.read_text(encoding="utf-8")
    assert "python opora_heart.py skill vyslech" in prompt and "## Tvar syntézy" not in prompt
    command.write_config(tmp_path / "brain")
    assert (tmp_path / "brain" / "skills" / "vyslech.md").read_bytes() == skill.read_bytes()
    done = subprocess.run([sys.executable, "-I", "opora_heart.py", "skill", "vyslech"], cwd=tmp_path / "brain",
                          capture_output=True, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert done.stdout.decode("utf-8").replace("\r\n", "\n").strip() == text.strip()
    missing = subprocess.run([sys.executable, "-I", "opora_heart.py", "skill", "nic"], cwd=tmp_path / "brain",
                             capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert missing.returncode == 1 and json.loads(missing.stdout.decode("utf-8"))["code"] == "skill_missing"

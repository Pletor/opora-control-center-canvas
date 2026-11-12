"""Řádka dávky srdce: přesně §2, nastavení se zdí nad zdrojem, prostředí bez klíčů API, hledání `claude`."""
import json
import os
import uuid

import pytest

from backend.brain import registry, seed
from backend.brain.store import Store
from backend.brain_opora.heart import command
from database.schema.project_schema import REGISTRY_SCHEMA

SID = str(uuid.UUID(int=7))
SKILLS = command.HeartSkills("P\n", {"vyslech": "V\n"}, {})


def seeded(tmp_path):
    """Registr a Brain v `tmp_path` po seedu (bez ponytailu)."""
    import sqlite3

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    seed.ensure(db, tmp_path, ponytail_cache=tmp_path / "chybi")
    return db


def test_heart_reads_prompt_and_modes_from_the_active_brain_version(tmp_path):
    db = seeded(tmp_path)
    skills = command.heart_skills(db, tmp_path)
    source = seed.SEED_DIR / "opora-heart" / "skills"
    assert skills.prompt == command.skill_body((source / "heart" / "SKILL.md").read_text(encoding="utf-8"))
    assert skills.prompt.startswith("# Srdce projektu OPORA") and "name: heart" not in skills.prompt
    assert list(skills.modes) == ["vyslech", "proces-na-platne", "git-linie-srdce", "zadani-na-kanvas"] and skills.modes["vyslech"].startswith("# Výslech")
    assert list(skills.extras) == ["git-linie-srdce", "zadani-na-kanvas"] and "plátna" in skills.extras["zadani-na-kanvas"]
    only_brain = command.heart_skills(db, tmp_path, dilna={"vyslech": {"description": "x", "body": "y"}})
    assert only_brain.modes["vyslech"].startswith("# Výslech") and only_brain.extras == {}
    sha = Store(tmp_path).version("opora-heart")
    assert skills.pins == {"heart": f"opora:brain:skill:heart@{sha[:12]}",
                           "vyslech": f"opora:brain:skill:vyslech@{sha[:12]}",
                           "proces-na-platne": f"opora:brain:skill:proces-na-platne@{sha[:12]}"}
    newer = Store(tmp_path).write("opora-heart", {"skills/heart/SKILL.md": "---\nname: heart\n---\nJiné srdce\n"}, "v2")
    version = registry.add_version(db, "opora:brain:skill:heart", newer, "skills/heart/SKILL.md")
    assert command.heart_skills(db, tmp_path).prompt == skills.prompt  # kandidát srdce nemění
    registry.activate(db, version)
    changed = command.heart_skills(db, tmp_path)
    assert changed.prompt == "Jiné srdce\n" and changed.pins["heart"] == f"opora:brain:skill:heart@{newer[:12]}"
    db.execute("UPDATE brain_artifact_versions SET status='retired'")
    with pytest.raises(RuntimeError, match="opora:brain:skill:heart"):  # žádná záloha v souboru
        command.heart_skills(db, tmp_path)


def build(resume, source_root=None):
    return command.build_command("claude", session_id=SID, resume=resume, settings_path="s.json",
                                 mcp_path="m.json", prompt_file="p.md", source_root=source_root)


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
    assert pairs["--system-prompt-file"] == "p.md"
    assert line[-2:] == ["--max-turns", "40"]


def test_flow_node_sets_model_advisor_and_allowed_subcommands():
    line = command.build_command("claude", session_id=SID, resume=False, settings_path="s", mcp_path="m",
                                 prompt_file="p", model="sonnet", advisor_model="fable", subcommands=("plan", "done"))
    pairs = {line[i]: line[i + 1] for i in range(1, len(line) - 1) if line[i].startswith("--")}
    assert pairs["--model"] == "sonnet" and pairs["--advisor"] == "fable"
    assert pairs["--allowedTools"] == "Read,Grep,Glob,Bash(python opora_heart.py plan:*),Bash(python opora_heart.py done:*)"


def test_resume_and_no_source_root():
    line = build(True)
    assert line[line.index("--resume") + 1] == SID and "--session-id" not in line and "--add-dir" not in line
    for bad in ("", "ne-uuid"):
        with pytest.raises(ValueError):
            command.build_command("claude", session_id=bad, resume=False, settings_path="s", mcp_path="m",
                                  prompt_file="p")


def test_settings_deny_writes_into_the_source_and_disable_hooks(tmp_path):
    value = command.settings(tmp_path / "src")
    root = command.rule_path(tmp_path / "src")
    assert value["disableAllHooks"] is True and root.startswith("//") and "\\" not in root
    assert {f"Edit({root}/**)", f"Write({root}/**)", "NotebookEdit", "Read(**/.env)"} <= set(value["permissions"]["deny"])
    assert value["permissions"]["allow"] == []
    settings_path, mcp_path, prompt_path = command.write_config(tmp_path / "brain", SKILLS, tmp_path / "src")
    assert prompt_path == tmp_path / "brain" / command.PROMPT_NAME and prompt_path.read_text(encoding="utf-8") == "P\n" + command.RUNTIME_GUIDANCE
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


def test_child_env_strips_api_keys_so_the_heart_runs_on_the_subscription_and_sets_the_heart():
    env = command.child_env(base_url="http://127.0.0.1:9", token="t", project="p", workspace="w",
                            environ={"ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "a", "TYPESAFE_API_KEY": "y",
                                     "CELERIS_API_KEY": "z", "PATH": "/bin"})
    assert not set(command.STRIPPED) & set(env) and env["PATH"] == "/bin"
    assert "ANTHROPIC_API_KEY" not in env and "ANTHROPIC_AUTH_TOKEN" not in env
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
    """Výslech, řez 2 (docs/navrhy/2026-10-30-vyslech-srdce.md §5): skill z Brainu leží v `brain/skills/`, čte ho
    `opora_heart.py skill vyslech` (z kopie v `brain/`) a základní prompt na něj jen odkazuje."""
    import subprocess
    import sys

    from backend.brain_opora.determinism import brief

    skills = command.heart_skills(seeded(tmp_path / "data"), tmp_path / "data")
    text = skills.modes["vyslech"]
    assert len(text.splitlines()) <= 80 and "--requirement" in text and "rozhodni z toho, co máš" in text
    for key in ("goal", "users", "parts", "acceptance", "outOfScope", "assumptions", "risks", "dependencies",
                "questions"):
        assert f'"{key}"' in text
    shape = text.split("```json\n")[1].split("```")[0]
    sample = json.loads(shape.replace("nodeId|areaId", "a0"))
    assert brief.check_synthesis(sample) is sample and brief.clarity(sample, [{"answer": "ano"}]) == []  # vzor projde kontrolou kódu (předpoklady potvrdí člověk)
    assert "python opora_heart.py skill vyslech" in skills.prompt and "## Tvar syntézy" not in skills.prompt
    command.write_config(tmp_path / "brain", skills)
    assert (tmp_path / "brain" / "skills" / "vyslech.md").read_text(encoding="utf-8") == text
    done = subprocess.run([sys.executable, "-I", "opora_heart.py", "skill", "vyslech"], cwd=tmp_path / "brain",
                          capture_output=True, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert done.stdout.decode("utf-8").replace("\r\n", "\n").strip() == text.strip()
    missing = subprocess.run([sys.executable, "-I", "opora_heart.py", "skill", "nic"], cwd=tmp_path / "brain",
                             capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert missing.returncode == 1 and json.loads(missing.stdout.decode("utf-8"))["code"] == "skill_missing"


def test_process_skill_lands_in_brain_and_is_printed_by_the_tool(tmp_path):
    """Skill `proces-na-platne` se zapíše do `brain/skills/` a `opora_heart.py skill proces-na-platne` ho vypíše."""
    import subprocess
    import sys

    skills = command.heart_skills(seeded(tmp_path / "data"), tmp_path / "data")
    text = skills.modes["proces-na-platne"]
    assert text.startswith("# Proces na plátně") and "Uložit BMI" in text and "library case run" in text
    command.write_config(tmp_path / "brain", skills)
    assert (tmp_path / "brain" / "skills" / "proces-na-platne.md").read_text(encoding="utf-8") == text
    done = subprocess.run([sys.executable, "-I", "opora_heart.py", "skill", "proces-na-platne"], cwd=tmp_path / "brain",
                          capture_output=True, check=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert done.stdout.decode("utf-8").replace("\r\n", "\n").strip() == text.strip()


def test_effort_only_when_set():
    def line(**extra):
        return command.build_command("claude", session_id=SID, resume=False, settings_path="s", mcp_path="m",
                                     prompt_file="p", **extra)

    assert "--effort" not in line()
    built = line(effort="max")
    assert built[built.index("--effort") + 1] == "max" and built[built.index("--model") + 2] == "--effort"

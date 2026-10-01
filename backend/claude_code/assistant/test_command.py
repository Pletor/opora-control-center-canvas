import json
import subprocess

from backend.claude_code.assistant import command as cli


def test_command_matches_contract_without_resume():
    command = cli.build_command("C:/bin/claude.exe", "opus")
    assert command[:10] == ["C:/bin/claude.exe", "-p", "--input-format", "stream-json", "--output-format",
                            "stream-json", "--verbose", "--include-partial-messages", "--model", "opus"]
    assert "--resume" not in command
    pairs = dict(zip(command[10::2], command[11::2]))
    assert pairs["--setting-sources"] == "user,project"
    # Fáze 2 (§5.1): dotazy na oprávnění jdou přes stdio do backendu, ne potichu do zamítnutí.
    assert pairs["--permission-mode"] == "default"
    assert pairs["--permission-prompt-tool"] == "stdio"
    # Žádný volný Bash vzor: `python *opora_read.py*` by pustil i `python -c`; čtení hlídá approvals.is_read.
    assert pairs["--allowedTools"] == "Read,Glob,Grep,Skill,WebFetch,WebSearch,Agent"
    assert pairs["--disallowedTools"] == "Edit,Write,NotebookEdit,PowerShell"
    settings = json.loads(pairs["--settings"])
    assert settings["disableAllHooks"] is True
    deny = settings["permissions"]["deny"]
    for item in ("Edit", "Write", "NotebookEdit", "PowerShell", "Read(**/.env)", "Read(**/.env.*)"):
        assert item in deny
    # Web je čtení podkladů (§13.1): nesmí být v deny ani v odebraných nástrojích.
    for item in ("WebFetch", "WebSearch"):
        assert item not in deny and item not in pairs["--disallowedTools"].split(",")
    # Celé "Bash" by v deny přebilo povolený čtecí vzor opora_read.py.
    assert "Bash" not in deny


def test_resume_only_with_session_id():
    command = cli.build_command("claude", "sonnet", "1b2c")
    index = command.index("--resume")
    assert command[index + 1] == "1b2c"
    assert "--resume" not in cli.build_command("claude", "fable", None)
    assert "--resume" not in cli.build_command("claude", "fable", "")


def test_unknown_model_is_rejected():
    try:
        cli.build_command("claude", "haiku")
    except ValueError as exc:
        assert "model" in str(exc)
    else:
        raise AssertionError("haiku není povolený model")
    assert cli.MODELS == ("opus", "sonnet", "fable") and cli.DEFAULT_MODEL == "opus"


def test_env_drops_api_key_and_keeps_the_rest():
    env = cli.child_env({"ANTHROPIC_API_KEY": "sk-x", "TYPESAFE_API_KEY": "ts", "CLAUDE_CODE_OAUTH_TOKEN": "t",
                         "PATH": "p"})
    assert "ANTHROPIC_API_KEY" not in env and "TYPESAFE_API_KEY" not in env
    assert env == {"CLAUDE_CODE_OAUTH_TOKEN": "t", "PATH": "p"}


def test_env_carries_own_instance_address():
    env = cli.child_env({"PATH": "p", "OPORA_BASE_URL": "http://127.0.0.1:1"}, base_url="http://127.0.0.1:8741")
    assert env == {"PATH": "p", "OPORA_BASE_URL": "http://127.0.0.1:8741"}
    assert "OPORA_BASE_URL" not in cli.child_env({"PATH": "p"})


def test_manager_hands_instance_address_to_process(tmp_path, monkeypatch):
    from backend.claude_code.assistant import manager as manager_module

    seen = {}

    class Process:
        alive = True

        def __init__(self, command, *, cwd, env, on_line, on_exit):
            seen["env"] = env

        def start(self):
            raise OSError("nespouštět")

    monkeypatch.setattr(manager_module, "SessionProcess", Process)
    manager = manager_module.AssistantManager(
        tmp_path / "data", lambda project, workspace=None: ("draft", tmp_path), which=lambda name: "claude",
        environ={"PATH": "p", "ANTHROPIC_API_KEY": "sk"}, base_url="http://127.0.0.1:8741")
    try:
        sid = manager.create("p1")["id"]
        try:
            manager.send(sid, "ahoj")
        except manager_module.AssistantUnavailable:
            pass
        assert seen["env"] == {"PATH": "p", "OPORA_BASE_URL": "http://127.0.0.1:8741"}
    finally:
        manager.close_all()


def test_find_claude_uses_which():
    assert cli.find_claude(lambda name: f"/usr/bin/{name}") == "/usr/bin/claude"


def test_version_probe_never_runs_model_and_survives_timeout():
    calls = []

    def run(args, **options):
        calls.append((args, options))
        return subprocess.CompletedProcess(args, 0, stdout="2.5.1 (Claude Code)\n", stderr="")

    assert cli.claude_version("claude", run=run) == "2.5.1 (Claude Code)"
    assert calls[0][0] == ["claude", "--version"] and calls[0][1]["timeout"] == 10
    assert "ANTHROPIC_API_KEY" not in calls[0][1]["env"]

    def slow(args, **options):
        raise subprocess.TimeoutExpired(args, 10)

    assert cli.claude_version("claude", run=slow) is None

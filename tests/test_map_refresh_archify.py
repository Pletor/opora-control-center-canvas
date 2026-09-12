import hashlib
import json
from pathlib import Path

import pytest


def _candidate():
    return {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {"title": "Snapshot map", "quality_profile": "showcase"},
        "components": [
            {
                "id": "api_service",
                "type": "backend",
                "label": "APIService",
                "sources": [{"path": "src/app.py", "line": 2, "label": "APIService"}],
            }
        ],
        "connections": [],
    }


def _agent_output(revision):
    return json.dumps(
        {
            "candidate": _candidate(),
            "specification": "# Snapshot architecture\n\nGrounded in APIService.",
            "evidence": [{"path": "src/app.py", "line": 2, "identifier": "APIService"}],
        }
    )


def _receipt(command, candidate, html):
    spec = candidate.encode("utf-8")
    artifact = html.encode("utf-8")
    if command == "validate":
        return json.dumps(
            {
                "ok": True,
                "command": "validate",
                "validation": {
                    "checksPassed": 9,
                    "checkCount": 9,
                    "compositionProfile": "showcase",
                    "errors": 0,
                    "warnings": 0,
                },
            }
        )
    if command == "deliver":
        return json.dumps(
            {
                "ok": True,
                "command": "deliver",
                "type": "architecture",
                "input": "ignored/map.architecture.json",
                "output": "ignored/map.architecture.html",
                "specification": {"sha256": hashlib.sha256(spec).hexdigest(), "bytes": len(spec)},
                "artifact": {
                    "sha256": hashlib.sha256(artifact).hexdigest(),
                    "bytes": len(artifact),
                },
                "validation": {
                    "checksPassed": 9,
                    "checkCount": 9,
                    "compositionProfile": "showcase",
                    "errors": 0,
                    "warnings": 0,
                },
            }
        )
    if command == "visual-check":
        return json.dumps(
            {
                "ok": True,
                "command": "visual-check",
                "status": "pass",
                "artifact": {"sha256": hashlib.sha256(artifact).hexdigest()},
                "containment": {"status": "pass", "viewports": []},
                "sidecars": {"receipt": "map.architecture.visual-check.json"},
            }
        )
    raise AssertionError(command)


def test_build_archify_runs_bounded_readonly_agent_and_native_receipts(tmp_path, monkeypatch):
    from backend import map_refresh_archify as subject

    source = tmp_path / "snapshot"
    (source / "src").mkdir(parents=True)
    (source / "src/app.py").write_text("# snapshot\nclass APIService: pass\n", encoding="utf-8")
    output = tmp_path / "private-output"
    revision = "a" * 40
    candidate_text = json.dumps(_candidate(), ensure_ascii=False, indent=2) + "\n"
    html = "<!doctype html><html><body><svg></svg></body></html>"
    seen = []

    def fake_run(command, *, cwd, env, deadline, cancel, stdin=None):
        seen.append((command, cwd, env, stdin))
        if Path(command[0]).name.startswith("claude"):
            assert (
                "--setting-sources" in command
                and command[command.index("--setting-sources") + 1] == "user"
            )
            assert command[command.index("--tools") + 1] == "Read,Glob,Grep"
            assert "Bash" not in command[command.index("--tools") + 1]
            assert "disableAllHooks" in command[command.index("--settings") + 1]
            return _agent_output(revision)
        native = command[2]
        delivered_candidate = candidate_text
        if native == "deliver":
            delivered_candidate = (Path(cwd) / "map.architecture.json").read_bytes().decode("utf-8")
            (Path(cwd) / "map.architecture.html").write_text(html, encoding="utf-8")
        return _receipt(native, delivered_candidate, html)

    monkeypatch.setattr(subject, "_run_process", fake_run)
    result = subject.build_archify(source, output, revision)

    assert result["sourceRevision"] == revision
    assert result["fileName"] == "map.architecture.html"
    assert result["specificationName"] == "map.architecture.json"
    assert result["validation"]["checksPassed"] == 9
    assert result["browserEvidence"]["status"] == "pass"
    assert (output / "map.architecture.json").read_text(encoding="utf-8") == candidate_text
    assert (output / "map.architecture.html").read_text(encoding="utf-8") == html
    assert f"Revize repa: `{revision}`" in (output / "SPEC.md").read_text(encoding="utf-8")
    assert (
        json.loads((output / "deliver-receipt.json").read_text(encoding="utf-8"))["artifact"]
        == result["artifact"]
    )
    assert (
        json.loads((output / "validate-receipt.json").read_text(encoding="utf-8"))["validation"][
            "warnings"
        ]
        == 0
    )
    assert (output / "evidence.json").is_file()
    assert any(Path(item[0][0]).name.startswith("claude") for item in seen)
    assert all("CLAUDE_CODE_OAUTH_TOKEN" not in item[3] for item in seen if item[3])


def test_build_archify_rejects_bad_evidence_without_publishing(tmp_path, monkeypatch):
    from backend import map_refresh_archify as subject

    source = tmp_path / "snapshot"
    (source / "src").mkdir(parents=True)
    (source / "src/app.py").write_text("# snapshot\nclass APIService: pass\n", encoding="utf-8")
    output = tmp_path / "private-output"
    response = json.loads(_agent_output("b" * 40))
    response["evidence"][0]["identifier"] = "InventedService"

    monkeypatch.setattr(subject, "_run_process", lambda *args, **kwargs: json.dumps(response))
    with pytest.raises(ValueError, match="[dD]ůkaz"):
        subject.build_archify(source, output, "b" * 40)
    assert not output.exists()


def test_author_reserves_a_tool_free_final_turn(tmp_path, monkeypatch):
    from backend import map_refresh_archify as subject
    calls = []
    session = '1538a182-cee7-44e8-bdfc-36f60e3b1fdf'
    def fake(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return json.dumps({'subtype':'error_max_turns','session_id':session,'num_turns':6})
        assert command[command.index('--tools') + 1] == ''
        assert command[command.index('--resume') + 1] == session
        return _agent_output('a' * 40)
    monkeypatch.setattr(subject, '_run_process', fake)
    result = subject._author(tmp_path, 'a' * 40, deadline=9999999999, cancel=None)
    assert json.loads(result)['candidate'] == _candidate()
    assert sum(int(c[c.index('--max-turns') + 1]) for c in calls) <= subject.MAX_TURNS


def test_build_archify_refuses_nonempty_private_output(tmp_path):
    from backend import map_refresh_archify as subject

    source = tmp_path / "snapshot"
    source.mkdir()
    output = tmp_path / "private-output"
    output.mkdir()
    (output / "previous.html").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="prázdný"):
        subject.build_archify(source, output, "c" * 40)
    assert (output / "previous.html").read_text(encoding="utf-8") == "preserve"

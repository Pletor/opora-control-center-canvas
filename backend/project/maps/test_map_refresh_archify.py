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
    from backend.project.maps import map_refresh_archify as subject

    source = tmp_path / "snapshot"
    (source / "src").mkdir(parents=True)
    (source / "src/app.py").write_text("# snapshot\nclass APIService: pass\n", encoding="utf-8")
    output = tmp_path / "private-output"
    revision = "a" * 40
    rendered_candidate = _candidate()
    for component in rendered_candidate['components']:
        component.pop('sources')
    candidate_text = json.dumps(rendered_candidate, ensure_ascii=False, indent=2) + "\n"
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
    from backend.project.maps import map_refresh_archify as subject

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
    from backend.project.maps import map_refresh_archify as subject
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


def test_local_repository_keeps_evidence_outside_public_link_fields():
    from backend.project.maps import map_refresh_archify as subject
    original = _candidate()
    rendered = subject._render_candidate(original)
    assert 'sources' not in rendered['components'][0]
    assert original['components'][0]['sources'][0]['path'] == 'src/app.py'
    assert rendered['components'][0]['id'] == original['components'][0]['id']


def test_build_archify_refuses_nonempty_private_output(tmp_path):
    from backend.project.maps import map_refresh_archify as subject

    source = tmp_path / "snapshot"
    source.mkdir()
    output = tmp_path / "private-output"
    output.mkdir()
    (output / "previous.html").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="prázdný"):
        subject.build_archify(source, output, "c" * 40)
    assert (output / "previous.html").read_text(encoding="utf-8") == "preserve"


SESSION = '1538a182-cee7-44e8-bdfc-36f60e3b1fdf'
DIAGNOSTIC = ('[composition/label-route-clearance] showcase architecture label "CachePort" '
              'is 0px from route (minimum 4px) — adjust labelAt')


def _snapshot(tmp_path):
    source = tmp_path / "snapshot"
    (source / "src").mkdir(parents=True)
    (source / "src/app.py").write_text("# snapshot\nclass APIService: pass\n", encoding="utf-8")
    return source


def _envelope(payload):
    return json.dumps({"type": "result", "session_id": SESSION, "result": payload})


def _rejected_validate():
    return json.dumps({"ok": False, "command": "validate", "stage": "render", "error": "render failed",
                       "diagnostics": [{"severity": "warning", "code": "x/minor", "message": "minor"},
                                       {"severity": "error", "code": "composition/label-route-clearance",
                                        "message": DIAGNOSTIC}]})


def _fake_pipeline(subject, monkeypatch, *, author, validate_results):
    """Claude calls pop from author; validate pops from validate_results (str or exception)."""
    html = "<!doctype html><html><body><svg></svg></body></html>"
    calls = []

    def fake_run(command, *, cwd, env, deadline, cancel, stdin=None):
        calls.append((command, stdin))
        if Path(command[0]).name.startswith("claude"):
            return author.pop(0)
        native = command[2]
        if native == "validate":
            result = validate_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        candidate = (Path(cwd) / "map.architecture.json").read_bytes().decode("utf-8")
        if native == "deliver":
            (Path(cwd) / "map.architecture.html").write_text(html, encoding="utf-8")
        return _receipt(native, candidate, html)

    monkeypatch.setattr(subject, "_run_process", fake_run)
    monkeypatch.setattr(subject, "_node_executable", lambda: "node")
    return calls


def test_node_executable_skips_version_manager_shims(tmp_path, monkeypatch):
    import os
    from backend.project.maps import map_refresh_archify as subject

    shims, real = tmp_path / "mise" / "Shims", tmp_path / "nodejs"
    for folder in (shims, real):
        folder.mkdir(parents=True)
        for name in ("node", "node.exe"):
            (folder / name).write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", os.pathsep.join([str(tmp_path / "missing"), str(shims), str(real)]))
    assert Path(subject._node_executable()).parent == real
    monkeypatch.setenv("PATH", str(shims))
    assert subject._node_executable() is None


def test_nonzero_archify_validate_reports_first_error_diagnostic(tmp_path):
    import sys
    from backend.project.maps import map_refresh_archify as subject

    script = tmp_path / "fake.py"
    script.write_text(f"import sys\nsys.stdout.write({_rejected_validate()!r})\nsys.exit(1)\n", encoding="utf-8")
    with pytest.raises(subject.ArchifyValidationError) as caught:
        subject._run_process([sys.executable, str(script), "validate"], cwd=tmp_path, env=None,
                             deadline=subject.time.monotonic() + 30, cancel=None)
    assert "Archify validate nedokončil běh (exit 1): [composition/label-route-clearance]" in str(caught.value)
    assert caught.value.diagnostics == [DIAGNOSTIC, "[x/minor] minor"]


def test_validate_failure_gets_one_repair_round(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    payload = _envelope(_agent_output("a" * 40))
    rejection = subject.ArchifyValidationError("Archify validate nedokončil běh (exit 1): x", [DIAGNOSTIC])
    calls = _fake_pipeline(subject, monkeypatch, author=[payload, payload],
                           validate_results=[rejection, _receipt("validate", "", "")])
    result = subject.build_archify(source, output, "a" * 40)

    assert result["validation"]["checksPassed"] == 9
    assert (output / "map.architecture.html").is_file()
    resumes = [(command, stdin) for command, stdin in calls if "--resume" in command]
    assert len(resumes) == 1
    command, stdin = resumes[0]
    assert command[command.index("--resume") + 1] == SESSION
    assert command[command.index("--tools") + 1] == "" and command[command.index("--max-turns") + 1] == "1"
    assert DIAGNOSTIC in stdin


def test_second_validate_failure_raises_after_repair_without_publishing(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    payload = _envelope(_agent_output("a" * 40))
    _fake_pipeline(subject, monkeypatch, author=[payload, payload],
                   validate_results=[_rejected_validate(), _rejected_validate()])
    with pytest.raises(subject.ArchifyValidationError, match="Po opravě: .*label-route-clearance") as caught:
        subject.build_archify(source, output, "a" * 40)
    assert caught.value.diagnostics[0] == DIAGNOSTIC
    assert not output.exists() or not any(output.iterdir())
    assert not list(tmp_path.glob("archify-private-*"))


def test_evidence_mismatch_triggers_repair(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    wrong = json.loads(_agent_output("a" * 40))
    wrong["evidence"][0]["line"] = 1
    calls = _fake_pipeline(subject, monkeypatch,
                           author=[_envelope(json.dumps(wrong)), _envelope(_agent_output("a" * 40))],
                           validate_results=[_receipt("validate", "", "")])
    subject.build_archify(source, output, "a" * 40)
    stdin = next(stdin for command, stdin in calls if "--resume" in command)
    assert "src/app.py:1" in stdin and "APIService" in stdin
    assert sum(1 for command, _ in calls if Path(command[0]).name == "node") == 3


def test_evidence_mismatch_without_session_names_offending_item(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    wrong = json.loads(_agent_output("a" * 40))
    wrong["evidence"][0]["line"] = 1
    calls = _fake_pipeline(subject, monkeypatch, author=[json.dumps(wrong)], validate_results=[])
    with pytest.raises(subject.ArchifyValidationError, match=r"src/app\.py:1 .*'APIService'"):
        subject.build_archify(source, output, "a" * 40)
    assert len(calls) == 1 and not output.exists()


def test_fenced_reply_with_prose_is_accepted(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    reply = "Here is the map:\n```\n" + _agent_output("a" * 40) + "```\nDone."
    calls = _fake_pipeline(subject, monkeypatch, author=[_envelope(reply)],
                           validate_results=[_receipt("validate", "", "")])
    subject.build_archify(source, output, "a" * 40)
    assert (output / "map.architecture.html").is_file()
    assert not any("--resume" in command for command, _ in calls)


def test_prose_reply_triggers_repair_and_repaired_json_builds(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    calls = _fake_pipeline(subject, monkeypatch,
                           author=[_envelope("I will now produce the map."), _envelope(_agent_output("a" * 40))],
                           validate_results=[_receipt("validate", "", "")])
    subject.build_archify(source, output, "a" * 40)
    assert (output / "map.architecture.html").is_file()
    stdin = next(stdin for command, stdin in calls if "--resume" in command)
    assert "[agent/json]" in stdin and "I will now produce the map." in stdin


def test_invalid_envelope_is_not_repaired(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    calls = _fake_pipeline(subject, monkeypatch, author=["Error: login\nexpired"], validate_results=[])
    with pytest.raises(subject.ArchifyBuildError, match="Claude Code nevrátil JSON obálku: Error: login expired") as caught:
        subject.build_archify(source, output, "a" * 40)
    assert not isinstance(caught.value, subject.ArchifyValidationError)
    assert len(calls) == 1 and not output.exists()


def test_repair_reply_still_not_json_fails_without_publishing(tmp_path, monkeypatch):
    from backend.project.maps import map_refresh_archify as subject

    source, output = _snapshot(tmp_path), tmp_path / "private-output"
    calls = _fake_pipeline(subject, monkeypatch, author=[_envelope("plan first"), _envelope("still a plan")],
                           validate_results=[])
    with pytest.raises(subject.ArchifyValidationError, match=r"Po opravě: .*\[agent/json\].*still a plan"):
        subject.build_archify(source, output, "a" * 40)
    assert sum(1 for command, _ in calls if "--resume" in command) == 1
    assert not output.exists() and not list(tmp_path.glob("archify-private-*"))

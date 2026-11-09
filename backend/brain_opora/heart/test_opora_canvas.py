"""CLI cannot manufacture an actor/scope or arbitrary endpoint."""
import argparse
import json
from types import SimpleNamespace

import pytest
from backend.brain_opora.heart import opora_canvas


def test_canvas_help_identifies_existing_saved_proposal_read(capsys):
    parser = argparse.ArgumentParser()
    opora_canvas.parser(parser.add_subparsers(dest="command"))
    with pytest.raises(SystemExit) as result:
        parser.parse_args(["canvas", "--help"])
    assert result.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "opora_graph_routes.read" in help_text
    assert "latestProposalId/supersedes" in help_text
    assert "contentInputs.researchEvidenceByNode" in help_text
    assert "neither --request-id nor proposal --accept" in help_text


def test_cli_exact_scope_body_and_named_path(tmp_path):
    parser = argparse.ArgumentParser()
    opora_canvas.parser(parser.add_subparsers(dest="command"))
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"identifier": "abc"}), encoding="utf-8")
    calls = []
    tool = SimpleNamespace(scope=lambda: {"project": "p", "workspace": "w"}, Failure=ValueError,
                           call=lambda *args, **kwargs: calls.append((args, kwargs)))
    opora_canvas.run(parser.parse_args(["canvas", "invoke", "opora_graph_routes.read", "--file", str(path)]), tool)
    assert calls[0][0] == ("POST", "/api/brain/canvas/invoke", {"project": "p", "workspace": "w",
        "capability": "opora_graph_routes.read", "input": {"identifier": "abc"}})
    path.write_text('{"project":"foreign"}', encoding="utf-8")
    with pytest.raises(ValueError):
        opora_canvas.run(parser.parse_args(["canvas", "invoke", "canvas_routes.view", "--file", str(path)]), tool)
    assert len(calls) == 1
    opora_canvas.run(parser.parse_args(["canvas", "describe", "../escape"]), tool)
    assert calls[-1][0][1].endswith("..%2Fescape")

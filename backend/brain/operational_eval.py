"""Frozen capability contracts grade parsed CLI behavior, never execute model output."""
import json
from pathlib import Path

from backend.brain.command_argv import commands
from backend.brain.command_probe import probe

CONTRACT = "operational-contract.json"
CAPABILITIES = {"node_packet", "research_scope", "solution_identity", "canonical_revision"}


def passed(value):
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 or value.get("passed") is not True:
        return False
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        return False
    capabilities = []
    for case in cases:
        if not isinstance(case, dict) or case.get("passed") is not True:
            return False
        checks = case.get("capabilities")
        if not isinstance(checks, list) or not checks:
            return False
        for check in checks:
            if (not isinstance(check, dict) or check.get("passed") is not True
                    or not isinstance(check.get("capability"), str) or check["capability"] not in CAPABILITIES):
                return False
            capabilities.append(check["capability"])
    return set(capabilities) == CAPABILITIES


def contract(plugin_dir, plugin):
    path = plugin_dir / "evals" / CONTRACT
    if not path.is_file():
        if plugin == "opora-control-center":
            raise ValueError("Control-center operational contract is missing.")
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or value.get("schemaVersion") != 1 or not isinstance(value.get("cases"), dict)
            or not value["cases"] or not all(isinstance(items, list) and items and all(isinstance(item, dict) for item in items)
                                             for items in value["cases"].values())):
        raise ValueError("Operational contract is malformed.")
    ids = [item.get("capability") for items in value["cases"].values() for item in items]
    if (not all(isinstance(key, str) and key for key in ids) or len(set(ids)) != len(ids)
            or any(not isinstance(item.get("parsed"), dict) or not item.get("route") or item.get("method") not in ("GET", "POST")
                   for items in value["cases"].values() for item in items)):
        raise ValueError("Operational capabilities are malformed.")
    if plugin == "opora-control-center" and set(ids) != CAPABILITIES:
        raise ValueError("All four control-center capabilities are required.")
    return value


def final_text(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Evaluation trace is too large.")
    last = None
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            last = event["result"]
        elif event.get("type") == "assistant":
            texts = [item["text"] for item in event.get("message", {}).get("content", [])
                     if item.get("type") == "text" and isinstance(item.get("text"), str)]
            if texts:
                last = "\n".join(texts)
    if last is None:
        raise ValueError("No final model response in evaluation trace.")
    return last


def grade(text, expected, script):
    argv = commands(text)
    if len(argv) != len(expected):
        raise ValueError("Wrong number of scoped read commands.")
    results = []
    for args, item in zip(argv, expected, strict=True):
        actual = probe(script, args)
        parsed = actual.pop("parsed")
        matches = all((str(parsed.get(key)).casefold() == str(value).casefold() if key == "query"
                       else parsed.get(key) == value) for key, value in item["parsed"].items())
        # An extra search scope, connection override or ignored extra flag is not the same operation.
        allowed = set(item["parsed"]) | {"command", "limit", "result_type", "raw"}
        if parsed.get("command") == "knowledge-search":
            allowed.add("search_scope")
            scopes = actual["arguments"].get("scopes")
            required = {"project": item["parsed"]["project"], "workspace": item["parsed"]["workspace"]}
            if not isinstance(scopes, list) or not scopes or any(scope != required for scope in scopes):
                raise ValueError("Search scope differs from the authorized capability.")
        extras = {key: value for key, value in parsed.items() if value not in (None, False, [], 0, 10, "solution") and key not in allowed}
        if not matches or extras or actual["method"] != item["method"] or actual["route"] != item["route"]:
            raise ValueError("Command does not match its exact scoped capability.")
        results.append({"capability": item["capability"], "passed": True, "argv": args, **actual})
    return results


def apply(report, specification, plugin_dir):
    if specification is None:
        return report
    cases = report.get("cases") or []
    by_name = {case.get("name"): case for case in cases}
    outcomes, scores = [], []
    for name, expected in specification["cases"].items():
        arms = by_name.get(name, {}).get("arms", {}).get("with", [])
        if not arms:
            outcomes.append({"case": name, "passed": False, "error": "missing_model_run"})
            scores.append(0)
        for run in arms:
            try:
                if run.get("error"):
                    raise ValueError("Model run did not complete.")
                checks = grade(final_text(run["tracePath"]), expected,
                               plugin_dir / "skills/opora-control-center/scripts/opora_read.py")
                outcomes.append({"case": name, "passed": True, "capabilities": checks})
                scores.append(1)
            except (ValueError, OSError, KeyError, TypeError, SyntaxError) as error:
                outcomes.append({"case": name, "passed": False, "error": str(error)[:300]})
                scores.append(0)
    return {**report, "nativeAggregates": report.get("aggregates"),
            "aggregates": {**report.get("aggregates", {}), "overallScore": sum(scores) / len(scores)},
            "operational": {"schemaVersion": 1, "passed": bool(scores) and all(scores), "cases": outcomes}}

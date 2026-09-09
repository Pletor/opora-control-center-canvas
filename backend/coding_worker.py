"""Hermes library worker; pouze tři scope-bound nástroje, bez host shellu."""
import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

# Spouští se výhradně Pythonem instalovaného Hermesu; neimportuje cílové repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.coding_tools import ScopedFiles, run_tests


def main():
    packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root, run_id = packet["targetPath"], packet["runId"]
    files = ScopedFiles(root)
    output_lock = threading.Lock()
    test_lock = threading.Lock()

    def event(kind, **data):
        with output_lock:
            print("OPORA_EVENT " + json.dumps({"kind": kind, "observedAt": datetime.now(UTC).isoformat(), **data}, ensure_ascii=True), flush=True)

    def read(args, **kwargs):
        try:
            result = {"path": args.get("path"), "content": files.read(args.get("path"))}
            event("file_read", path=args.get("path"))
            return json.dumps(result)
        except (ValueError, OSError):
            return json.dumps({"error": "Read refused: only calculator.py in the approved workspace."})

    def write(args, **kwargs):
        try:
            with test_lock:
                result = files.write(args.get("path"), args.get("content"))
            event("file_written", **result)
            return json.dumps(result)
        except (ValueError, OSError):
            return json.dumps({"error": "Write refused: only calculator.py, max 16000 characters, no redirects."})

    def tests(args, **kwargs):
        if args:
            return json.dumps({"error": "The test command takes no arguments."})
        event("tests_started")
        with test_lock:
            result = run_tests(root, run_id)
        event("tests_finished", **result)
        return json.dumps(result)

    from run_agent import AIAgent
    from tools.registry import registry
    definitions = [
        ("canvas_read_file", "Read calculator.py from the approved coding workspace.", {"path": {"type": "string", "enum": ["calculator.py"]}}, ["path"], read),
        ("canvas_write_file", "Write actual Python source to calculator.py. Cannot write tests, credentials, or any other file.", {"path": {"type": "string", "enum": ["calculator.py"]}, "content": {"type": "string"}}, ["path", "content"], write),
        ("canvas_run_tests", "Run the immutable addition oracle in a network-disabled Docker sandbox. Returns real test output and exit code.", {}, [], tests),
    ]
    for name, description, properties, required, handler in definitions:
        registry.register(name=name, toolset="opora_coding", schema={"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}, handler=handler, description=description)
    settings = packet["context"]["settings"]
    agent = AIAgent(provider=settings["provider"], model=settings["model"], enabled_toolsets=["opora_coding"], max_iterations=8, run_budget_seconds=settings["budgetSeconds"], quiet_mode=True, skip_context_files=True, skip_memory=True, skip_background_review=True, load_soul_identity=False, fallback_model=[], reasoning_config={"effort": "low"}, session_id="opora-" + run_id)
    from model_tools import get_tool_definitions
    # Explicitní pracovní katalog před první konverzací; žádné změny Hermes configu.
    agent.tools = get_tool_definitions(enabled_toolsets=["opora_coding"], quiet_mode=True, skip_tool_search_assembly=True)
    names = {tool["function"]["name"] for tool in agent.tools}
    agent.valid_tool_names = names
    event("tool_preflight", toolNames=sorted(names))
    if names != {d[0] for d in definitions}:
        raise RuntimeError("Hermes tool preflight failed closed")
    if "--preflight" in sys.argv:
        return
    event("hermes_ready", toolNames=sorted(names), provider=settings["provider"], model=settings["model"])
    result = agent.run_conversation(user_message=json.dumps({"task": packet["task"], "savedContext": packet["context"], "contract": "Read calculator.py; run tests to see baseline; implement add(a,b) as addition; run tests after writing. Use tools, not a proposed patch. The function must contain a single arithmetic return expression, no imports, decorators, calls or side effects. Do not alter or invent tests. Stop after reporting the actual test result."}, ensure_ascii=False))
    event("agent_finished", response=str(result.get("final_response", ""))[:8000])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - protokolová hranice nesmí uniknout traceback s credentials.
        # Chyba třídy je bezpečná; nevypisovat credential-bearing traceback.
        print("OPORA_EVENT " + json.dumps({"kind": "worker_error", "errorType": type(exc).__name__}), flush=True)
        sys.exit(1)

"""Hermes worker pro dokumentační handoff; žádný host shell ani file toolset."""

import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root))
assert (_root / "backend" / "paths.py").is_file(), "kořen repozitáře nenalezen; změnila se hloubka souboru"
from backend.agents.runs.task_handoff_tools import DocumentTools


def main():
    packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    tools = DocumentTools(packet["workspacePath"], packet["context"])
    lock = threading.Lock()

    def event(kind, **data):
        with lock:
            print(
                "OPORA_EVENT "
                + json.dumps(
                    {"kind": kind, "observedAt": datetime.now(UTC).isoformat(), **data},
                    ensure_ascii=True,
                ),
                flush=True,
            )

    def read(args, **_kwargs):
        try:
            section = args.get("section")
            result = tools.read_context(section)
            event("context_read", section=section)
            return json.dumps({"section": section, "content": result}, ensure_ascii=False)
        except (AttributeError, ValueError):
            return json.dumps({"error": "Read refused: only approved map or documents snapshots."})

    def write(args, **_kwargs):
        try:
            result = tools.write_result(args.get("content"))
            event("result_written", **result)
            return json.dumps(result)
        except (AttributeError, OSError, ValueError):
            return json.dumps(
                {"error": "Write refused: only bounded result.md in the isolated workspace."}
            )

    from run_agent import AIAgent
    from tools.registry import registry

    definitions = [
        (
            "canvas_read_document_context",
            "Read one approved immutable context snapshot.",
            {"section": {"type": "string", "enum": ["map", "documents", "workspaceDocuments"]}},
            ["section"],
            read,
        ),
        (
            "canvas_write_result",
            "Write the final documentation to result.md only.",
            {"content": {"type": "string"}},
            ["content"],
            write,
        ),
    ]
    for name, description, properties, required, handler in definitions:
        registry.register(
            name=name,
            toolset="opora_documentation",
            schema={
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
            handler=handler,
            description=description,
        )
    settings = packet["settings"]
    agent = AIAgent(
        provider=settings["provider"],
        model=settings["model"],
        enabled_toolsets=["opora_documentation"],
        max_iterations=6,
        run_budget_seconds=settings["budgetSeconds"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        load_soul_identity=False,
        fallback_model=[],
        reasoning_config={"effort": "low"},
        session_id="opora-document-" + packet["id"],
    )
    from model_tools import get_tool_definitions

    agent.tools = get_tool_definitions(
        enabled_toolsets=["opora_documentation"], quiet_mode=True, skip_tool_search_assembly=True
    )
    names = {tool["function"]["name"] for tool in agent.tools}
    agent.valid_tool_names = names
    event("tool_preflight", toolNames=sorted(names))
    if names != {definition[0] for definition in definitions}:
        raise RuntimeError("Hermes tool preflight failed closed")
    if "--preflight" in sys.argv:
        return
    event(
        "hermes_ready",
        provider=settings["provider"],
        model=settings["model"],
        toolNames=sorted(names),
    )
    result = agent.run_conversation(
        user_message=json.dumps(
            {
                "task": packet["task"],
                "contract": "Use the approved context tools. Read relevant map, documents, and workspaceDocuments snapshots, then write the requested documentation to result.md with canvas_write_result. Do not propose a patch or access any other file, command, network, credential, or tool. Finish after the write.",
                "scope": packet["scope"],
            },
            ensure_ascii=False,
        )
    )
    event("agent_finished", response=str(result.get("final_response", ""))[:8000])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - worker boundary must not leak secrets.
        print(
            "OPORA_EVENT " + json.dumps({"kind": "worker_error", "errorType": type(exc).__name__}),
            flush=True,
        )
        sys.exit(1)

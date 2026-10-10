"""Profil zápisů rozhodnutí a pipeline (cProfile). ZAPISUJE do kopie dat.

`uv run python tools/perf/bench_writes.py <kopie> [--project P]`
U každého zápisu vypíše i délku odpovědi v JSON (cíl karty P3: < 10 kB).
"""
import copy
import cProfile
import io
import json
import pstats
import time

from perf_common import parser, use_repo


def profile(name, action):
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    try:
        result = action()
        size = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        outcome = f"ok, odpověď {size / 1024:.1f} kB"
    except Exception as error:  # noqa: BLE001 - měření hlásí chybu zápisu, nespadne
        outcome = repr(error)[:200]
    profiler.disable()
    print(f"== {name}: {time.perf_counter() - started:.3f}s {outcome}")
    out = io.StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumulative").print_stats(16)
    print(out.getvalue().split("\n", 6)[-1])


def main():
    args = parser("Profil zápisů rozhodnutí a pipeline.").parse_args()
    use_repo()
    from backend.canvas.canvas_service import CanvasService
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
    from backend.editor.agent_memory.memory_items import MemoryItems
    from backend.editor.agent_memory.pipeline_routing import PipelineRouting

    project, workspace = args.project, args.workspace
    service = CanvasService(args.data)
    state = DesktopV3State(service)
    service.desktop_v3_state = state
    items, routing = MemoryItems(state), PipelineRouting(service, state)
    stored = state.read(project, workspace)["state"]
    print("rozhodnutí", len(stored["decisions"]), "uzlů", len(stored["nodes"]))
    if stored["decisions"]:
        item = {**copy.deepcopy(stored["decisions"][0]), "id": f"perfprobe{int(time.time())}"}
        profile("decision add", lambda: items.apply("decisions", {
            "project": project, "workspace": workspace, "id": item["id"], "op": "add",
            "expected": None, "item": item}, actor="human"))
    current = state.read(project, workspace)
    nodes = current["state"]["nodes"]

    def unrouted(node):
        entry = nodes.get(node["id"], {})
        stages = (entry.get("stages") or {}).get("items")
        return not entry.get("done", {}).get("confirmed") and not stages

    graph = service.view(project, workspace)["graph"]
    target = next((node["id"] for node in graph["nodes"]
                   if node.get("kind") == "node" and unrouted(node)), None)
    if target:
        profile("pipeline route", lambda: routing.apply({
            "project": project, "workspace": workspace, "nodeId": target,
            "expectedRevision": current["revision"], "op": "route", "reason": "perf",
            "profile": "code"}, actor="human"))


if __name__ == "__main__":
    main()

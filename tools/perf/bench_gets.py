"""Latence čtecích endpointů UI na kopii dat: každý dotaz 2×, druhý běh je teplý.

`uv run python tools/perf/bench_gets.py <kopie> [--project P] [--node N]`
"""
import os
import time

from perf_common import parser, use_repo


def urls(project, workspace, node):
    scope = f"project={project}&workspace={workspace}"
    desk = "/api/desktop-v3/"
    return ["/api/bootstrap", f"/api/view?{scope}", f"{desk}state?{scope}", f"{desk}frontier?{scope}",
            f"{desk}work-overview?{scope}", f"{desk}scenario-history?{scope}", f"{desk}leases?{scope}",
            f"{desk}assignment-status?{scope}", f"{desk}source-status?{scope}",
            f"{desk}card-checklist?{scope}", f"{desk}agent-workspace-summaries?{scope}",
            f"/api/brief-vault?{scope}", f"/api/map-refresh/status?project={project}",
            f"/api/canvas-index?{scope}", f"/api/canvas-versions?{scope}",
            f"{desk}node-brief?{scope}&nodeId={node}"]


def main():
    args = parser("Latence čtecích endpointů UI na kopii dat.").parse_args()
    os.environ["OPORA_CANVAS_PORT"] = "8740"
    use_repo()
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    client = TestClient(create_app(args.data), base_url="http://127.0.0.1:8740")
    print(f"{'kód':>4} {'1. běh':>9} {'2. běh':>9} {'velikost':>10}  endpoint")
    for url in urls(args.project, args.workspace, args.node):
        times = []
        for _ in range(2):
            started = time.perf_counter()
            response = client.get(url)
            times.append(time.perf_counter() - started)
        print(f"{response.status_code:>4} {times[0] * 1000:7.0f}ms {times[1] * 1000:7.0f}ms "
              f"{len(response.content) / 1024:8.1f}kB  {url.split('?')[0]}")


if __name__ == "__main__":
    main()

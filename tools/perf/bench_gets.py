"""Latence čtecích endpointů UI na kopii dat: každý dotaz `--repeat`× (výchozí 2), druhý běh je teplý.

`uv run python tools/perf/bench_gets.py <kopie> [--project P] [--node N] [--repeat 20]`
Při `--repeat` > 2 vypíše i p50/p95/p99 teplých běhů. Vrátí-li endpoint `ETag`, změří i podmíněný
dotaz s `If-None-Match` (sloupec 304: kód a čas), jak ho posílá UI při pollingu.
"""
import os
import time

from perf_common import parser, percentiles, use_repo


def urls(project, workspace, node):
    scope = f"project={project}&workspace={workspace}"
    desk = "/api/desktop-v3/"
    return ["/api/bootstrap", f"/api/view?{scope}", f"{desk}state?{scope}", f"{desk}frontier?{scope}",
            f"{desk}work-overview?{scope}", f"{desk}scenario-history?{scope}", f"{desk}leases?{scope}",
            f"{desk}assignment-status?{scope}", f"{desk}source-status?{scope}",
            f"{desk}card-checklist?{scope}", f"{desk}agent-workspace-summaries?{scope}",
            f"/api/brief-vault?{scope}", f"/api/map-refresh/status?project={project}",
            f"/api/canvas-index?{scope}", f"/api/canvas-versions?{scope}",
            f"/api/canvas-versions/head?{scope}",
            f"{desk}node-brief?{scope}&nodeId={node}"]


def main():
    cli = parser("Latence čtecích endpointů UI na kopii dat.")
    cli.add_argument("--repeat", type=int, default=2)
    args = cli.parse_args()
    os.environ["OPORA_CANVAS_PORT"] = "8740"
    use_repo()
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    client = TestClient(create_app(args.data), base_url="http://127.0.0.1:8740")
    repeat = max(2, args.repeat)
    stats = repeat > 2
    print(f"{'kód':>4} {'1. běh':>9} {'2. běh':>9}"
          + (f" {'p50':>8} {'p95':>8} {'p99':>8}" if stats else "")
          + f" {'304':>12} {'velikost':>10}  endpoint")
    for url in urls(args.project, args.workspace, args.node):
        times = []
        for _ in range(repeat):
            started = time.perf_counter()
            response = client.get(url)
            times.append((time.perf_counter() - started) * 1000)
        conditional = "-"
        tag = response.headers.get("etag")
        if response.status_code == 200 and tag:
            started = time.perf_counter()
            again = client.get(url, headers={"If-None-Match": tag})
            conditional = f"{again.status_code} {(time.perf_counter() - started) * 1000:5.0f}ms"
        line = f"{response.status_code:>4} {times[0]:7.0f}ms {times[1]:7.0f}ms"
        if stats:
            p50, p95, p99 = percentiles(times[1:])
            line += f" {p50:6.0f}ms {p95:6.0f}ms {p99:6.0f}ms"
        print(f"{line} {conditional:>12} {len(response.content) / 1024:8.1f}kB  {url.split('?')[0]}", flush=True)


if __name__ == "__main__":
    main()

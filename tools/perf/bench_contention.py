"""Souběh oken: N oken polluje /api/canvas-versions jako dřívější UI, mezitím se měří jiné dotazy.

`uv run python tools/perf/bench_contention.py <kopie> <okna> [--interval 3] [--seconds 45]`
Okno vystřelí dotaz každých `--interval` s bez ohledu na předchozí (jako `setInterval` bez guardu),
takže měření ukazuje nejhorší případ i po opravě pollerů ve frontendu.
"""
import os
import threading
import time

from perf_common import parser, use_repo


def main():
    cli = parser("Souběh oken nad výpisem verzí.")
    cli.add_argument("tabs", type=int)
    cli.add_argument("--interval", type=float, default=3.0)
    cli.add_argument("--seconds", type=float, default=45.0)
    args = cli.parse_args()
    use_repo()
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    app = create_app(args.data)
    scope = f"project={args.project}&workspace={args.workspace}"
    stop = time.time() + args.seconds
    latencies = []

    def poller():
        client = TestClient(app, base_url="http://127.0.0.1:8740")

        def one():
            started = time.perf_counter()
            client.get(f"/api/canvas-versions?{scope}")
            latencies.append(time.perf_counter() - started)

        while time.time() < stop:
            threading.Thread(target=one, daemon=True).start()
            time.sleep(args.interval)

    for _ in range(args.tabs):
        threading.Thread(target=poller, daemon=True).start()
    time.sleep(8)
    client = TestClient(app, base_url="http://127.0.0.1:8740")
    desk = "/api/desktop-v3/"
    for url in [f"{desk}leases?{scope}", f"{desk}node-brief?{scope}&nodeId={args.node}",
                f"{desk}state?{scope}", f"{desk}leases?{scope}"]:
        started = time.perf_counter()
        client.get(url)
        print(f"okna={args.tabs} {time.perf_counter() - started:6.2f}s {url.split('?')[0]}", flush=True)
    print("canvas-versions latence (s):", [round(value, 2) for value in latencies], flush=True)
    os._exit(0)  # pollery jsou daemon vlákna s otevřenými dotazy; nečekat na ně


if __name__ == "__main__":
    main()

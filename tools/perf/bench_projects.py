"""Souběh projektů: dlouhé čtení Ample (výpis verzí + node-brief) vs. leases a frontier (karta P2).

`uv run python tools/perf/bench_projects.py <kopie> [--other P] [--seconds 30] [--loops 2] [--samples 8]`
Nejdřív změří leases a frontier na Ample i na druhém projektu bez souběhu (medián), pak spustí
`--loops` vláken, která na Ample dokola čtou /api/canvas-versions a node-brief, a měří totéž znovu.
Cíl karty P2: leases pod souběhem < 200 ms, frontier nejvýš o 20 % pomalejší než bez souběhu.
"""
import os
import statistics
import threading
import time

from perf_common import parser, use_repo

# Druhý projekt kopie dat: OPORA Control Center — vývoj aplikace.
OTHER_PROJECT = "4b38182c5b04482bb00e0f3d3ae55656"
LEASES_LIMIT_MS = 200
FRONTIER_SLOWDOWN = 1.2


def main():
    cli = parser("Souběh dvou projektů: dlouhé čtení vs. leases a frontier.")
    cli.add_argument("--other", default=OTHER_PROJECT)
    cli.add_argument("--seconds", type=float, default=30.0)
    cli.add_argument("--loops", type=int, default=2)
    cli.add_argument("--samples", type=int, default=8)
    args = cli.parse_args()
    os.environ["OPORA_CANVAS_PORT"] = "8740"
    use_repo()
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    app = create_app(args.data)
    desk = "/api/desktop-v3/"
    ample = f"project={args.project}&workspace={args.workspace}"
    other = f"project={args.other}&workspace={args.workspace}"
    probes = {"leases Ample": f"{desk}leases?{ample}", "frontier Ample": f"{desk}frontier?{ample}",
              "leases druhý": f"{desk}leases?{other}", "frontier druhý": f"{desk}frontier?{other}"}
    client = TestClient(app, base_url="http://127.0.0.1:8740")

    def sample(url):
        started = time.perf_counter()
        response = client.get(url)
        if response.status_code != 200:
            raise SystemExit(f"{url} vrátil {response.status_code}: {response.text[:200]}")
        return (time.perf_counter() - started) * 1000

    def measure():
        return {name: [sample(url) for _ in range(args.samples)] for name, url in probes.items()}

    for url in probes.values():  # zahřátí: první otevření DB a cache instance
        sample(url)
    quiet = measure()

    stop = threading.Event()
    long_reads = []

    def long_reader():
        reader = TestClient(app, base_url="http://127.0.0.1:8740")
        urls = [f"/api/canvas-versions?{ample}", f"{desk}node-brief?{ample}&nodeId={args.node}"]
        while not stop.is_set():
            for url in urls:
                started = time.perf_counter()
                reader.get(url)
                long_reads.append((url.split("?")[0], time.perf_counter() - started))

    threads = [threading.Thread(target=long_reader, daemon=True) for _ in range(args.loops)]
    for thread in threads:
        thread.start()
    time.sleep(2)  # dlouhá čtení už běží
    deadline = time.time() + args.seconds
    busy = {name: [] for name in probes}
    while time.time() < deadline:
        for name, values in measure().items():
            busy[name].extend(values)
    stop.set()

    print(f"{'endpoint':<16} {'klid med':>9} {'souběh med':>11} {'souběh p95':>11} {'souběh max':>11}")
    ok = True
    for name in probes:
        calm, loaded = statistics.median(quiet[name]), statistics.median(busy[name])
        p95 = statistics.quantiles(busy[name], n=20)[-1]
        print(f"{name:<16} {calm:7.0f}ms {loaded:9.0f}ms {p95:9.0f}ms {max(busy[name]):9.0f}ms")
        if name.startswith("leases"):
            ok &= max(busy[name]) < LEASES_LIMIT_MS
        else:
            ok &= loaded <= calm * FRONTIER_SLOWDOWN
    for url in sorted({url for url, _ in long_reads}):
        values = [value for key, value in long_reads if key == url]
        print(f"dlouhé čtení {url}: {len(values)}× medián {statistics.median(values):.2f}s")
    print("cíl P2 (leases < 200 ms, frontier ≤ +20 %):", "SPLNĚN" if ok else "NESPLNĚN", flush=True)
    os._exit(0 if ok else 1)  # dlouhá čtení jsou daemon vlákna s otevřeným dotazem; nečekat na ně


if __name__ == "__main__":
    main()

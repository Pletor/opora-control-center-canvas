"""HTTP sonda hostu pro monitoring (plátno 4, M1): jedno měření `{ok, status, latency_ms, error}`.

Měří stejný klient jako stav webu (`integrations/web_probe_client.probe_host`: HTTPS, timeout 5 s, SSRF ochrana),
tady se jeho výsledek jen zúží na to, co potřebuje detektor. `ok` je jen stav `up`; `degraded` z health je anomálie.
"""

from backend.integrations.web_probe_client import probe_host


def probe(host, health_path=None, transport=probe_host):
    """Změří host; výjimka transportu je neúspěšné měření, ne pád tiku."""
    try:
        result = transport(host, health_path)
    except Exception as error:  # noqa: BLE001 – jeden špatný host nesmí zastavit tik ostatních
        return {"ok": False, "status": None, "latency_ms": None, "error": f"sonda selhala: {error}"}
    ok = result.get("state") == "up"
    return {"ok": ok, "status": result.get("httpStatus"), "latency_ms": result.get("latencyMs"),
            "error": None if ok else result.get("detail") or result.get("state")}

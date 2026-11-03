"""Registr typů uzlů v kódu: porty a funkce, která uzel vykoná.

Funkce dostane `ctx` (node, node_run_id, input, config sub-portů, idempotency_key, now) a vrátí jedno z:
- `{"port": "<výstupní port>", "output": ...}`: uzel skončil a tok pokračuje hranami `main` z portu,
- `{"wait": "<na co čeká>", "deadline": <datetime>}`: uzel čeká; po deadline pokračuje portem `timeout`,
- `{"detach": True}`: jen typ s `detached=True`; práce běží jinde (mimo zámek registru), posílá heartbeat
  a skončí přes `interpreter.finish` / `interpreter.fail`.

Typy katalogu srdce (`backend/flow/catalogs/heart/`) se do registru přidávají na konci modulu; katalog importuje
`node_spec`, ne tento modul, takže nevzniká kruh.
"""

from datetime import timedelta

from backend.flow.catalogs.heart.nodes import HEART_TYPES
from backend.flow.node_spec import PORT_KINDS, NodeType, Port  # noqa: F401

DEFAULT_APPROVAL_SECONDS = 24 * 3600


def _pass_input(ctx):
    """Spouštěč předá data spouštěče, `debug.echo` vrátí svůj vstup."""
    return {"port": "main", "output": ctx["input"]}


def _approval(ctx):
    seconds = int(ctx["node"].get("params", {}).get("timeout_seconds", DEFAULT_APPROVAL_SECONDS))
    return {"wait": "human", "deadline": ctx["now"] + timedelta(seconds=seconds)}


NODE_TYPES = {
    t.type: t
    for t in (
        NodeType("trigger.manual", 1, (Port("main", "out"),), _pass_input, trigger=True),
        NodeType("debug.echo", 1, (Port("main", "in"), Port("main", "out")), _pass_input),
        NodeType(
            "approval.human", 1,
            (Port("main", "in"), Port("approved", "out"), Port("rejected", "out"), Port("timeout", "out")),
            _approval,
        ),
    )
}

NODE_TYPES.update({t.type: t for t in HEART_TYPES})

"""Druhy dat uzlů plátna procesu: `(accepts, emits)` podle typu (`docs/navrhy/2026-11-04-platno-procesu.md` §2).

Co tu typ chybí, nic neomezuje. Dynamické uzly (`custom.step`, `flow.*`) a sub-porty AI se nevyplňují záměrně.
"""

SHOW = ("text", "number", "json", "table", "event")
DATA_FLOW = {
    "fe.click": ((), "event"), "fe.form": ((), "json"), "fe.state": ((), "json"),
    "fe.show": (SHOW, ""), "fe.notify": (SHOW, ""),
    "be.endpoint": (("json", "event"), "json"), "be.validate": (("json",), "json"), "be.function": ((), "json"),
    "db.read": ((), "table"), "db.write": (("json", "table"), ""), "db.transaction": (("json", "table"), ""),
    "ai.documentLoader": ((), "document"), "ai.embedding": ((), "vector"), "ai.retriever": ((), "document"),
}

"""Karta plánu jako uzel PR Lens (docs/plan-lens.md): id, pruh, popisek, souhrn, delta a odznaky.

Čisté funkce bez služby. Plán proti realitě: karta se `sourceRef` původu `existing`, jejíž cesta
v hlavním checkoutu existuje, je `unchanged` (kód stojí); všechno ostatní je `added` s odznakem
„plán“ (zatím jen záměr). Uzavřená karta (`done.confirmed`) nese odznak „hotovo“."""
import hashlib
import re

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*")
MAX_ID, MAX_LABEL, MAX_SUMMARY, MAX_EDGE_LABEL = 128, 120, 200, 80
# Pruhy podle otázky z docs/pravidla-struktury.md; karta bez vrstvy (sektor, starší uzel) jde do „plánu“.
LANES = (("frontend", "Frontend"), ("backend", "Backend"), ("database", "Databáze"),
         ("library", "Knihovna"), ("plan", "Plán"))
LANE_LABEL = dict(LANES)
NEIGHBOURS = ("okoli", "Sousední oblasti")
# Druh karty PR Lens řídí jen ikonu a tvar.
NODE_KIND = {"frontend": "ui", "backend": "module", "database": "datastore", "library": "package"}
# Port vazby → nejbližší druh hrany PR Lens: `next` je pořadí práce („potom tahle karta“), tedy
# volání dalšího kroku; tlačítko bloku je závislost; tok mezi oblastmi nese data.
EDGE_KIND = {"next": "call", "block": "dependency", "flow": "data"}
CARD_KINDS = ("node", "sector")
PLANNED, DONE = "plán", "hotovo"


def lens_id(prefix, raw):
    """Id PR Lens z id plátna; co neprojde vzorem nebo délkou, nahradí stabilní otisk."""
    candidate = f"{prefix}:{raw}"
    if len(candidate) <= MAX_ID and ID.fullmatch(candidate):
        return candidate
    return f"{prefix}:h" + hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:32]


def clip(text, limit):
    """Text na jeden řádek do `limit` znaků; prázdný → None (PR Lens nebere prázdné řetězce)."""
    flat = " ".join(str(text or "").split())
    if not flat:
        return None
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def first_sentence(text, limit=MAX_SUMMARY):
    flat = " ".join(str(text or "").split())
    match = re.search(r"[.!?](?=\s|$)", flat)
    return clip(flat[: match.end()] if match else flat, limit)


def label(node, fallback):
    return clip(node.get("name"), MAX_LABEL) or fallback


def clean_path(value):
    """Cesta zdroje relativní k repozitáři ve tvaru, který PR Lens přijme, jinak None."""
    if not isinstance(value, str):
        return None
    path = value.strip().strip("/")
    path = path.removeprefix("./")
    if not path or len(path) > 1024 or "\\" in path or re.match(r"[A-Za-z]:", path):
        return None
    if any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return path


def source_path(node):
    ref = node.get("sourceRef")
    return clean_path(ref.get("path")) if isinstance(ref, dict) else None


def layer(node):
    value = (node.get("card") or {}).get("layer") if isinstance(node.get("card"), dict) else None
    return value if value in NODE_KIND else "plan"


def is_card(node):
    return node.get("kind") in CARD_KINDS


def done_ids(state):
    """Karty uzavřené člověkem nebo autonomií (`done.confirmed`) ze stavu plochy."""
    nodes = (state or {}).get("nodes") or {}
    return {key for key, value in nodes.items()
            if isinstance(value, dict) and isinstance(value.get("done"), dict) and value["done"].get("confirmed") is True}


def realized(node, existing):
    ref = node.get("sourceRef")
    path = source_path(node)
    return isinstance(ref, dict) and ref.get("origin") == "existing" and path is not None and path in existing


def card_node(node, existing, done):
    """Uzel PR Lens jedné karty v pohledu oblasti."""
    real, path = realized(node, existing), source_path(node)
    badges = ([] if real else [PLANNED]) + ([DONE] if node["id"] in done else [])
    item = {"id": lens_id("card", node["id"]), "label": label(node, "Karta bez názvu"),
            "kind": NODE_KIND.get(layer(node), "service" if node.get("kind") == "sector" else "other"),
            "delta": "unchanged" if real else "added", "lane": layer(node)}
    subtitle = clip(path, MAX_LABEL)
    if subtitle:
        item["subtitle"] = subtitle
    summary = first_sentence(node.get("purpose"))
    if summary:
        item["summary"] = summary
    item["files"] = [{"path": path}] if real else []
    item["badges"] = badges
    return item


def report_label(state, edge_id):
    """Popisek hrany z poslední zprávy na vazbě (`handoff`, jinak `summary`), zkrácený."""
    report = ((state or {}).get("edges") or {}).get(edge_id)
    if not isinstance(report, dict):
        return None
    return first_sentence(report.get("handoff"), MAX_EDGE_LABEL) or first_sentence(report.get("summary"), MAX_EDGE_LABEL)


def edge(edge_id, source, target, kind, delta, text=None, emphasis=None):
    item = {"id": edge_id, "from": source, "to": target, "kind": kind, "delta": delta}
    if text:
        item["label"] = text
    if emphasis:
        item["emphasis"] = emphasis
    return item


def lanes_for(nodes):
    """Jen použité pruhy, v pevném pořadí (plán poslední, sousedé úplně vpravo)."""
    used = {item["lane"] for item in nodes}
    known = [*LANES, NEIGHBOURS]
    return [{"id": key, "label": text, "order": index} for index, (key, text) in enumerate(known) if key in used]

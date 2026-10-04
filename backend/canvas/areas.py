"""Členství v oblasti (`kind: "area"`) je geometrické, nikde se neukládá.

Oblast je dashovaný obdélník na plátně, který karty seskupuje podle polohy, ne podle
odkazu. Karta patří do oblasti na stejné vrstvě (stejný `parentId`), jejíž obdélník
`[x, x+w] × [y, y+h]` obsahuje střed karty. Střed karty (uzel/sektor) je `(x+180, y+120)`
(karta je široká 360 a vysoká zhruba 240), střed komentáře `(x+120, y+80)`. Když karta leží
uvnitř více oblastí zároveň, vyhrává nejmenší (podle plochy). Oblast sama do jiné oblasti
nikdy nepatří (stejně jako nikdy není rodičem, viz `graph.py`).
"""

# Odsazení středu karty od jejího levého horního rohu, podle druhu uzlu.
_CENTRE_OFFSET = {"node": (180, 120), "sector": (180, 120), "comment": (120, 80)}


def _centre(node):
    dx, dy = _CENTRE_OFFSET.get(node["kind"], (180, 120))
    return node["x"] + dx, node["y"] + dy


def area_of(node, nodes):
    """Vrátí uzel oblasti (`kind == "area"`), do které `node` geometricky patří, nebo None.

    `nodes` je seznam všech uzlů grafu (stejný tvar jako `graph["nodes"]`).
    """
    if node.get("kind") == "area":
        return None
    cx, cy = _centre(node)
    candidates = []
    for other in nodes:
        if other["kind"] != "area" or other["id"] == node["id"]:
            continue
        if other["parentId"] != node["parentId"]:
            continue
        size = other.get("size")
        if not size:
            continue
        x0, y0 = other["x"], other["y"]
        x1, y1 = x0 + size["w"], y0 + size["h"]
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            candidates.append(other)
    if not candidates:
        return None
    candidates.sort(key=lambda area: area["size"]["w"] * area["size"]["h"])
    return candidates[0]

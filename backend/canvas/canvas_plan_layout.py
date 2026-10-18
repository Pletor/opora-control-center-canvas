"""Poloha nových uzlů dávky plánu (`/api/canvas-plan`): auto-layout nebo bod vložení z katalogu.

Karta (uzel, sektor) je 360 × 240, komentář 240 × 160, oblast podle `size`; mezi tělesy zůstává
mezera 96. Na vrstvě (stejný `parentId`) se nové uzly kladou do mřížky pod všechny existující
uzly vrstvy, takže nic nepřekryjí a ani omylem nespadnou do cizí oblasti (členství v oblasti je
geometrické, viz `areas.py`). Karta, kterou dávka posadí do oblasti, se položí celá dovnitř
jejího obdélníku. Oblast je pružná: když se karta nevejde, rámeček vyroste – nejdřív do šířky
na `AREA_COLUMNS` sloupců karet, pak po řádcích dolů – ale jen tam, kde mu nestojí v cestě jiné
těleso vrstvy (cizí karta nebo oblast) a jen do `AREA_SIZE_MAX`. Teprve když vyrůst nemůže, je to
chyba dávky, ne karta přes okraj.
"""

CARD = (360, 240)
COMMENT = (240, 160)
GAP = 96
COLUMNS = 6
# Okraj uvnitř oblasti, aby karta nelepila na dashovaný rámeček.
AREA_PAD = 48
MAX_ROWS = 10000
# Pružná oblast: do šířky roste nejvýš na tolik sloupců karet, dál už jen po řádcích dolů.
AREA_COLUMNS = 3
# Stejný strop jako `AREA_SIZE_MAX` v `frontend/editor/canvas/area/logic/area-model.ts`.
AREA_SIZE_MAX = 20000


def body_size(node):
    if node["kind"] == "area":
        return node["size"]["w"], node["size"]["h"]
    return COMMENT if node["kind"] == "comment" else CARD


def body_rect(node):
    w, h = body_size(node)
    return node["x"], node["y"], w, h


def _clear(candidate, occupied):
    """Těleso se nepřekrývá s žádným obsazeným a drží od něj mezeru."""
    x, y, w, h = candidate
    return all(
        x + w + GAP <= ox or ox + ow + GAP <= x or y + h + GAP <= oy or oy + oh + GAP <= y
        for ox, oy, ow, oh in occupied
    )


def _centre_inside(body, area):
    """Těleso patří do oblasti stejně jako v `areas.py`: jeho střed leží v obdélníku oblasti."""
    x, y, w, h = body
    ax, ay, aw, ah = area
    return ax <= x + w / 2 <= ax + aw and ay <= y + h / 2 <= ay + ah


def _overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class Layer:
    """Volné místo na jedné vrstvě: existující tělesa a to, co na ni dávka už položila."""

    def __init__(self, existing):
        self.occupied = [body_rect(node) for node in existing]
        if self.occupied:
            self.x0 = min(r[0] for r in self.occupied)
            self.y0 = max(r[1] + r[3] for r in self.occupied) + GAP
        else:
            self.x0, self.y0 = 0, 0

    def place(self, size, area=None, position=None):
        """Vrátí (x, y) prvního volného místa v mřížce, nebo None, když se do oblasti nevejde.

        `area` je obdélník oblasti (x, y, w, h); bez ní se klade pod existující uzly vrstvy."""
        w, h = size
        step_x, step_y = CARD[0] + GAP, CARD[1] + GAP
        if area is None:
            x0, y0 = self.x0, self.y0
            width, rows = max(COLUMNS * step_x - GAP, w), MAX_ROWS
            blockers = self.occupied
        else:
            ax, ay, aw, ah = area
            x0, y0 = ax + AREA_PAD, ay + AREA_PAD
            width, height = aw - 2 * AREA_PAD, ah - 2 * AREA_PAD
            if w > width or h > height:
                return None
            rows = (height - h) // step_y + 1
            # Rámeček vlastní oblasti kartu neblokuje; ostatní tělesa ano.
            blockers = [r for r in self.occupied if r != tuple(area)]
        if position is not None:
            preferred = self._near(position, size, blockers, area)
            if preferred is not None:
                self.occupied.append((*preferred, w, h))
                return preferred
        for row in range(int(rows)):
            y = y0 + row * step_y
            x = x0
            while x + w <= x0 + width:
                candidate = (x, y, w, h)
                if _clear(candidate, blockers):
                    self.occupied.append(candidate)
                    return x, y
                x += step_x
        return None

    def grow(self, area, size):
        """Zvětší obdélník oblasti tak, aby se do něj vešla další karta `size`; vrátí nový obdélník nebo None.

        Nejdřív přidá sloupec karet (do `AREA_COLUMNS`), potom řádek; každý směr musí zůstat volný od
        těles vrstvy, která do oblasti nepatří, a pod `AREA_SIZE_MAX`. Obsazení vrstvy aktualizuje."""
        ax, ay, aw, ah = area
        w, h = size
        step_x, step_y = CARD[0] + GAP, CARD[1] + GAP
        columns = max(1, (aw - 2 * AREA_PAD + GAP) // step_x)
        wider = (ax, ay, max(aw, 2 * AREA_PAD + (columns + 1) * step_x - GAP), max(ah, h + 2 * AREA_PAD))
        taller = (ax, ay, max(aw, w + 2 * AREA_PAD), ah + step_y)
        attempts = [wider, taller] if columns < AREA_COLUMNS else [taller, wider]
        blockers = [r for r in self.occupied if r != tuple(area) and not _centre_inside(r, area)]
        for candidate in attempts:
            if candidate[2] > AREA_SIZE_MAX or candidate[3] > AREA_SIZE_MAX:
                continue
            if _clear(candidate, blockers):
                self.occupied = [candidate if r == tuple(area) else r for r in self.occupied]
                return candidate
        return None

    def _near(self, position, size, blockers, area):
        """Keep the drop point when free; otherwise try nearby collision-free positions."""
        x, y = position
        w, h = size
        if area is not None:
            ax, ay, aw, ah = area
            x = max(ax + AREA_PAD, min(x, ax + aw - AREA_PAD - w))
            y = max(ay + AREA_PAD, min(y, ay + ah - AREA_PAD - h))
        step_x, step_y = w + GAP, h + GAP
        offsets = [(0, 0)]
        # Bounded local search; existing auto-layout is the fallback for crowded layers.
        for radius in range(1, 13):
            ring = [(dx, dy) for dx in range(-radius, radius + 1)
                    for dy in range(-radius, radius + 1) if max(abs(dx), abs(dy)) == radius]
            offsets.extend(sorted(ring, key=lambda offset: (
                (offset[0] * step_x) ** 2 + (offset[1] * step_y) ** 2, offset[1], offset[0])))
        for dx, dy in offsets:
            cx, cy = x + dx * step_x, y + dy * step_y
            if abs(cx) > 1_000_000 or abs(cy) > 1_000_000:
                continue
            if area is not None and not (
                ax + AREA_PAD <= cx and cx + w <= ax + aw - AREA_PAD
                and ay + AREA_PAD <= cy and cy + h <= ay + ah - AREA_PAD
            ):
                continue
            if _clear((cx, cy, w, h), blockers):
                return cx, cy
        return None


def layout(new_nodes, existing_nodes, inside, positions=None):
    """Doplní `x`/`y` nových uzlů na místě.

    `new_nodes` jsou hotové uzly grafu (bez polohy) v pořadí dávky, `existing_nodes` uzly
    současného grafu, `inside` mapuje id nové karty na id oblasti, do které patří.
    Oblasti se kladou první, aby karty uvnitř znaly jejich obdélník. Plná oblast vyroste
    (`Layer.grow`, mění `size` uzlu oblasti na místě). Vrací id uzlu, který se do své oblasti
    nevešel ani po růstu, jinak None."""
    layers = {}
    by_id = {node["id"]: node for node in existing_nodes}

    def layer_of(parent_id):
        if parent_id not in layers:
            layers[parent_id] = Layer([n for n in existing_nodes if n["parentId"] == parent_id])
        return layers[parent_id]

    ordered = [n for n in new_nodes if n["kind"] == "area"] + [n for n in new_nodes if n["kind"] != "area"]
    for node in ordered:
        area_node = by_id[inside[node["id"]]] if node["id"] in inside else None
        layer = layer_of(node["parentId"])
        while True:
            area = body_rect(area_node) if area_node is not None else None
            spot = layer.place(body_size(node), area, (positions or {}).get(node["id"]))
            if spot is not None:
                break
            if area_node is None or area is None:
                return node["id"]
            grown = layer.grow(area, body_size(node))
            if grown is None:
                return node["id"]
            area_node["size"] = {"w": grown[2], "h": grown[3]}
        node["x"], node["y"] = spot
        by_id[node["id"]] = node
    return None


def overlapping(nodes):
    """Dvojice id těles na stejné vrstvě, která se překrývají (oblast a karta v ní se nepočítá)."""
    pairs = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if a["parentId"] != b["parentId"] or (a["kind"] == "area") != (b["kind"] == "area"):
                continue
            if _overlaps(body_rect(a), body_rect(b)):
                pairs.append((a["id"], b["id"]))
    return pairs

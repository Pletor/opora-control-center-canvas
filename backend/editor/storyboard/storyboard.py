"""Storyboard karty: validace, čtení a zápis s revizí, sekce pro node-brief (docs/storyboard-karty.md)."""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import UTC, datetime

from backend.editor.node.drawing_files import valid_file_id

ANIMATIONS = {"kulicka": "Kulička", "ritual-bodu-nula": "Rituál bodu nula", "kod": "Vlastní kód", "scena": "Webová scéna"}
EASES = ("linear", "in", "out", "inout", "hold")
SCHEMA = "opora.storyboard/1"
PAYLOAD_KEYS = {"project", "workspace", "nodeId", "expected_revision", "storyboard"}
BACKGROUND_DEFAULT = "#101418"
MOMENT_ID = re.compile(r"m-[0-9a-f]{8}")
SKETCH_LAYER = re.compile(r"sb/(?P<node>[A-Za-z0-9_-]{1,80})/(?P<moment>m-[0-9a-f]{8})")
FIELD_KEY = re.compile(r"[a-z][a-zA-Z0-9]{0,31}")
LAYER_ID = re.compile(r"[a-z][a-z0-9-]{0,31}")
FIELD_KINDS = ("number", "color", "boolean", "string")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BACKDROP_KEY = "storyboardBackdrop"
# Podklady (nahrané obrázky): účel texture = agent obrázek kreslí (drawImage/createPattern), reference = jen se jím řídí.
ASSET_ID = re.compile(r"a-[0-9a-f]{8}")
ASSET_PURPOSES = ("texture", "reference")
# colorUse: object = barva prvku/objektu (fill), tint = přebarvení textury (multiply přes obrázek). Bez barvy prázdné.
COLOR_USES = ("", "object", "tint")
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
ASSET_MIME = ("image/png", "image/jpeg", "image/webp")
MAX_ASSETS = 16
TEMPLATE_LAYERS = {"kulicka": ("pozadi", "stin", "kulicka"), "ritual-bodu-nula": ("pozadi", "koule", "jadro", "prekryv")}
ASSET_INSTRUCTION_KEYS = ("fileId", "purpose", "target", "momentId", "color", "colorUse", "note")
PLURALS = {
    "arrow": ("šipka", "šipky", "šipek"), "text": ("text", "texty", "textů"), "freedraw": ("kresba", "kresby", "kreseb"),
    "rectangle": ("obdélník", "obdélníky", "obdélníků"), "ellipse": ("elipsa", "elipsy", "elips"),
    "diamond": ("kosočtverec", "kosočtverce", "kosočtverců"), "line": ("čára", "čáry", "čar"),
    "image": ("obrázek", "obrázky", "obrázků"), "frame": ("rámeček", "rámečky", "rámečků"),
}


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} musí být konečné číslo.")
    if not low <= value <= high:
        raise ValueError(f"{name} musí být v rozsahu {low}–{high}.")
    return value


def _text(value, name, limit):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} musí být text.")
    if len(value) > limit:
        raise ValueError(f"{name} může mít nejvýše {limit} znaků.")
    return value


def _point(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} musí být bod {{x, y}}.")
    return {"x": _number(value.get("x"), f"{name}.x", 0, 1), "y": _number(value.get("y"), f"{name}.y", 0, 1)}


def _state(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("Stav momentu musí být objekt s nejvýše 32 klíči.")
    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 100:
            raise ValueError("Klíč stavu musí být text do 100 znaků.")
        if isinstance(item, bool):
            result[key] = item
        elif isinstance(item, (int, float)):
            result[key] = _number(item, f"state.{key}", -1e9, 1e9)
        elif isinstance(item, str):
            result[key] = _text(item, f"state.{key}", 100)
        else:
            raise ValueError(f"Hodnota state.{key} musí být číslo, text nebo ano/ne.")
    return result


def _annotation(item):
    if not isinstance(item, dict):
        raise ValueError("Anotace musí být objekt.")
    kind = item.get("kind")
    text = _text(item.get("text"), "Text anotace", 200)
    if kind == "arrow":
        return {"kind": "arrow", "from": _point(item.get("from"), "from"), "to": _point(item.get("to"), "to"), "text": text}
    if kind == "note":
        return {"kind": "note", "at": _point(item.get("at"), "at"), "text": text}
    raise ValueError("Anotace musí být šipka (arrow) nebo poznámka (note).")


def _sketch(value, node_id, moment_id):
    """Skica momentu {layer, fileId, imageStale}; text ze staré verze se zahodí."""
    if value is None or isinstance(value, str):
        return None
    if not isinstance(value, dict):
        raise ValueError("Skica momentu musí být objekt.")
    layer = value.get("layer")
    match = SKETCH_LAYER.fullmatch(layer) if isinstance(layer, str) else None
    if not match or match["moment"] != moment_id or (node_id is not None and match["node"] != node_id):
        raise ValueError("Vrstva skici musí být sb/<uzel>/<moment> tohoto momentu.")
    file_id = value.get("fileId")
    stale = bool(value.get("imageStale", False))
    if not isinstance(file_id, str) or len(file_id) > 80 or (not file_id and not stale) or (file_id and not valid_file_id(file_id)):
        raise ValueError("Skica momentu vyžaduje fileId nahraného PNG do 80 znaků (prázdné jen u imageStale).")
    return {"layer": layer, "fileId": file_id, "imageStale": stale}


def _flag(value):
    if not isinstance(value, bool):
        raise ValueError("Odpovězeno musí být ano/ne.")
    return value


def _code_field(item):
    if not isinstance(item, dict):
        raise ValueError("Pole kódu animace musí být objekt.")
    key = item.get("key")
    if not isinstance(key, str) or not FIELD_KEY.fullmatch(key):
        raise ValueError("Klíč pole kódu musí odpovídat [a-z][a-zA-Z0-9]{0,31}.")
    kind = item.get("kind")
    if kind not in FIELD_KINDS:
        raise ValueError("Druh pole kódu musí být number, color, boolean nebo string.")
    clean = {"key": key, "kind": kind, "label": _text(item.get("label"), "Popisek pole kódu", 80)}
    for name in ("min", "max", "step"):
        if item.get(name) is not None:
            clean[name] = _number(item[name], f"Pole kódu {key}.{name}", -1e9, 1e9)
    return clean


def _code_layer(item):
    if not isinstance(item, dict):
        raise ValueError("Vrstva kódu animace musí být objekt.")
    layer_id = item.get("id")
    if not isinstance(layer_id, str) or not LAYER_ID.fullmatch(layer_id):
        raise ValueError("Id vrstvy kódu musí odpovídat [a-z][a-z0-9-]{0,31}.")
    return {"id": layer_id, "label": _text(item.get("label"), "Popisek vrstvy kódu", 80)}


def _code(value):
    """Kód animace {source, fields, layers, title}; jen tvar, kód se nespouští."""
    if not isinstance(value, dict):
        raise ValueError("Animace „kod“ vyžaduje objekt code {source, fields, layers}.")
    source = value.get("source")
    if not isinstance(source, str) or not 1 <= len(source) <= 65536:
        raise ValueError("Zdroj kódu animace musí být text o 1–65536 znacích.")
    if CONTROL_CHARS.search(source):
        raise ValueError("Zdroj kódu animace nesmí obsahovat řídicí znaky kromě odřádkování a tabulátoru.")
    fields = value.get("fields", [])
    if not isinstance(fields, list) or len(fields) > 32:
        raise ValueError("Kód animace smí mít nejvýše 32 polí.")
    layers = value.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 16:
        raise ValueError("Kód animace musí mít 1–16 vrstev.")
    return {
        "source": source, "fields": [_code_field(f) for f in fields],
        "layers": [_code_layer(layer) for layer in layers], "title": _text(value.get("title"), "Název kódu animace", 120),
    }


def _scene(value):
    """Webová scéna {html, fields, layers, title}; jen tvar, dokument se nespouští."""
    if not isinstance(value, dict):
        raise ValueError("Animace „scena“ vyžaduje objekt scene {html, fields, layers}.")
    html = value.get("html")
    if not isinstance(html, str) or not 1 <= len(html) <= 262144:
        raise ValueError("Dokument scény musí být text o 1–262144 znacích.")
    if CONTROL_CHARS.search(html):
        raise ValueError("Dokument scény nesmí obsahovat řídicí znaky kromě odřádkování a tabulátoru.")
    fields = value.get("fields", [])
    if not isinstance(fields, list) or len(fields) > 32:
        raise ValueError("Scéna smí mít nejvýše 32 polí.")
    layers = value.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 16:
        raise ValueError("Scéna musí mít 1–16 vrstev.")
    return {
        "html": html, "fields": [_code_field(f) for f in fields],
        "layers": [_code_layer(layer) for layer in layers], "title": _text(value.get("title"), "Název scény", 120),
    }


def _asset(item, layers, moment_ids, taken=()):
    """Podklad {id, name, fileId, mimeType, purpose, target, momentId, color, colorUse, note, answered}; neznámý cíl = chyba."""
    if not isinstance(item, dict):
        raise ValueError("Podklad musí být objekt.")
    asset_id = item.get("id")
    if not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id) or asset_id in taken:
        asset_id = "a-" + uuid.uuid4().hex[:8]
    name = _text(item.get("name"), "Název podkladu", 120).strip() or asset_id
    file_id = item.get("fileId")
    if not valid_file_id(file_id):
        raise ValueError(f"Podklad „{name}“ vyžaduje fileId nahraného obrázku.")
    mime = item.get("mimeType")
    if mime not in ASSET_MIME:
        raise ValueError(f"Podklad „{name}“: obrázek musí být PNG, JPEG nebo WebP (mimeType).")
    purpose = item.get("purpose", "reference")
    if purpose not in ASSET_PURPOSES:
        raise ValueError(f"Podklad „{name}“: účel musí být texture (kreslí se) nebo reference (jen vzor).")
    target = _text(item.get("target"), "Cílová vrstva podkladu", 32)
    if target and target not in layers:
        raise ValueError(f"Podklad „{name}“: cílová vrstva „{target}“ v animaci není. Vrstvy: {', '.join(layers) or 'žádné'}.")
    moment_id = _text(item.get("momentId"), "Moment podkladu", 10)
    if moment_id and moment_id not in moment_ids:
        raise ValueError(f"Podklad „{name}“: moment „{moment_id}“ ve storyboardu není.")
    color = _text(item.get("color"), "Barva podkladu", 7)
    if color and not HEX_COLOR.fullmatch(color):
        raise ValueError(f"Podklad „{name}“: barva musí být #rrggbb.")
    color_use = item.get("colorUse", "")
    if color_use not in COLOR_USES:
        raise ValueError(f"Podklad „{name}“: colorUse musí být object (barva prvku) nebo tint (přebarvení textury).")
    if color and not color_use:
        raise ValueError(f"Podklad „{name}“: u barvy uveď colorUse (object = barva prvku, tint = přebarvení textury).")
    return {
        "id": asset_id, "name": name, "fileId": file_id, "mimeType": mime, "purpose": purpose, "target": target,
        "momentId": moment_id, "color": color.lower(), "colorUse": color_use if color else "",
        "note": _text(item.get("note"), "Pokyn k podkladu", 500), "answered": _flag(item.get("answered", False)),
    }


def animation_layers(board):
    """Id vrstev animace: u `kod` z code.layers, u šablon z TEMPLATE_LAYERS (stejné jako registr frontendu)."""
    if board.get("animation") == "kod":
        return tuple(layer["id"] for layer in board.get("code", {}).get("layers", []))
    if board.get("animation") == "scena":
        return tuple(layer["id"] for layer in board.get("scene", {}).get("layers", []))
    return TEMPLATE_LAYERS.get(board.get("animation"), ())


def _moment(item, duration, node_id=None, taken=()):
    if not isinstance(item, dict):
        raise ValueError("Moment musí být objekt.")
    moment_id = item.get("id")
    if not isinstance(moment_id, str) or not MOMENT_ID.fullmatch(moment_id) or moment_id in taken:
        moment_id = "m-" + uuid.uuid4().hex[:8]
    ease = item.get("ease", "linear")
    if ease not in EASES:
        raise ValueError("Zrychlení momentu musí být linear, in, out, inout nebo hold.")
    annotations = item.get("annotations", [])
    if not isinstance(annotations, list) or len(annotations) > 20:
        raise ValueError("Moment smí mít nejvýše 20 anotací.")
    sketch = _sketch(item.get("sketch"), node_id, moment_id)
    clean = {
        "id": moment_id,
        "t": _number(item.get("t"), "Čas momentu", 0, duration),
        "title": _text(item.get("title"), "Název momentu", 500),
        "shows": _text(item.get("shows"), "Co divák vidí", 500),
        "changes": _text(item.get("changes"), "Co se mění", 500),
        "comment": _text(item.get("comment"), "Komentář", 2000),
        "ease": ease,
        "answered": _flag(item.get("answered", False)),
        "state": _state(item.get("state")),
        "annotations": [_annotation(a) for a in annotations],
    }
    if sketch:
        clean["sketch"] = sketch
    return clean


def validate_storyboard(data, node_id=None) -> dict:
    """Ověří a znormalizuje storyboard; neznámé klíče zahodí, chybějící nepovinné doplní. Chyba = ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Storyboard musí být objekt.")
    if data.get("schema", SCHEMA) != SCHEMA:
        raise ValueError(f"Schéma storyboardu musí být {SCHEMA}.")
    animation = data.get("animation")
    if animation not in ANIMATIONS:
        raise ValueError("Neznámá animace storyboardu.")
    duration = _number(data.get("duration"), "Délka", 1, 120)
    fps = _number(data.get("fps", 60), "Snímková frekvence", 24, 60)
    size = data.get("size", {"w": 1920, "h": 1080})
    if not isinstance(size, dict):
        raise ValueError("Rozměr musí být objekt {w, h}.")
    moments = data.get("moments")
    if not isinstance(moments, list) or not 1 <= len(moments) <= 200:
        raise ValueError("Storyboard musí mít 1–200 momentů.")
    background = _text(data.get("background", BACKGROUND_DEFAULT), "Pozadí", 100) or BACKGROUND_DEFAULT
    clean_moments = []
    for m in moments:
        clean_moments.append(_moment(m, duration, node_id, {c["id"] for c in clean_moments}))
    result = {
        "schema": SCHEMA,
        "animation": animation,
        "title": _text(data.get("title"), "Název storyboardu", 500),
        "duration": duration,
        "fps": fps,
        "size": {"w": _number(size.get("w", 1920), "Šířka", 320, 4096), "h": _number(size.get("h", 1080), "Výška", 320, 4096)},
        "ground": _number(data.get("ground", 0.8), "Podlaha", 0, 1),
        "background": background,
        "moments": sorted(clean_moments, key=lambda m: m["t"]),
    }
    if animation == "kod":
        result["code"] = _code(data.get("code"))
    if animation == "scena":
        result["scene"] = _scene(data.get("scene"))
    assets = data.get("assets", [])
    if not isinstance(assets, list) or len(assets) > MAX_ASSETS:
        raise ValueError(f"Storyboard smí mít nejvýše {MAX_ASSETS} podkladů.")
    layers, moment_ids = animation_layers(result), {m["id"] for m in clean_moments}
    result["assets"] = []
    for item in assets:
        result["assets"].append(_asset(item, layers, moment_ids, {a["id"] for a in result["assets"]}))
    return result


def _moment_input(moment):
    """Vstup člověka k momentu: komentář, šipky a PNG skici; změna znovu otevře práci agenta."""
    sketch = moment.get("sketch") if isinstance(moment.get("sketch"), dict) else None
    sketch_key = f"{sketch.get('fileId', '')}|{'stale' if sketch.get('imageStale') else ''}" if sketch else ""
    return (str(moment.get("comment", "")).strip(), json.dumps(moment.get("annotations", []), sort_keys=True), sketch_key)


def _has_input(moment):
    comment, _, sketch_key = _moment_input(moment)
    return bool(comment or moment.get("annotations") or sketch_key)


def reopen_changed(clean, stored):
    """`answered: true` smí zůstat jen u momentu a podkladu, jehož vstup člověka se od uloženého stavu nezměnil.

    Zápis (člověka i agenta) tak nemůže nový komentář, šipku, skicu ani pokyn/barvu/cíl podkladu označit za vyřízené.
    """
    old_moments = {m.get("id"): m for m in (stored or {}).get("moments", []) if isinstance(m, dict)}
    for moment in clean["moments"]:
        before = old_moments.get(moment["id"])
        if moment["answered"] and (before is None or _moment_input(before) != _moment_input(moment)):
            moment["answered"] = False
    old_assets = {a.get("id"): a for a in (stored or {}).get("assets", []) if isinstance(a, dict)}
    for asset in clean.get("assets", []):
        before = old_assets.get(asset["id"])
        if asset["answered"] and (before is None or any(before.get(k, "") != asset[k] for k in ASSET_INSTRUCTION_KEYS)):
            asset["answered"] = False
    return clean


def _now():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pt(point):
    return f"({point['x']:.2f}, {point['y']:.2f})"


def _plural(kind, count):
    one, few, many = PLURALS.get(kind, (kind, kind, kind))
    return f"{count} {one if count == 1 else few if 2 <= count <= 4 else many}"


def sketch_summary(scene):
    """Souhrn scény skici: počty podle typu a texty prvků (max 10, po 80 znacích); podklad se vynechá."""
    counts, texts = {}, []
    for element in scene.get("elements", []):
        custom = element.get("customData")
        if element.get("isDeleted") or (isinstance(custom, dict) and custom.get(BACKDROP_KEY)):
            continue
        kind = element.get("type")
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "text" and str(element.get("text", "")).strip():
            texts.append(str(element["text"]).strip())
    parts = [_plural(kind, n) for kind, n in counts.items()]
    quoted = [f"„{t[:80]}“" for t in texts[:10]]
    if not parts:
        return ""
    return ", ".join(parts) + (": " + ", ".join(quoted) if quoted else "")


def _sentence(item):
    if item.get("kind") == "arrow":
        return f"šipka z {_pt(item['from'])} do {_pt(item['to'])}: {item.get('text', '')}"
    return f"poznámka u {_pt(item['at'])}: {item.get('text', '')}"


def _workflow(moments, assets=(), saved_at="", revision=0):
    """Co čeká na agenta: momenty se vstupem člověka (komentář, šipky, skica) bez odpovědi a podklady bez odpovědi."""
    open_ = [m for m in moments if _has_input(m) and not m.get("answered", False)]
    open_assets = [a for a in assets if isinstance(a, dict) and not a.get("answered", False)]
    parts = []
    if open_:
        listed = ", ".join(f"t={m.get('t')} s „{m.get('title', '')}“" for m in open_[:5])
        parts.append(f"Reaguj na {len(open_)} momentů s novým komentářem: {listed}")
    if open_assets:
        listed = ", ".join(f"„{a.get('name', a.get('id'))}“ ({a.get('purpose')}{' → ' + a['target'] if a.get('target') else ''})" for a in open_assets[:5])
        parts.append(f"Použij {len(open_assets)} podkladů bez odpovědi: {listed}")
    if not parts:
        return {"openComments": 0, "openAssets": 0, "next": "Žádný nový komentář; čekej na člověka."
                + (f" Storyboard naposledy uložen {saved_at} (revize {revision}); komentář napsaný později a neuložený tlačítkem Uložit tu není vidět." if saved_at else "")}
    return {"openComments": len(open_), "openAssets": len(open_assets), "next": "; ".join(parts)}


class StoryboardService:
    def __init__(self, canvas):
        self.canvas = canvas

    def _path(self, project, workspace, node_id):
        return self.canvas.folder(project).storyboard(workspace, node_id)

    @staticmethod
    def _stored(path):
        """Uložený storyboard; smazaný nechává náhrobek `{deleted, revision}`, aby CAS nešel obejít návratem k revizi 0."""
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        return None if stored.get("deleted") else stored

    @staticmethod
    def _revision(path):
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("revision", 0)
        except FileNotFoundError:
            return 0

    @staticmethod
    def _write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _card_view(self, project, workspace, node_id):
        view = self.canvas.view(project, workspace)  # neznámý projekt/workspace = ValueError
        node = next((n for n in view["graph"]["nodes"] if n["id"] == node_id), None)
        if node is None:
            raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
        if node.get("kind") not in ("node", "sector"):
            raise ValueError("Storyboard patří kartě nebo sektoru pracovního kontextu.")
        return view

    @staticmethod
    def _backfill_ids(stored):
        """Starší storyboardy bez `id` momentů dostanou stabilní id při prvním čtení; vrací True při změně."""
        if not stored or not isinstance(stored.get("moments"), list):
            return False
        taken = {m.get("id") for m in stored["moments"] if isinstance(m, dict)}
        changed = False
        for moment in stored["moments"]:
            if not isinstance(moment, dict):
                continue
            moment_id = moment.get("id")
            if isinstance(moment_id, str) and MOMENT_ID.fullmatch(moment_id):
                continue
            new_id = "m-" + uuid.uuid4().hex[:8]
            while new_id in taken:
                new_id = "m-" + uuid.uuid4().hex[:8]
            taken.add(new_id)
            moment["id"] = new_id
            changed = True
        return changed

    def read(self, project, workspace, node_id, revision=None):
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            from database.repositories.storyboard_revisions import StoryboardRevisions
            view = self.canvas.view(project, workspace)
            repo = StoryboardRevisions(self.canvas.db_for(project), project, workspace, node_id)
            if revision is not None and repo.latest() is not None:
                value = repo.read(revision)  # Historical owned source survives deletion of its graph card.
            else:
                self._card_view(project, workspace, node_id)
                value = self.source(project, workspace, node_id)
                if revision is not None:
                    value = repo.read(revision)
        animations = [{"id": key, "label": label} for key, label in ANIMATIONS.items()]
        return {"storyboard": value["storyboard"], "revision": value["revision"], "readOnly": bool(view["readOnly"]), "animations": animations}

    def source(self, project, workspace, node_id):
        """SQL is authoritative after import. Empty reads never create a source row."""
        from database.repositories.storyboard_revisions import StoryboardRevisions
        db = self.canvas.db_for(project)
        repo = StoryboardRevisions(db, project, workspace, node_id)
        path = self._path(project, workspace, node_id)
        if repo.latest() is None and path.exists():
            with self.canvas.lock_for(project):
                db = self.canvas.db_for(project)
                repo = StoryboardRevisions(db, project, workspace, node_id)
                if db.in_transaction:
                    repo.import_legacy(path, self._backfill_ids)
                else:
                    with db:
                        db.execute("BEGIN IMMEDIATE")
                        repo.import_legacy(path, self._backfill_ids)
        return repo.read()

    def save_in_transaction(self, project, workspace, node_id, expected, board):
        from database.repositories.storyboard_revisions import StoryboardRevisions
        db = self.canvas.db_for(project)
        if not db.in_transaction:
            raise RuntimeError("Storyboard save requires the caller's transaction.")
        current = self.source(project, workspace, node_id)
        if expected != current["revision"]:
            raise ValueError("Storyboard se změnil v jiném okně. Obnovte ho.")
        clean = None if board is None else validate_storyboard(board, node_id)
        if clean is None and current["storyboard"] is None:
            return current
        if clean is not None:
            self._check_asset_files(project, clean)
            reopen_changed(clean, current["storyboard"])
        record = {"deleted": True} if clean is None else clean
        record.update(revision=expected + 1, updatedAt=_now())
        return StoryboardRevisions(db, project, workspace, node_id).append(expected, record)

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
            raise ValueError("Neplatný formát uložení storyboardu.")
        project, workspace, node_id = payload["project"], payload["workspace"], payload["nodeId"]
        expected = payload["expected_revision"]
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError("Neplatná revize storyboardu.")
        board = payload["storyboard"]
        clean = None if board is None else validate_storyboard(board, node_id)
        with self.canvas.graph_lock_for(project):
            view = self._card_view(project, workspace, node_id)
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení.")
            with self.canvas.lock_for(project):
                db = self.canvas.db_for(project)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    value = self.save_in_transaction(project, workspace, node_id, expected, clean)
                return {"revision": value["revision"]}

    def _stored_mimes(self, project, ids):
        if not ids:
            return {}
        rows = self.canvas.db_for(project).execute(
            f"SELECT file_id, mime_type FROM drawing_files WHERE project_id=? AND file_id IN ({','.join('?' * len(ids))})", (project, *ids))
        return {row[0]: row[1] for row in rows}

    def _check_asset_files(self, project, clean):
        """Každý podklad (a PNG skici) musí mít obrázek v `drawing_files` projektu a podklad i shodný typ; jinak se neuloží."""
        assets = clean.get("assets", [])
        sketches = [(m["sketch"]["fileId"], m) for m in clean["moments"] if m.get("sketch", {}).get("fileId")]
        stored = self._stored_mimes(project, list({a["fileId"] for a in assets} | {f for f, _ in sketches}))
        for asset in assets:
            if asset["fileId"] not in stored:
                raise ValueError(f"Obrázek podkladu „{asset['name']}“ není nahraný ({asset['fileId']}). Nahrajte ho přes /api/drawing-file.")
            if stored[asset["fileId"]] != asset["mimeType"]:
                raise ValueError(f"Podklad „{asset['name']}“ udává {asset['mimeType']}, nahraný obrázek je {stored[asset['fileId']]}.")
        for file_id, moment in sketches:
            if file_id not in stored:
                raise ValueError(f"PNG skici momentu t={moment['t']} s není nahrané ({file_id}).")

    def sketch_layers(self, project, workspace, node_id):
        """Povolené vrstvy skic karty: sb/<nodeId>/<momentId> všech jejích momentů."""
        with self.canvas.lock_for(project):
            stored = self.source(project, workspace, node_id)["storyboard"]
        moments = stored.get("moments", []) if stored else []
        return {f"sb/{node_id}/{m['id']}" for m in moments if isinstance(m.get("id"), str)}

    def mark_sketch_stale(self, project, workspace, node_id, moment_id):
        """Scénu skici změnil někdo bez exportu PNG: moment dostane imageStale (bez skici ji založí) a revize se zvedne."""
        with self.canvas.graph_lock_for(project), self.canvas.lock_for(project):
            stored = self.source(project, workspace, node_id)["storyboard"]
            moment = next((m for m in (stored or {}).get("moments", []) if m.get("id") == moment_id), None)
            if moment is None:
                return
            if isinstance(moment.get("sketch"), dict):
                moment["sketch"]["imageStale"] = True
            else:  # agent skicu zakládá: scéna je, PNG ještě ne
                moment["sketch"] = {"layer": f"sb/{node_id}/{moment_id}", "fileId": "", "imageStale": True}
            moment["answered"] = False  # skica se změnila: moment znovu čeká na reakci
            stored["revision"] = stored.get("revision", 0) + 1
            stored["updatedAt"] = _now()
            from database.repositories.storyboard_revisions import StoryboardRevisions
            db = self.canvas.db_for(project)
            if db.in_transaction:
                StoryboardRevisions(db, project, workspace, node_id).append(stored["revision"] - 1, stored)
            else:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    StoryboardRevisions(db, project, workspace, node_id).append(stored["revision"] - 1, stored)

    def _sketch_with_summary(self, project, workspace, moment):
        sketch = moment.get("sketch")
        if not isinstance(sketch, dict):
            return ""
        with self.canvas.reading(project):
            scene = self.canvas.drawings.read((project, workspace, sketch.get("layer", "")))["scene"]
        return {**sketch, "summary": sketch_summary(scene)}

    def _assets_for_brief(self, project, workspace, assets):
        """Podklady s cestou ke skutečnému obrázku (API i CLI) a příznakem, zda obrázek v projektu opravdu je."""
        ids = [a.get("fileId", "") for a in assets if a.get("fileId")]
        with self.canvas.reading(project):
            missing = self.canvas.drawing_files.missing(self.canvas.db_for(project), project, ids) if ids else set()
        return [
            {
                **a, "available": bool(a.get("fileId")) and a["fileId"] not in missing,
                "read": f"/api/drawing-files?project={project}&workspace={workspace}&ids={a.get('fileId', '')}",
                "cli": f"opora_read.py drawing-file --project {project} --workspace {workspace} --id {a.get('fileId', '')} --out <soubor>",
            }
            for a in assets
        ]

    def brief_section(self, project, workspace, node_id):
        """Sekce `storyboard` pro node-brief; None, když karta storyboard nemá."""
        with self.canvas.lock_for(project):
            stored = self.source(project, workspace, node_id)["storyboard"]
        if not stored:
            return None
        moments = stored.get("moments", [])
        assets = [a for a in stored.get("assets", []) if isinstance(a, dict)]
        section = {
            "animation": stored.get("animation"),
            "duration": stored.get("duration"),
            "layers": list(animation_layers(stored)),
            "revision": stored.get("revision", 0),
            "updatedAt": stored.get("updatedAt", ""),
            "workflow": _workflow(moments, assets, stored.get("updatedAt", ""), stored.get("revision", 0)),
            "assets": self._assets_for_brief(project, workspace, assets),
            "moments": [
                {
                    "id": m.get("id"), "t": m.get("t"), "title": m.get("title", ""), "shows": m.get("shows", ""),
                    "changes": m.get("changes", ""), "comment": m.get("comment", ""), "answered": bool(m.get("answered", False)), "sketch": self._sketch_with_summary(project, workspace, m),
                    "state": m.get("state", {}), "annotations": m.get("annotations", []),
                    "annotationsText": [_sentence(a) for a in m.get("annotations", [])],
                }
                for m in moments
            ],
        }
        if stored.get("animation") == "kod" and isinstance(stored.get("code"), dict):
            code = stored["code"]
            section["code"] = {key: code.get(key, "" if key in ("source", "title") else []) for key in ("source", "fields", "layers", "title")}
        if stored.get("animation") == "scena" and isinstance(stored.get("scene"), dict):
            scene = stored["scene"]
            section["scene"] = {key: scene.get(key, "" if key in ("html", "title") else []) for key in ("title", "html", "fields", "layers")}
        return section

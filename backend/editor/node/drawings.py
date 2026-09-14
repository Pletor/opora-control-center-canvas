import json
import math
from urllib.parse import urlsplit

MAX_ELEMENTS = 2000
MAX_SCENE_BYTES = 1_500_000
MAX_ID_LENGTH = 120
SUPPORTED_TYPES = {"rectangle", "diamond", "ellipse", "line", "arrow", "freedraw", "text", "frame"}
FORBIDDEN_FIELDS = {"fileId", "fileIds", "embeddable", "embeddableUrl", "iframe", "dataURL"}


def _json_safe(value, depth=0):
    """Ověří serializovatelnost bez změny běžných Excalidraw polí."""
    if depth > 64:
        raise ValueError("Scéna je příliš hluboká.")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("Číslo kresby přesahuje bezpečný rozsah prohlížeče.")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Scéna obsahuje neplatné číslo.")
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise ValueError("Scéna obsahuje neplatný Unicode.") from exc
        return
    if isinstance(value, list):
        for item in value:
            _json_safe(item, depth + 1)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Scéna obsahuje neplatný klíč.")  # noqa: TRY004 - klientská validační chyba mapovaná na HTTP 409
            _json_safe(key, depth + 1)
            _json_safe(item, depth + 1)
        return
    raise ValueError("Scéna obsahuje nepodporovanou hodnotu.")


def validate_scene(scene):
    if (
        not isinstance(scene, dict)
        or set(scene) != {"elements"}
        or not isinstance(scene["elements"], list)
    ):
        raise ValueError("Neplatný formát kresby.")
    elements = scene["elements"]
    if len(elements) > MAX_ELEMENTS:
        raise ValueError("Kresba překročila povolený počet prvků.")
    ids = set()
    for element in elements:
        if not isinstance(element, dict):
            raise ValueError("Neplatný prvek kresby.")  # noqa: TRY004 - klientská validační chyba mapovaná na HTTP 409
        if any(key in element for key in FORBIDDEN_FIELDS):
            raise ValueError("Vložené soubory a externí embed nejsou podporované.")
        element_id = element.get("id")
        if (
            not isinstance(element_id, str)
            or not element_id
            or len(element_id) > MAX_ID_LENGTH
            or element_id in ids
        ):
            raise ValueError("Neplatné nebo duplicitní ID prvku.")
        if not isinstance(element.get("type"), str) or element["type"] not in SUPPORTED_TYPES:
            raise ValueError("Nepodporovaný typ kresby.")
        if element["type"] == "text" and (
            not isinstance(element.get("text"), str) or len(element["text"]) > 20000
        ):
            raise ValueError("Neplatný text kresby.")
        if element["type"] in ("line", "arrow", "freedraw"):
            points = element.get("points")
            if not isinstance(points, list) or not points:
                raise ValueError("Čára vyžaduje pole bodů.")
            for point in points:
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(
                        type(v) not in (int, float) or abs(v) > 10000000 or not math.isfinite(v)
                        for v in point
                    )
                ):
                    raise ValueError("Neplatné body kresby.")
        for key in ("x", "y", "width", "height"):
            value = element.get(key)
            if (
                type(value) not in (int, float)
                or abs(value) > 10_000_000
                or not math.isfinite(value)
            ):
                raise ValueError("Neplatná geometrie kresby.")
        if element["width"] < 0 or element["height"] < 0:
            raise ValueError("Rozměry kresby nesmí být záporné.")
        link = element.get("link")
        parsed = urlsplit(link) if isinstance(link, str) else None
        if link is not None and (
            parsed is None or parsed.scheme.lower() not in ("http", "https") or not parsed.netloc
        ):
            raise ValueError("Odkaz kresby musí být HTTP(S).")
        ids.add(element_id)
    _json_safe(scene)
    try:
        encoded = json.dumps(
            scene, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Kresbu nelze bezpečně uložit.") from exc
    if len(encoded) > MAX_SCENE_BYTES:
        raise ValueError("Kresba je příliš velká.")
    return encoded.decode("utf-8")


class DrawingStore:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, scope):
        row = self.canvas.db_for(scope[0]).execute(
            """SELECT revision,scene,saved_at FROM drawing_revisions
               WHERE project_id=? AND workspace_id=? AND layer_id=? ORDER BY revision DESC LIMIT 1""",
            scope,
        ).fetchone()
        if row is None:
            return {"scene": {"elements": []}, "revision": 0, "saved_at": None}
        return {
            "scene": json.loads(row["scene"]),
            "revision": row["revision"],
            "saved_at": row["saved_at"],
        }

    def save(self, scope, expected_revision, scene, saved_at):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Neplatná očekávaná revize kresby.")
        encoded = validate_scene(scene)
        db = self.canvas.db_for(scope[0])
        try:
            db.execute("BEGIN IMMEDIATE")
            current = self.read(scope)
            if current["revision"] != expected_revision:
                raise ValueError("Kresba se změnila v jiném okně. Obnovte ji.")
            revision = expected_revision + 1
            db.execute(
                "INSERT INTO drawing_revisions VALUES(?,?,?,?,?,?)",
                (*scope, revision, encoded, saved_at),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {"scene": scene, "revision": revision, "saved_at": saved_at}

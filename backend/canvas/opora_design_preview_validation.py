"""Tvar dokladu `evidence.preview` (docs/design-nahled.md §3): čistá validace, neplatné se odmítne, nic se neopravuje.

`preview = {prNumber, headSha, designMdSha256, proposedDesignMd?, screenshots: [{label, viewport, stage?, dataURL}]}`.
Screenshot je jen PNG v data URL (hlavička `\\x89PNG` se ověřuje), do 2 MiB; klient nikdy neposílá cestu ani ID
souboru, ID odvodí server z obsahu. Režim karty server bere ze svého záznamu, ne od agenta."""
import hashlib
import re

from backend.editor.node.drawing_files import decode_file

SHA, SHA256 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")
TEXT = re.compile(r"[^\x00-\x1f\x7f]{1,60}")
MODES = ("brand", "explore")
MAX_SHOTS = 8  # na jednu hlavu PR jednoho běhu, součet přes všechna odeslání
MAX_PNG_BYTES = 2 * 1024 * 1024
MAX_PROPOSAL_BYTES = 64 * 1024
FIELDS = {"prNumber", "headSha", "designMdSha256", "screenshots"}
SHOT_FIELDS = {"label", "viewport", "dataURL"}


def file_id(digest):
    """Obsahová adresa v `drawing_files`: stejný PNG = stejné ID, cizí ID nikdy nepřepíše."""
    return "preview_" + digest


def _text(value, name):
    if not isinstance(value, str) or TEXT.fullmatch(value) is None or value != value.strip():
        raise ValueError(f"preview {name} must be 1–60 printable characters without outer spaces.")
    return value


def _viewport(value):
    if not isinstance(value, dict) or set(value) != {"width", "height"}:
        raise ValueError("preview viewport must be {width, height}.")
    for key, top in (("width", 8000), ("height", 20000)):
        if type(value[key]) is not int or not 120 <= value[key] <= top:
            raise ValueError(f"preview viewport.{key} must be an integer between 120 and {top}.")
    return {"width": value["width"], "height": value["height"]}


def screenshot(value):
    """`{label, viewport, stage?, dataURL}` → metadata + bajty PNG (`fileId` a `sha256` z obsahu)."""
    if not isinstance(value, dict) or not SHOT_FIELDS <= set(value) or set(value) - SHOT_FIELDS - {"stage"}:
        raise ValueError("A screenshot needs label, viewport, dataURL and optionally stage.")
    data_url = value["dataURL"]
    if not isinstance(data_url, str) or len(data_url) > (MAX_PNG_BYTES // 3 + 1) * 4 + 64:
        raise ValueError(f"A screenshot must be a PNG of at most {MAX_PNG_BYTES} bytes.")
    _, _, data = decode_file({"id": "preview", "mimeType": "image/png", "dataURL": data_url})
    if len(data) > MAX_PNG_BYTES:
        raise ValueError(f"A screenshot must be a PNG of at most {MAX_PNG_BYTES} bytes.")
    digest = hashlib.sha256(data).hexdigest()
    meta = {"label": _text(value["label"], "label"), "viewport": _viewport(value["viewport"]),
            "stage": _text(value["stage"], "stage") if "stage" in value else None,
            "fileId": file_id(digest), "sha256": digest, "bytes": len(data)}
    return meta, data


def validate_preview(value):
    """Normalizovaný doklad (bez režimu) a bajty PNG podle `fileId`; dekódování PNG běží mimo zámky projektu."""
    if not isinstance(value, dict) or not FIELDS <= set(value) or set(value) - FIELDS - {"proposedDesignMd"}:
        raise ValueError("preview needs prNumber, headSha, designMdSha256, screenshots and optionally proposedDesignMd.")
    if type(value["prNumber"]) is not int or not 0 < value["prNumber"] < 10**9:
        raise ValueError("Invalid preview prNumber.")
    if not isinstance(value["headSha"], str) or SHA.fullmatch(value["headSha"]) is None:
        raise ValueError("preview.headSha must be a full lowercase commit SHA.")
    design = value["designMdSha256"]
    if design is not None and (not isinstance(design, str) or SHA256.fullmatch(design) is None):
        raise ValueError("preview.designMdSha256 must be a sha256 hex digest or null.")
    proposal = value.get("proposedDesignMd")
    if proposal is not None and (not isinstance(proposal, str) or not proposal.strip()
                                 or len(proposal.encode("utf-8")) > MAX_PROPOSAL_BYTES):
        raise ValueError(f"proposedDesignMd must be nonempty Markdown of at most {MAX_PROPOSAL_BYTES} bytes.")
    shots = value["screenshots"]
    if not isinstance(shots, list) or not 1 <= len(shots) <= MAX_SHOTS:
        raise ValueError(f"preview.screenshots must hold 1–{MAX_SHOTS} screenshots.")
    metas, files = [], {}
    for item in shots:
        meta, data = screenshot(item)
        if any(other["label"] == meta["label"] for other in metas):
            raise ValueError("Screenshot labels must be unique for one head.")
        metas.append(meta)
        files[meta["fileId"]] = data
    result = {"prNumber": value["prNumber"], "headSha": value["headSha"], "designMdSha256": design,
              "screenshots": metas}
    if proposal is not None:
        result["proposedDesignMd"] = proposal
    return result, files


def with_mode(value, mode):
    """Doklad doplněný o režim karty ze serveru.

    `brand`: `designMdSha256` je otisk DESIGN.md, podle kterého screenshoty vznikly (null = projekt DESIGN.md nemá),
    `proposedDesignMd` zakázaný. `explore`: karta z DESIGN.md nečerpá, `designMdSha256` musí být null a smí přijít
    `proposedDesignMd` (návrh nového DESIGN.md, Markdown do 64 KiB)."""
    if mode not in MODES:
        raise ValueError("Unknown design mode.")
    if mode == "explore" and value["designMdSha256"] is not None:
        raise ValueError("An explore card must not draw from DESIGN.md: designMdSha256 must be null.")
    if mode == "brand" and "proposedDesignMd" in value:
        raise ValueError("proposedDesignMd is only for an explore card.")
    return {**value, "mode": mode}

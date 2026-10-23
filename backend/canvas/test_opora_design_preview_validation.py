"""Tvar `evidence.preview`: jen PNG s pravou hlavičkou, strop velikosti a počtu, štítky, pravidla režimu."""
import base64
import hashlib

import pytest

from backend.canvas.opora_design_preview_validation import (
    MAX_PNG_BYTES,
    validate_preview,
    with_mode,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
HEAD = "c" * 40
DESIGN = "a" * 64


def data_url(data=PNG, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def shot(label="mobil světlý", data=PNG, **extra):
    return {"label": label, "viewport": {"width": 390, "height": 844}, "dataURL": data_url(data), **extra}


def preview(*shots, **extra):
    return {"prNumber": 7, "headSha": HEAD, "designMdSha256": DESIGN, "screenshots": list(shots) or [shot()], **extra}


def test_valid_preview_gets_a_content_address_and_no_client_path():
    value, files = validate_preview(preview(shot(stage="kontroly"), shot("desktop tmavý", PNG + b"\x01")))
    first = value["screenshots"][0]
    digest = hashlib.sha256(PNG).hexdigest()
    assert first == {"label": "mobil světlý", "viewport": {"width": 390, "height": 844}, "stage": "kontroly",
                     "fileId": "preview_" + digest, "sha256": digest, "bytes": len(PNG)}
    assert value["screenshots"][1]["stage"] is None and files[first["fileId"]] == PNG
    assert with_mode(value, "brand")["mode"] == "brand"


@pytest.mark.parametrize("item", [
    shot(data=b"GIF89a" + b"\x00" * 10),  # wrong magic under a PNG data URL
    {**shot(), "dataURL": data_url(PNG, "image/jpeg")},  # only PNG is accepted
    {**shot(), "dataURL": "data:image/png;base64,!!!"},
    {**shot(), "dataURL": "file:///etc/passwd"},
    {**shot(), "path": "C:/x.png"},  # no path input from clients
    {**shot(), "fileId": "preview_x"},
    shot(label=""), shot(label=" x"), shot(label="x" * 61), shot(label="a\nb"),
    {**shot(), "viewport": {"width": 50, "height": 844}}, {**shot(), "viewport": {"width": 390}},
    {**shot(), "viewport": {"width": True, "height": 844}}, shot(stage=""),
])
def test_invalid_screenshot_is_refused(item):
    with pytest.raises(ValueError):
        validate_preview(preview(item))


def test_size_and_count_caps():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_PNG_BYTES
    with pytest.raises(ValueError, match="at most"):
        validate_preview(preview(shot(data=big)))
    with pytest.raises(ValueError, match="1–8"):
        validate_preview(preview(*[shot(f"s{index}", PNG + bytes([index])) for index in range(9)]))
    with pytest.raises(ValueError, match="1–8"):
        validate_preview({**preview(), "screenshots": []})
    with pytest.raises(ValueError, match="unique"):
        validate_preview(preview(shot("a"), shot("a", PNG + b"\x01")))
    with pytest.raises(ValueError, match="proposedDesignMd"):
        validate_preview(preview(proposedDesignMd="x" * (64 * 1024 + 1)))


@pytest.mark.parametrize("value", [
    None, {}, {**preview(), "extra": 1}, preview(prNumber=0), preview(prNumber=True), preview(headSha="C" * 40),
    preview(headSha="c" * 39), preview(designMdSha256="xyz"), preview(proposedDesignMd="  "),
])
def test_invalid_preview_fields(value):
    with pytest.raises(ValueError):
        validate_preview(value)


def test_mode_rules_brand_follows_design_md_explore_does_not():
    brand, _ = validate_preview(preview())
    with pytest.raises(ValueError, match="must not draw from DESIGN.md"):
        with_mode(brand, "explore")
    proposal, _ = validate_preview(preview(designMdSha256=None, proposedDesignMd="# Nový směr\n"))
    assert with_mode(proposal, "explore")["proposedDesignMd"] == "# Nový směr\n"
    with pytest.raises(ValueError, match="only for an explore"):
        with_mode(proposal, "brand")
    without, _ = validate_preview(preview(designMdSha256=None))
    assert with_mode(without, "brand")["designMdSha256"] is None  # project without DESIGN.md
    with pytest.raises(ValueError):
        with_mode(brand, "other")

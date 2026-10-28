import os
import time

import pytest

from tools.opora import apply_environment, frontend_stale, load_config, load_dotenv, merge, resolve

CONFIG = """
[app]
host = "127.0.0.1"
port = 8740
data = ".data/production"
open_browser = true

[build]
frontend = "auto"
command = "npm run build"

[profiles.preview]
port = 8790
data = ".data/preview"
open_browser = false
frontend = "never"

[integrations]
graphify_python = "C:/py/python.exe"
"""


def test_app_profile_and_overrides(tmp_path):
    config_file = tmp_path / "opora.toml"
    config_file.write_text(CONFIG, encoding="utf-8")
    config = load_config(config_file, tmp_path / "missing.local.toml")

    base = resolve(config)
    assert (base["port"], base["data"], base["open_browser"], base["frontend"]) == (8740, ".data/production", True, "auto")
    assert base["integrations"] == {"graphify_python": "C:/py/python.exe"}

    preview = resolve(config, "preview")
    assert (preview["port"], preview["data"], preview["open_browser"], preview["frontend"], preview["profile"]) == (8790, ".data/preview", False, "never", "preview")

    custom = resolve(config, "preview", port=8791, data=".data/kopie")
    assert (custom["port"], custom["data"]) == (8791, ".data/kopie")

    with pytest.raises(ValueError):
        resolve(config, "neexistuje")
    with pytest.raises(ValueError):
        resolve(config, port=70000)


def test_local_override_merges_deeply(tmp_path):
    (tmp_path / "opora.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "opora.local.toml").write_text('[app]\nport = 8745\n[profiles.preview]\ndata = ".data/moje"\n', encoding="utf-8")
    config = load_config(tmp_path / "opora.toml", tmp_path / "opora.local.toml")
    assert resolve(config)["port"] == 8745
    assert resolve(config, "preview")["data"] == ".data/moje"
    assert resolve(config, "preview")["port"] == 8790
    assert merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 9}, "d": 3}) == {"a": {"b": 9, "c": 2}, "d": 3}


def test_environment_from_settings_never_overrides_existing():
    settings = resolve({"app": {"port": 8791, "data": "d"}, "integrations": {"graphify_python": "py"}})
    environ = {"OPORA_GRAPHIFY_PYTHON": "existing"}
    applied = apply_environment(settings, environ)
    assert applied == []
    assert environ["OPORA_CANVAS_PORT"] == "8791"
    assert environ["OPORA_CANVAS_DATA"] == "d"
    assert environ["OPORA_GRAPHIFY_PYTHON"] == "existing"
    assert environ["OPORA_JEV_PROVIDER"] == "typesafe"


def test_jev_provider_from_local_config(tmp_path):
    (tmp_path / "opora.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "opora.local.toml").write_text('[jev]\nprovider = "celeris"\n', encoding="utf-8")
    settings = resolve(load_config(tmp_path / "opora.toml", tmp_path / "opora.local.toml"))
    assert settings["jev_provider"] == "celeris"
    environ = {}
    apply_environment(settings, environ)
    assert environ["OPORA_JEV_PROVIDER"] == "celeris"


def test_embed_origins_default_empty_and_local_override(tmp_path):
    (tmp_path / "opora.toml").write_text(CONFIG, encoding="utf-8")
    base = resolve(load_config(tmp_path / "opora.toml", tmp_path / "missing.local.toml"))
    assert base["embed_origins"] == []
    environ = {"OPORA_CANVAS_EMBED_ORIGINS": "http://stale.test"}
    apply_environment(base, environ)
    assert environ["OPORA_CANVAS_EMBED_ORIGINS"] == ""

    (tmp_path / "opora.local.toml").write_text('[app]\nembed_origins = ["http://localhost:4600"]\n', encoding="utf-8")
    local = resolve(load_config(tmp_path / "opora.toml", tmp_path / "opora.local.toml"))
    assert local["embed_origins"] == ["http://localhost:4600"]
    apply_environment(local, environ)
    assert environ["OPORA_CANVAS_EMBED_ORIGINS"] == "http://localhost:4600"


def test_invalid_embed_origin_fails_config():
    with pytest.raises(ValueError, match="Neplatný původ v \\[app\\] embed_origins"):
        resolve({"app": {"embed_origins": ["http://localhost:4600/*"]}})


def test_frontend_stale_detects_missing_or_older_build(tmp_path):
    (tmp_path / "frontend").mkdir()
    source = tmp_path / "frontend/App.tsx"
    source.write_text("x", encoding="utf-8")
    assert frontend_stale(tmp_path) is True
    (tmp_path / "dist").mkdir()
    index = tmp_path / "dist/index.html"
    index.write_text("<html>", encoding="utf-8")
    now = time.time()
    os.utime(source, (now - 100, now - 100))
    os.utime(index, (now, now))
    assert frontend_stale(tmp_path) is False
    os.utime(source, (now + 100, now + 100))
    assert frontend_stale(tmp_path) is True


def test_mirror_off_by_default_and_on_only_with_enabled(tmp_path):
    (tmp_path / "opora.toml").write_text(CONFIG, encoding="utf-8")
    environ = {"OPORA_MIRROR_URL": "http://127.0.0.1:1"}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", tmp_path / "nic.toml")), environ)
    assert environ["OPORA_MIRROR_URL"] == "" and environ["OPORA_MIRROR_PROJECTS"] == ""
    local = tmp_path / "opora.local.toml"
    local.write_text('[mirror]\nenabled = true\nurl = "http://127.0.0.1:8750"\nprojects = ["p1", "p2"]\n', encoding="utf-8")
    environ = {}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", local)), environ)
    assert environ["OPORA_MIRROR_URL"] == "http://127.0.0.1:8750"
    assert environ["OPORA_MIRROR_PROJECTS"] == "p1,p2"
    local.write_text('[mirror]\nenabled = "ano"\nurl = "http://127.0.0.1:8750"\n', encoding="utf-8")
    environ = {}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", local)), environ)
    assert environ["OPORA_MIRROR_URL"] == ""


def test_strazci_section_becomes_worker_environment(tmp_path):
    (tmp_path / "opora.toml").write_text(CONFIG, encoding="utf-8")
    environ = {}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", tmp_path / "nic.toml")), environ)
    assert "OPORA_GUARDS_WORKER" not in environ and "OPORA_GUARDS_SECONDS" not in environ
    local = tmp_path / "opora.local.toml"
    local.write_text("[strazci]\nenabled = false\nseconds = 12\n", encoding="utf-8")
    environ = {"OPORA_GUARDS_SECONDS": "5"}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", local)), environ)
    assert environ["OPORA_GUARDS_WORKER"] == "0" and environ["OPORA_GUARDS_SECONDS"] == "5"
    local.write_text('[strazci]\nenabled = "ne"\nseconds = 12\n', encoding="utf-8")
    environ = {}
    apply_environment(resolve(load_config(tmp_path / "opora.toml", local)), environ)
    assert "OPORA_GUARDS_WORKER" not in environ and environ["OPORA_GUARDS_SECONDS"] == "12.0"


def test_dotenv_fills_only_missing_and_never_prints(tmp_path, capsys):
    secret = "tajna-hodnota-" + "x" * 8
    (tmp_path / ".env").write_text(
        "﻿# komentář\n\nCELERIS_API_KEY=\"" + secret + "\"\nexport OPORA_X='a b'\nSYSTEM_KEY=z-env\n"
        "neplatny radek\n1BAD=x\nPRAZDNY=\n", encoding="utf-8")
    environ = {"SYSTEM_KEY": "ze-systemu"}
    assert load_dotenv(tmp_path / ".env", environ) == 3
    assert environ["CELERIS_API_KEY"] == secret
    assert environ["OPORA_X"] == "a b" and environ["PRAZDNY"] == ""
    assert environ["SYSTEM_KEY"] == "ze-systemu"
    assert "1BAD" not in environ
    out = capsys.readouterr()
    assert secret not in out.out + out.err
    assert load_dotenv(tmp_path / "chybi.env", {}) == 0

import os
import time

import pytest

from tools.opora import apply_environment, frontend_stale, load_config, merge, resolve

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

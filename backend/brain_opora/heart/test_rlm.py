"""Knihovna dílny `rlm.py`: data `ctx`, čtení zdroje jen uvnitř kořene, grep, dávky a `sub` s falešným voláním
(strop 20 za run, pořadí odpovědí, hloubka 1, prostředí bez klíčů). Skutečný `claude` se nevolá."""
import json
import threading
import time

import pytest

from backend.brain_opora.heart import rlm


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "src"
    (root / "src" / "pages").mkdir(parents=True)
    (root / "node_modules" / "x").mkdir(parents=True)
    (root / "src" / "pages" / "Home.tsx").write_text("const a = 1;\nexport function Home() {}\n", encoding="utf-8")
    (root / "README.md").write_text("Zahrada\n", encoding="utf-8")
    (root / "node_modules" / "x" / "i.js").write_text("export function Home() {}\n", encoding="utf-8")
    (tmp_path / "tajne.txt").write_text("heslo", encoding="utf-8")
    monkeypatch.setenv("OPORA_SOURCE_ROOT", str(root))
    return root


def test_files_read_and_grep_stay_inside_the_source(source):
    assert rlm.files() == ["README.md", "src/pages/Home.tsx"]
    assert rlm.files("src/*.tsx") == ["src/pages/Home.tsx"]
    assert rlm.read("src/pages/Home.tsx", 2, 2) == "export function Home() {}\n"
    assert rlm.read("README.md") == "Zahrada\n"
    assert rlm.grep(r"function Home") == [{"path": "src/pages/Home.tsx", "line": 2, "text": "export function Home() {}"}]
    for escape in ("../tajne.txt", str(source.parent / "tajne.txt")):
        with pytest.raises(ValueError):
            rlm.read(escape)
    with pytest.raises(ValueError):
        rlm.grep("heslo", ["../tajne.txt"])


def test_load_chunks_and_missing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(rlm, "HERE", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "tasks.json").write_text('[{"taskId": "ht_1"}]', encoding="utf-8")
    assert rlm.load("tasks") == [{"taskId": "ht_1"}]
    with pytest.raises(ValueError):
        rlm.load("../tasks")
    assert rlm.chunks(range(5), 2) == [[0, 1], [2, 3], [4]]
    with pytest.raises(ValueError):
        rlm.chunks([1], 0)
    monkeypatch.delenv("OPORA_SOURCE_ROOT", raising=False)
    with pytest.raises(RuntimeError):
        rlm.files()


@pytest.fixture
def subs(tmp_path, monkeypatch):
    log = tmp_path / ".sub-1.jsonl"
    monkeypatch.setenv("OPORA_RLM_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-tajne")
    monkeypatch.delenv("OPORA_RLM_DEPTH", raising=False)
    monkeypatch.setattr(rlm, "find_claude", lambda: "claude")
    monkeypatch.setattr(rlm, "_RESERVED", [0])
    return log


def test_sub_answers_in_input_order_with_cost_and_no_keys(subs):
    seen, lock = [], threading.Lock()

    def call(line, text, env):
        with lock:
            seen.append((line, text, env))
        number = int(text.rsplit("\n", 1)[1].strip('"'))
        time.sleep(0.01 * (5 - number))  # pozdější položky doběhnou dřív
        return f"odpověď {number}", 0.001

    answers = rlm.sub("Ohodnoť", [str(i) for i in range(5)], parallel=4, call=call)
    assert answers == [f"odpověď {i}" for i in range(5)]
    line, text, env = seen[0]
    assert line[:4] == ["claude", "-p", "--model", "haiku"] and line[line.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in line and text.startswith("Ohodnoť\n")
    assert "ANTHROPIC_API_KEY" not in env and env["OPORA_RLM_DEPTH"] == "1"
    costs = [json.loads(row)["costUsd"] for row in subs.read_text(encoding="utf-8").splitlines()]
    assert costs == [0.001] * 5


def test_sub_is_capped_at_20_per_run_and_has_depth_one(subs, monkeypatch):
    def call(line, text, env):
        return "ok", 0.0

    assert rlm.sub("p", range(15), call=call) == ["ok"] * 15
    with pytest.raises(RuntimeError, match="20"):
        rlm.sub("p", range(6), call=call)
    assert rlm.sub("p", range(5), call=call) == ["ok"] * 5
    with pytest.raises(RuntimeError):
        rlm.sub("p", ["x"], call=call)
    monkeypatch.setenv("OPORA_RLM_DEPTH", "1")
    with pytest.raises(RuntimeError, match="hloubka"):
        rlm.sub("p", ["x"], call=call)
    monkeypatch.delenv("OPORA_RLM_DEPTH")
    monkeypatch.delenv("OPORA_RLM_LOG")
    with pytest.raises(RuntimeError, match="run"):
        rlm.sub("p", ["x"], call=call)


def test_call_parses_the_json_result_and_survives_failures(monkeypatch):
    class Done:
        def __init__(self, stdout):
            self.stdout = stdout

    outputs = iter([json.dumps({"result": "ano", "total_cost_usd": 0.002, "is_error": False}),
                    json.dumps({"result": "limit", "is_error": True, "total_cost_usd": 0}), "nic"])
    monkeypatch.setattr(rlm.subprocess, "run", lambda *args, **kwargs: Done(next(outputs)))
    assert rlm._call(["claude"], "x", {}) == ("ano", 0.002)
    assert rlm._call(["claude"], "x", {}) == (None, 0.0)
    assert rlm._call(["claude"], "x", {}) == (None, 0.0)

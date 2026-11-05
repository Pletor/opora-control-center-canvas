"""Ollama: modely a GPU přes falešný transport, VRAM přes falešný nvidia-smi."""
from backend.agi_pletor.llm_settings import ollama
from backend.agi_pletor.llm_settings.conftest import fake_run

GB = 1024 ** 3


def transport(method, path, body=None, timeout=None):
    assert method == "GET" and timeout == ollama.TIMEOUT
    if path == "/api/tags":
        return {"models": [{"name": "qwen3:14b", "size": 9 * GB}, {"name": "nomic-embed", "size": GB // 4}]}
    return {"models": [{"name": "qwen3:14b", "size_vram": int(10.5 * GB)}]}


def test_models_gpu_and_vram():
    out = ollama.read(transport, fake_run({"nvidia-smi": "12282, 9000\n"}))
    assert out == {"available": True,
                   "installed": [{"name": "qwen3:14b", "sizeGb": 9.0}, {"name": "nomic-embed", "sizeGb": 0.2}],
                   "loaded": [{"name": "qwen3:14b", "vramGb": 10.5}],
                   "vram": {"totalGb": 12.0, "usedGb": 8.8, "freeGb": 3.2}}


def test_ollama_down_keeps_vram_and_missing_gpu_is_none():
    def down(*args):
        raise ConnectionRefusedError("odmítnuto")

    out = ollama.read(down, fake_run({"nvidia-smi": FileNotFoundError("nvidia-smi")}))
    assert out["available"] is False and "odmítnuto" in out["reason"] and out["vram"] is None
    assert out["installed"] == [] and out["loaded"] == []

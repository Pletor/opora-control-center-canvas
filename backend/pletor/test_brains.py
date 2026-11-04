"""Mozky Pletora s falešným transportem (žádná síť): přepínací věty, volba modelu, nastavení, tah Ollamy a jeho chyby,
a přepnutí příkazem v chatu přes `Pletor.message` (příkaz nejde do modelu, tah pak jde do Ollamy)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN, seed
from backend.pletor import brains, store
from backend.pletor.service import Pletor

TAGS = {"models": [{"name": "qwen3:14b"}, {"name": "qwen3-embedding:0.6b"}, {"name": "gemma4:12b"}]}


class Ollama:
    """Falešná Ollama: `/api/tags` vrací `tags`, `/api/chat` vrací `content` (nebo vyhodí `chat_error`)."""

    def __init__(self, tags=TAGS, content='{"reply": "Lokálně.", "actions": []}', chat_error=None):
        self.tags, self.content, self.chat_error, self.calls = tags, content, chat_error, []

    def __call__(self, method, path, body=None, timeout=None):
        self.calls.append((method, path, body))
        if path == "/api/tags":
            if isinstance(self.tags, Exception):
                raise self.tags
            return self.tags
        if self.chat_error:
            raise self.chat_error
        return {"message": {"role": "assistant", "content": self.content}}


@pytest.mark.parametrize(("text", "expected"), [
    ("Přepni na lokální mozek", ("ollama", None)),
    ("prepni na LOKALNI MOZEK.", ("ollama", None)),
    ("Pletore, přepni se na Ollamu!", ("ollama", None)),
    ("switch to local brain", ("ollama", None)),
    ("Přepni zpět na Claude", ("claude", None)),
    ("přepni zpátky na předplatné", ("claude", None)),
    ("Switch back to cloud", ("claude", None)),
    ("přepni na model qwen3:8b", ("ollama", "qwen3:8b")),
    ("Přepni na lokální mozek a pak mi shrň stav srdce", None),
    ("Co je lokální mozek?", None),
    ("Postav web o dvou stránkách.", None),
])
def test_command(text, expected):
    assert brains.command(text) == expected


def test_models_skip_embeddings_and_prefer_gemma_or_qwen35():
    assert brains.models(Ollama()) == ["qwen3:14b", "gemma4:12b"]
    assert brains.default_model(["qwen3:14b", "gemma4:12b"]) == "gemma4:12b"
    assert brains.default_model(["llama3:8b", "qwen3:14b"]) == "llama3:8b"
    assert brains.default_model([]) is None
    assert brains.models(Ollama(tags=ConnectionRefusedError("odmítnuto"))) == []
    assert brains.models(Ollama(tags={"nic": 1})) == []


def test_settings_default_and_switch(tmp_path):
    assert store.settings(tmp_path) == {"brain": "claude", "ollamaModel": None}
    (tmp_path / store.SETTINGS).write_text("{rozbitý", encoding="utf-8")
    assert store.settings(tmp_path)["brain"] == "claude"
    ok, reply = brains.switch(tmp_path, "ollama", transport=Ollama())
    assert ok and "Lokální mozek zapnut" in reply
    assert store.settings(tmp_path) == {"brain": "ollama", "ollamaModel": "gemma4:12b"}
    assert brains.switch(tmp_path, "ollama", "qwen3:14b", transport=Ollama())[0]
    assert brains.switch(tmp_path, "claude", transport=Ollama()) == (True, "Zpátky na Claude, pane.")
    # zpět na lokální: drží naposled zvolený model, pokud v Ollamě pořád je
    brains.switch(tmp_path, "ollama", transport=Ollama())
    assert brains.status(tmp_path, Ollama()) == {"brain": "ollama", "model": "qwen3:14b",
                                                 "available": ["qwen3:14b", "gemma4:12b"]}


def test_switch_fails_and_stays(tmp_path):
    ok, reply = brains.switch(tmp_path, "ollama", transport=Ollama(tags=ConnectionRefusedError("odmítnuto")))
    assert not ok and "Zůstávám na Claude" in reply
    ok, reply = brains.switch(tmp_path, "ollama", "llama9", transport=Ollama())
    assert not ok and "llama9" in reply and "qwen3:14b" in reply
    assert store.settings(tmp_path)["brain"] == "claude"


def test_ollama_turn_ok_and_errors():
    fake = Ollama(content='{"reply": "Hotovo.", "actions": [{"type": "vault_note", "text": "x"}]}')
    assert brains.ollama_turn("qwen3:14b", "PODKLADY", fake) == ("Hotovo.", [{"type": "vault_note", "text": "x"}])
    body = fake.calls[0][2]
    assert body["format"] == "json" and body["stream"] is False and body["messages"][1]["content"] == "PODKLADY"
    with pytest.raises(RuntimeError, match="neodpovídá"):
        brains.ollama_turn("qwen3:14b", "x", Ollama(chat_error=json.JSONDecodeError("vadný JSON", "<", 0)))
    with pytest.raises(RuntimeError, match="neodpovídá"):
        brains.ollama_turn("qwen3:14b", "x", Ollama(chat_error=ConnectionRefusedError("odmítnuto")))
    with pytest.raises(RuntimeError, match="prázdnou"):
        brains.ollama_turn("qwen3:14b", "x", Ollama(content=""))


def test_chat_command_switches_without_model_and_turn_goes_to_ollama(tmp_path):
    def no_claude(*args, **kwargs):
        raise AssertionError("příkaz ani lokální tah nesmí spustit claude")

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        pletor = Pletor(client.app.state.service, client.app.state.heart, runner=no_claude, find=lambda: "claude")
        pletor.transport = fake = Ollama()
        assert pletor.message("draft", "draft", "Přepni na lokální mozek") == {
            "reply": "Lokální mozek zapnut, pane (gemma4:12b). Teď nic nestojím.", "actions": []}
        assert pletor.message("draft", "draft", "Jak se máš?")["reply"] == "Lokálně."
        assert fake.calls[-1][2]["model"] == "gemma4:12b"
        fake.chat_error = ConnectionRefusedError("odmítnuto")
        assert "neodpovídá" in pletor.message("draft", "draft", "Haló?")["reply"]
        assert pletor.message("draft", "draft", "přepni zpět na Claude")["reply"] == "Zpátky na Claude, pane."
        roles = [m["role"] for m in pletor.state("draft", "draft")["messages"]]
        assert roles == ["human", "pletor"] * 4

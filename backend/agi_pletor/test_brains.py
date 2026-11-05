"""Mozky Pletora s falešným transportem (žádná síť): přepínací věty, volba modelu, nastavení, tah Ollamy a jeho chyby,
a přepnutí příkazem v chatu přes `Pletor.message` (příkaz nejde do modelu, tah pak jde do Ollamy)."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN, seed
from backend.agi_pletor import brains, store
from backend.agi_pletor.service import Pletor

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
    ("Přepni na lokální mozek.", ("ollama", None)),
    ("přepni na místní model", ("ollama", None)),
    ("zapni lokální mozek", ("ollama", None)),
    ("Přepni na Klaud", ("claude", None)),
    ("Přepni na Claude na předplatné.", ("claude", None)),
    ("použij Clauda", ("claude", None)),
    ("přepni zpět na cloud", ("claude", None)),
    ("Přepni na lokální mozek a pak mi shrň stav srdce a řekni, co je nového v projektu", None),
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
    assert brains.ollama_turn("qwen3:14b", "PODKLADY", "Zapiš x.", transport=fake) == (
        "Hotovo.", [{"type": "vault_note", "text": "x"}])
    assert brains.ollama_turn("qwen3:14b", "PODKLADY", "Ahoj", transport=Ollama(content="Ahoj, pane.")) == (
        "Ahoj, pane.", [])  # prostý text bez JSON je odpověď bez akcí
    for error in (json.JSONDecodeError("vadný JSON", "<", 0), ConnectionRefusedError("odmítnuto")):
        with pytest.raises(RuntimeError, match="neodpovídá"):
            brains.ollama_turn("qwen3:14b", "P", "x", transport=Ollama(chat_error=error))
    with pytest.raises(RuntimeError, match="prázdnou"):
        brains.ollama_turn("qwen3:14b", "P", "x", transport=Ollama(content=""))


HISTORY = [{"role": "human", "text": f"otázka {n}"} if n % 2 == 0 else {"role": "pletor", "text": f"odpověď {n}"}
           for n in range(12)]


def test_ollama_turn_sends_roles_history_and_options():
    fake = Ollama(content="Nová odpověď.")
    brains.ollama_turn("qwen3:8b", "PODKLADY X", "Jak se máš?", HISTORY, fake)
    body = fake.calls[0][2]
    assert "format" not in body and body["stream"] is False and body["think"] is False
    assert body["keep_alive"] == "30m"
    assert body["options"] == {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1, "num_ctx": 8192}
    system, *past, last = body["messages"]
    # podklady jsou v systému před pravidly lokálního mozku, poslední user je jen zpráva člověka
    assert system["role"] == "system" and system["content"].index("PODKLADY X") < system["content"].index(brains.LOCAL)
    assert [m["content"] for m in past] == [item["text"] for item in HISTORY[-brains.HISTORY:]]
    assert [m["role"] for m in past] == ["user", "assistant"] * 4
    assert last == {"role": "user", "content": "Jak se máš?"}


def test_ollama_turn_retries_once_when_it_repeats_itself():
    history = [{"role": "human", "text": "Ahoj"}, {"role": "pletor", "text": "Dnes je středa. Nic se neplánovalo."}]

    class Repeating(Ollama):
        def __call__(self, method, path, body=None, timeout=None):
            self.content = "dnes je  středa. nic se neplánovalo" if not self.calls else "Mám se dobře."
            return super().__call__(method, path, body, timeout)

    fake = Repeating()
    assert brains.ollama_turn("qwen3:14b", "P", "Jak se máš?", history, fake) == ("Mám se dobře.", [])
    assert len(fake.calls) == 2
    assert fake.calls[1][2]["messages"][-1]["content"].endswith(
        "(Předchozí odpověď neodpovídala dotazu, odpověz přímo na: Jak se máš?)")
    # stejná zpráva člověka smí dostat stejnou odpověď, bez opakování tahu
    same = Ollama(content="Dnes je středa. Nic se neplánovalo.")
    brains.ollama_turn("qwen3:14b", "P", "Ahoj", history, same)
    assert len(same.calls) == 1


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
        # historie rozhovoru z messages.jsonl, bez právě položené zprávy, ta jde jako poslední user
        assert fake.calls[-1][2]["messages"][1:] == [
            {"role": "user", "content": "Přepni na lokální mozek"},
            {"role": "assistant", "content": "Lokální mozek zapnut, pane (gemma4:12b). Teď nic nestojím."},
            {"role": "user", "content": "Jak se máš?"}]
        assert "PROJEKT: draft" in fake.calls[-1][2]["messages"][0]["content"]
        fake.chat_error = ConnectionRefusedError("odmítnuto")
        assert "neodpovídá" in pletor.message("draft", "draft", "Haló?")["reply"]
        assert pletor.message("draft", "draft", "přepni zpět na Claude")["reply"] == "Zpátky na Claude, pane."
        roles = [m["role"] for m in pletor.state("draft", "draft")["messages"]]
        assert roles == ["human", "pletor"] * 4

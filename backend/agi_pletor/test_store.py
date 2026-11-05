"""Rozhovor Pletora: řádky po projektu a prostoru, vadné řádky se přeskočí, rozhodnutí do brain/ projektu."""
import json

from backend.agi_pletor import store


def test_messages_are_filtered_by_project_and_workspace(tmp_path):
    store.append_message(tmp_path, "t1", "p1", "draft", "human", "Ahoj")
    store.append_message(tmp_path, "t2", "p2", "draft", "human", "Jinde")
    store.append_message(tmp_path, "t3", "p1", "draft", "pletor", "Dobrý den.")
    with (tmp_path / store.MESSAGES).open("a", encoding="utf-8") as file:
        file.write("{rozbitý\n")
    assert store.messages(tmp_path, "p1", "draft") == [{"role": "human", "text": "Ahoj", "at": "t1"},
                                                        {"role": "pletor", "text": "Dobrý den.", "at": "t3"}]
    assert store.messages(tmp_path, "p1", "draft", last=1)[0]["at"] == "t3"
    assert store.messages(tmp_path / "nic", "p1", "draft") == []


def test_decision_is_one_json_line(tmp_path):
    store.append_decision(tmp_path / "brain", "t1", "draft", "Web má dvě stránky.")
    line = (tmp_path / "brain" / store.DECISIONS).read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"at": "t1", "workspace": "draft", "text": "Web má dvě stránky.", "by": "pletor"}

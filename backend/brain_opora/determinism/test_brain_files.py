"""Soubory `brain/` pro snímek: zprávy člověka po pracovních prostorech a deník dávek, poškozené řádky se přeskočí."""
from backend.brain_opora.determinism import brain_files


def test_messages_are_appended_filtered_by_workspace_and_capped(tmp_path):
    brain = tmp_path / "brain"
    for i in range(7):
        brain_files.append_message(brain, f"t{i}", "main", f"zpráva {i}")
    brain_files.append_message(brain, "t9", "draft", "jinde")
    with (brain / brain_files.MESSAGES).open("a", encoding="utf-8") as file:
        file.write("rozbitý řádek\n[1, 2]\n")
    assert [entry["text"] for entry in brain_files.messages(brain, "main")] == [f"zpráva {i}" for i in range(2, 7)]
    assert brain_files.messages(brain, "draft") == [{"at": "t9", "workspace": "draft", "text": "jinde"}]
    assert brain_files.messages(tmp_path / "nic", "main") == []


def test_relayed_message_keeps_via(tmp_path):
    brain = tmp_path / "brain"
    assert brain_files.append_message(brain, "t", "main", "záměr", via="orchestrator") == {
        "at": "t", "workspace": "main", "text": "záměr", "via": "orchestrator"}
    assert "via" not in brain_files.append_message(brain, "t", "main", "člověk", via=None)
    assert [entry.get("via") for entry in brain_files.messages(brain, "main")] == ["orchestrator", None]


def test_journal_reads_last_entries_and_survives_missing_file(tmp_path):
    assert brain_files.journal(tmp_path) == []
    (tmp_path / brain_files.JOURNAL).write_text("\n".join(f'{{"at": "t{i}", "summary": "s{i}"}}' for i in range(8)),
                                                encoding="utf-8")
    assert [entry["summary"] for entry in brain_files.journal(tmp_path, 3)] == ["s5", "s6", "s7"]
    assert len(brain_files.journal(tmp_path, None)) == 8  # None = celý deník (ctx journal)

"""Otázky Pletora srdci na disku: založení, upřesnění jedné otevřené, odpověď (kontroly, idempotence) a uzavření."""
from types import SimpleNamespace

import pytest

from backend.agi_pletor import questions
from backend.brain_opora.determinism.gate_payloads import GateError


@pytest.fixture
def service(tmp_path):
    folder = SimpleNamespace(path=tmp_path)
    return SimpleNamespace(folder=lambda project: folder)


def test_one_open_question_gets_refined_and_closing_frees_the_slot(service):
    first, refined = questions.ask(service, "p1", "draft", "Jak má vypadat přihlášení?", "t1")
    assert not refined and first["id"].startswith("pq_") and first["status"] == "asked"
    again, refined = questions.ask(service, "p1", "draft", "Hlavně e-mail, nebo i Google?", "t2")
    assert refined and again["id"] == first["id"] and again["refinements"] == [{"text": "Hlavně e-mail, nebo i Google?", "at": "t2"}]
    assert len(questions.listing(service, "p1")) == 1
    assert questions.close(service, "p1", "Jen e-mail.", "t3")["closedNote"] == "Jen e-mail."
    assert questions.current(questions.listing(service, "p1")) is None
    assert questions.close(service, "p1", "x", "t4") is None
    new, refined = questions.ask(service, "p1", "draft", "Jiná otázka", "t5")
    assert not refined and new["id"] != first["id"] and len(questions.listing(service, "p1")) == 2


def test_answer_checks_saves_once_and_refinement_reopens(service):
    asked, _ = questions.ask(service, "p1", "draft", "Jak?", "t1")
    qid = asked["id"]
    for args, status in ((("pq_nic", "A", [], False, None), 404), ((qid, "  ", [], False, None), 422),
                         ((qid, "A", [], True, " "), 422), ((qid, "A", ["r"] * 11, False, None), 422)):
        with pytest.raises(GateError) as error:
            questions.answer(service, "p1", *args, "agent:heart", "t2")
        assert error.value.status == status
    done, changed = questions.answer(service, "p1", qid, "Jen e-mail.", ["vf_1"], False, None, "agent:heart", "t2")
    assert changed and done["status"] == "answered" and done["answers"][0]["refs"] == ["vf_1"]
    same, changed = questions.answer(service, "p1", qid, "Jen e-mail.", ["vf_1"], False, None, "agent:heart", "t3")
    assert not changed and len(same["answers"]) == 1
    assert questions.ask(service, "p1", "draft", "A Google?", "t4")[0]["status"] == "asked"
    unknown, changed = questions.answer(service, "p1", qid, "Nevím.", [], True, "Chybí přístup k účtu.", "agent:heart", "t5")
    assert changed and unknown["answers"][-1] == {"text": "Nevím.", "refs": [], "unknown": True,
                                                  "reason": "Chybí přístup k účtu.", "at": "t5", "by": "agent:heart"}
    questions.close(service, "p1", "Hotovo.", "t6")
    with pytest.raises(GateError) as error:
        questions.answer(service, "p1", qid, "Pozdě.", [], False, None, "agent:heart", "t7")
    assert error.value.status == 409

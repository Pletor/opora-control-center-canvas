"""OP-B171BE: absent repository stays an honest draft in the actual emitted instructions."""
from backend.brain_opora.heart import command
from backend.brain_opora.heart.test_command import seeded
from backend.canvas.graph import CARD_VALUES
from backend.canvas.opora_plan_steps import validate_steps


def test_emitted_planning_instructions_keep_missing_sources_explicit(tmp_path):
    db = seeded(tmp_path)
    skills = command.heart_skills(db, tmp_path)
    brain = tmp_path / "runtime"
    _, _, prompt = command.write_config(brain, skills)
    instructions = [prompt.read_text(encoding="utf-8"),
                    (brain / "skills" / "zadani-na-kanvas.md").read_text(encoding="utf-8")]
    for text in instructions:
        assert "files: []" in text and "card.status: draft" in text
        assert "konkrétní revizi" in text and "nikoli nalezený soubor" in text
        assert "nejprve zpřístupnit a prohlédnout zdroj" in text
    assert "Ostrý `plan` plán sám přijme" not in instructions[0]
    assert "ke každé kartě práce vydej jeden ticket" not in instructions[0]
    assert "přijaté, připravené zadání a autorizovanou realizaci" in instructions[0]
    assert "canvasDraft" in instructions[0] and "resultKind" in instructions[0]
    for capability in ("canvas discover", "canvas describe", "node_routes.node_spec",
                       "canvas_routes.graph", "canvas_routes.canvas_plan", "opora_graph_routes.context"):
        assert capability in instructions[0]
    assert "nejsou atomické" in instructions[0]
    assert "draft" in CARD_VALUES["status"]  # Instructions use native values, not an invented blocked status.
    validate_steps([{"id": "discover", "order": 1, "title": "Zpřístupnit zdroj",
                     "kind": "research", "files": [], "dependsOn": [],
                     "acceptance": ["Zaznamenán dostupný zdroj a jeho revize."]}])

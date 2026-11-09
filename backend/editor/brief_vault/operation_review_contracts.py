"""Finite 27-operation matrix; native handlers remain the permission/shape authority."""
from backend.editor.brief_vault.brief_vault import HUMAN_OPS, OPS

NATIVE_TESTS = {
    "create": "test_brief_vault.py", "revise": "test_brief_vault.py", "split": "test_brief_vault.py",
    "research": "test_brief_vault.py", "promote": "test_brief_vault.py", "propose-mvp": "test_brief_vault.py",
    "set-mvp": "test_brief_vault.py", "delete": "test_brief_vault.py", "restore": "test_brief_vault.py",
    "set-discipline": "test_brief_vault_disciplines.py", "research-update": "test_brief_vault_develop.py",
    "question": "test_brief_vault_develop.py", "answer": "test_brief_vault_develop.py",
    "feedback": "test_brief_vault_develop.py", "link-decisions": "test_brief_vault_develop.py",
    "from-idea": "test_brief_vault_develop.py", "propose": "test_brief_vault_gates.py",
    "reject-proposal": "test_brief_vault_gates.py", "gate": "test_brief_vault_placement.py",
    "confirm-lesson": "test_brief_vault_lessons.py", "drop-lesson": "test_brief_vault_lessons.py",
    "duel-open": "test_brief_vault_duel.py", "duel-turn": "test_brief_vault_duel.py",
    "duel-score": "test_brief_vault_duel.py", "duel-decide": "test_brief_vault_duel.py",
    "vision-set": "test_brief_vault_duel.py", "vision-align": "test_brief_vault_duel.py",
}

ADAPTER_TESTS = {
    **dict.fromkeys(("create", "delete", "restore"), "test_operation_reviews.py::test_fragment_receipt_replay_exact_text_and_human_delete_restore"),
    "revise": "test_operation_reviews.py::test_stale_human_intent_never_applies_and_reject_is_replayable",
    **dict.fromkeys(("split", "propose-mvp", "set-mvp", "set-discipline"), "test_operation_review_workflows.py::test_split_mvp_discipline_and_stale_revision"),
    **dict.fromkeys(("research", "research-update", "promote", "question", "answer", "feedback"), "test_operation_review_workflows.py::test_research_promote_question_answer_feedback_preserve_sources"),
    **dict.fromkeys(("from-idea", "link-decisions"), "test_operation_review_workflows.py::test_idea_and_decision_links_use_actual_scoped_state"),
    **dict.fromkeys(("propose", "reject-proposal", "gate", "confirm-lesson", "drop-lesson"), "test_operation_review_placement.py::test_full_gate_cycle_proposals_placement_and_lessons"),
    **dict.fromkeys(("duel-open", "duel-turn", "duel-score", "duel-decide", "vision-set", "vision-align"), "test_operation_review_duel.py::test_delegated_duel_and_vision_are_native_records_not_human_approval"),
}


def inventory():
    return [{"op": name, "required": sorted(required), "optional": sorted(optional),
             "authority": "human review" if name in HUMAN_OPS else "native conditional authority",
             "nativeTest": NATIVE_TESTS[name], "adapterTest": ADAPTER_TESTS[name]}
            for name, (required, optional) in OPS.items()]

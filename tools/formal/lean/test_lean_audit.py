"""Audit parsing tests (no Lean needed): forbidden constructs, theorem discovery, axiom policy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402


def write(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_scan_rejects_sorry_axiom_eval_and_foreign_imports(tmp_path):
    path = write(tmp_path, "OporaHub/Bad.lean", "import Mathlib\nnamespace X\naxiom cheat : False\n"
                 "theorem t : 1 = 2 := by sorry\n#eval IO.println 1\nmacro \"x\" : term => `(1)\n"
                 "theorem u : True := by native_decide\nend X\n")
    tokens = {item["token"] for item in audit.scan([path], tmp_path)}
    assert {"import Mathlib", "axiom", "sorry", "#eval", "metaprogram", "native_decide"} <= tokens


def test_scan_ignores_comments_and_allows_own_imports(tmp_path):
    path = write(tmp_path, "OporaHub/Good.lean", "import OporaHub.Votes\n/- no sorry here,\n axiom -/\n"
                 "-- #eval nothing\ntheorem t : True := trivial\n")
    assert audit.scan([path], tmp_path) == []


def test_theorems_are_namespaced(tmp_path):
    path = write(tmp_path, "OporaHub/A.lean", "namespace OporaHub.A\ntheorem one : True := trivial\n"
                 "/- theorem hidden : True -/\nprivate theorem two (n : Nat) : n = n := rfl\nend OporaHub.A\n"
                 "theorem top : True := trivial\n")
    assert [item["name"] for item in audit.theorems([path], tmp_path)] == ["OporaHub.A.one", "OporaHub.A.two", "top"]


def test_axiom_policy_rejects_sorry_and_custom_axioms_and_missing_output():
    printed = audit.parse_axioms("'A.ok' depends on axioms: [propext, Quot.sound]\n"
                                 "'A.free' does not depend on any axioms\n"
                                 "'A.cheat' depends on axioms: [sorryAx]\n'A.custom' depends on axioms: [A.myAxiom, propext]\n")
    declared = [{"name": name, "module": "A"} for name in ("A.ok", "A.free", "A.cheat", "A.custom", "A.missing")]
    records, failures = audit.audit(declared, printed)
    assert [item["ok"] for item in records] == [True, True, False, False, False]
    assert {(item["kind"], item["theorem"]) for item in failures} == {
        ("nonstandard_axiom", "A.cheat"), ("nonstandard_axiom", "A.custom"), ("audit_incomplete", "A.missing")}


def test_annotations_carry_the_audit_and_each_failure():
    document = {"tool": {"toolchain": "leanprover/lean4:v4.22.0"}, "trusted": False, "ok": False,
                "theorems": [{"name": "A.t", "axioms": ["propext"]}],
                "failures": [{"kind": "vectors_drift"}, {"kind": "build_failed", "log": "x"}]}
    lines = audit.annotations(document)
    assert lines[0].startswith("::notice title=formal/lean audit::") and '["A.t",["propext"]]' in lines[0]
    assert lines[1] == '::error title=formal/lean vectors_drift::{"kind":"vectors_drift"}'
    assert '"log"' not in lines[2]


def test_repository_proofs_are_clean_by_scan():
    files = audit.sources()
    assert audit.scan(files) == []
    names = {item["name"] for item in audit.theorems(files)}
    assert {"OporaHub.Votes.posted_iff", "OporaHub.Votes.no_repost", "OporaHub.Votes.dedupe_idempotent",
            "OporaHub.AcceptedHead.stale_never_advances", "OporaHub.AcceptedHead.reachable_linear",
            "OporaHub.FieldMerge.merged_comm", "OporaHub.FieldMerge.disjoint_preserves_both"} <= names

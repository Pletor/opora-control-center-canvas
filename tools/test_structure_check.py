from tools import verify
from tools.structure_check import check_repo, counts


def _write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rules(root):
    return {(rule, path) for rule, path, _why in check_repo(root)}


def test_clean_feature_folder_has_no_findings(tmp_path):
    _write(tmp_path, "frontend/editor/card/README.md", "Karta.")
    _write(tmp_path, "frontend/editor/card/components/Card.tsx")
    _write(tmp_path, "frontend/editor/card/components/Card.test.ts")
    _write(tmp_path, "frontend/editor/card/logic/card-model.ts")
    _write(tmp_path, "frontend/editor/card/logic/card-model.test.ts")
    _write(tmp_path, "frontend/editor/card/styles/card.css")
    _write(tmp_path, "frontend/editor/card/logic/vite-env.d.ts")
    assert check_repo(tmp_path) == []


def test_file_outside_its_drawer_is_found(tmp_path):
    _write(tmp_path, "frontend/editor/card/README.md", "Karta.")
    _write(tmp_path, "frontend/editor/card/logic/Card.tsx")
    _write(tmp_path, "frontend/editor/card/components/use-card.ts")
    _write(tmp_path, "frontend/editor/card/card.css")
    assert _rules(tmp_path) == {
        ("supliky", "frontend/editor/card/logic/Card.tsx"),
        ("supliky", "frontend/editor/card/components/use-card.ts"),
        ("supliky", "frontend/editor/card/card.css"),
    }


def test_tests_folder_router_outside_api_and_vague_name_are_found(tmp_path):
    _write(tmp_path, "backend/README.md", "Backend.")
    _write(tmp_path, "backend/__init__.py")
    _write(tmp_path, "backend/editor/README.md", "Editor.")
    _write(tmp_path, "backend/editor/__init__.py")
    _write(tmp_path, "backend/editor/tests/test_node.py")
    _write(tmp_path, "backend/editor/node_routes.py", "router = APIRouter()\n")
    _write(tmp_path, "backend/editor/helpers.py")
    _write(tmp_path, "backend/api/editor/node_routes.py", "router = APIRouter()\n")
    assert _rules(tmp_path) == {
        ("testy-vedle", "backend/editor/tests"),
        ("router-v-api", "backend/editor/node_routes.py"),
        ("nazev", "backend/editor/helpers.py"),
    }


def test_missing_readme_and_long_file_are_found(tmp_path):
    _write(tmp_path, "frontend/editor/card/components/Card.tsx", "x\n" * 201)
    _write(tmp_path, "backend/editor/__init__.py")
    _write(tmp_path, "backend/editor/test_long.py", "x\n" * 500)
    assert _rules(tmp_path) == {
        ("readme", "frontend/editor/card"),
        ("readme", "backend/editor"),
        ("delka", "frontend/editor/card/components/Card.tsx"),
    }


def test_skipped_dirs_are_ignored(tmp_path):
    _write(tmp_path, "frontend/node_modules/pkg/index.ts")
    _write(tmp_path, "tools/vendor/test/x.test.mjs")
    assert check_repo(tmp_path) == []


def test_counts_groups_by_rule():
    assert counts([("delka", "a", ""), ("delka", "b", ""), ("readme", "c", "")]) == {"delka": 2, "readme": 1}


def test_structure_ratchet_fails_on_new_rule_and_growth(monkeypatch):
    from tools import structure_check
    monkeypatch.setattr(verify, "STRUCTURE_BASELINE", {"delka": 2})
    monkeypatch.setattr(structure_check, "check_repo", lambda root: [("delka", "a", ""), ("delka", "b", "")])
    assert verify.check_structure()[0] is True
    monkeypatch.setattr(structure_check, "check_repo", lambda root: [("delka", "a", ""), ("readme", "b", "")])
    passed, message = verify.check_structure()
    assert passed is False and "readme 1/0" in message
    monkeypatch.setattr(structure_check, "check_repo", lambda root: [])
    passed, message = verify.check_structure()
    assert passed is True and "utáhni" in message

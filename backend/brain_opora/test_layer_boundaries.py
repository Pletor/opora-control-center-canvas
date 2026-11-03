"""Imports in the brain only go downwards: heart -> decision -> determinism."""
import ast
from pathlib import Path

BRAIN = Path(__file__).parent
FORBIDDEN = {
    "determinism": ("decision", "heart"),
    "decision": ("heart",),
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            names.add(prefix + (node.module or ""))
    return names


def _hits(layer: str, imported: str) -> bool:
    """Absolute `backend.brain_opora.<upper>` or a sibling-relative `..<upper>` import."""
    sibling = imported.startswith("..") and not imported.startswith("...")
    target = imported[2:] if sibling else imported.removeprefix("backend.brain_opora.")
    if not sibling and target == imported:
        return False
    return any(target == upper or target.startswith(upper + ".") for upper in FORBIDDEN[layer])


def test_lower_layers_never_import_upper_ones():
    violations = [
        f"{path.relative_to(BRAIN)} imports {name}"
        for layer in FORBIDDEN
        for path in (BRAIN / layer).rglob("*.py")
        for name in _imports(path)
        if _hits(layer, name)
    ]
    assert violations == []


def test_each_layer_is_a_documented_package():
    for layer in ("determinism", "decision", "heart"):
        assert (BRAIN / layer / "__init__.py").is_file()
        assert (BRAIN / layer / "README.md").is_file()


def test_boundary_check_catches_an_upward_import(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from backend.brain_opora.heart import batch\nfrom ..decision import gatekeeper\n", encoding="utf-8")
    assert {name for name in _imports(bad) if _hits("determinism", name)} == {
        "backend.brain_opora.heart", "..decision"}

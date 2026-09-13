from backend.paths import REPO_ROOT, DIST_DIR, VENDOR_DIR


def test_repo_root_points_at_checkout_root():
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert DIST_DIR == REPO_ROOT / "dist"
    assert VENDOR_DIR == REPO_ROOT / "vendor"

"""Jediné místo, kde backend odvozuje kořen repozitáře. Při přesunu modulů se mění jen zde."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
GRAPHIFY_VENV = REPO_ROOT / ".venv-graphify"

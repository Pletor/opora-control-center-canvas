"""Git worktrees uvnitř složky projektu. `main/` je čistá kopie a nikdy nedostane zápis."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from backend.integrations.gitio import git

WORKTREE_ID = re.compile(r"^wt-[a-z0-9-]{1,40}$")
TAIL = 4000


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class WorktreeManager:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.main = self.project_dir / "main"
        self.root = self.project_dir / "worktrees"

    def _check_id(self, worktree_id: str) -> str:
        if worktree_id == "main":
            raise ValueError("main je čistá kopie; není to worktree a nelze do něj zapisovat.")
        if not WORKTREE_ID.match(str(worktree_id)):
            raise ValueError("Neplatné ID worktree (wt-<a-z0-9->).")
        return worktree_id

    def path(self, worktree_id: str) -> Path:
        return self.root / self._check_id(worktree_id)

    def _meta(self, worktree_id: str) -> Path:
        return self.root / (self._check_id(worktree_id) + ".json")

    def main_is_clean(self) -> bool:
        return git(self.main, "status", "--porcelain").strip() == ""

    def create(self, worktree_id: str, *, base: str = "main", branch: str | None = None) -> dict:
        target = self.path(worktree_id)
        if target.exists() or self._meta(worktree_id).exists():
            raise ValueError("Worktree s tímto ID už existuje.")
        if not (self.main / ".git").exists():
            raise ValueError("Projekt nemá spravovanou kopii main.")
        if base == "main":
            base_ref = git(self.main, "rev-parse", "HEAD").strip()
        else:
            base_ref = git(self.path(base), "rev-parse", "HEAD").strip()
        branch = branch or f"opora/{worktree_id}"
        self.root.mkdir(parents=True, exist_ok=True)
        git(self.main, "worktree", "add", "-b", branch, str(target), base_ref, timeout=60)
        meta = {"id": worktree_id, "path": str(target), "branch": branch, "base": base, "baseCommit": base_ref, "createdAt": _now()}
        self._write_meta(worktree_id, meta)
        return meta

    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("wt-*.json"))]
        return sorted(items, key=lambda item: item["createdAt"])

    def get(self, worktree_id: str) -> dict:
        try:
            return json.loads(self._meta(worktree_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Worktree neexistuje.") from None

    def head(self, worktree_id: str) -> str:
        return git(self.path(worktree_id), "rev-parse", "HEAD").strip()

    def run_check(self, worktree_id: str, command: list[str], timeout: int = 600) -> dict:
        directory = self.path(worktree_id)
        if not directory.is_dir():
            raise ValueError("Worktree neexistuje.")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise ValueError("Příkaz musí být neprázdný seznam řetězců.")
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError:
            return {"ok": False, "exitCode": None, "stdoutTail": "", "stderrTail": f"Příkaz nenalezen: {command[0]}", "at": _now()}
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "exitCode": None, "stdoutTail": (exc.stdout or "")[-TAIL:], "stderrTail": f"Časový limit {timeout}s vypršel.", "at": _now()}
        return {"ok": result.returncode == 0, "exitCode": result.returncode, "stdoutTail": result.stdout[-TAIL:], "stderrTail": result.stderr[-TAIL:], "at": _now()}

    def remove(self, worktree_id: str, *, keep_branch: bool = False) -> None:
        meta = self.get(worktree_id)
        target = self.path(worktree_id)
        if target.exists():
            git(self.main, "worktree", "remove", "--force", str(target), timeout=60)
        git(self.main, "worktree", "prune", optional=True)
        if not keep_branch:
            git(self.main, "branch", "-D", meta["branch"], optional=True)
        os.remove(self._meta(worktree_id))

    def _write_meta(self, worktree_id: str, meta: dict) -> None:
        path = self._meta(worktree_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

Worktree projektu pro prostředí Projekt (`docs/domeny-a-worktree.md` §6, §13.3). Worktree zakládá `CanvasService.create_workspace` z HEAD mainu; do `main/` se nikdy nezapisuje.

- `workspace_domain.py`: worktree patří jedné doméně architektury. `require_domain` hlídá založení i přeřazení, `rebind` = `PATCH /api/workspaces/{wid}`.
- `workspace_archive.py`: skladiště uzavřených worktree. `POST /api/workspaces/{wid}/archive` odmítne worktree se změnami nebo s živou relací, pak po krocích zapíše `archived_workspaces`, odebere Git worktree bez `--force` (větev `work/<id>` zůstává), přesune data do `canvas/workspaces/_archive/<id>` a smaže řádek `workspaces`. Nedokončený přesun jde zopakovat. `GET /api/workspaces/archive` skladiště jen čte.

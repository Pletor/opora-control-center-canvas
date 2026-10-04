# Skill opora-control-center

Znovupoužitelný skill pro práci s plátnem OPORA v **kterémkoli projektu**, současném i budoucím.
Platí pro asistenta v okně OPORA (`docs/asistent.md`) i pro agenta mimo aplikaci (Claude Code
v terminálu nebo VS Code). Globálně je dostupný přes odkaz `~/.claude/skills/opora-control-center`
na tuto složku v repu OPORA, takže v repu projektu nic instalovat netřeba a úprava zde platí všude.

Projekt neurčuje skill, ale dvě hodnoty: `<projectId>` a `<workspace>`. Asistent je dostane
v `<opora_context>`, agent mimo aplikaci je zjistí `opora_read.py projects` / `workspaces`.
Do skillu nepatří nic specifického pro jeden projekt.

## Co je uvnitř

- `SKILL.md`: kde agent běží (v aplikaci / mimo ni), rozcestník, postup a hranice.
- `references/`: čtení a zápis (`api.md`), pracovní postupy na plátně (`workflow.md`), orientace,
  mapy, telemetrie, export.
- `scripts/opora_read.py`: čtení plátna a hledání (loopback i tunel); jen standardní Python 3.
- `scripts/opora_write.py`: zápis na pevný seznam cest, jen loopback. V okně OPORA každé volání
  schvaluje člověk (kromě `--dry-run` u `/api/canvas-plan`).
- `assets/task-brief.md`: šablona návrhu karty.

## Příklad: připojený projekt

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 projects
# → id projektu, např. "ample" = cc5f34ec07cd455ca5ad1a69af19022b
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 view --project cc5f34ec07cd455ca5ad1a69af19022b --workspace draft
```

## Údržba

Testy skriptů: `uv run pytest .claude/skills/opora-control-center/scripts` (z kořene repa OPORA).
Co asistent smí spustit, určuje backend (`backend/claude_code/assistant/approvals.py`, `command.py`),
ne tento skill. Novou cestu nebo příkaz zapiš do skillu až ve chvíli, kdy existuje v kódu.

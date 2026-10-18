# Skill opora-control-center

Znovupoužitelný skill pro práci s plátnem OPORA v **kterémkoli projektu**, současném i budoucím.
Platí pro asistenta v okně OPORA (`docs/asistent.md`) i pro agenta mimo aplikaci (Claude Code
v terminálu nebo VS Code). Globálně je dostupný přes odkaz `~/.claude/skills/opora-control-center`
na tuto složku v repu OPORA, takže v repu projektu nic instalovat netřeba a úprava zde platí všude.

Projekt neurčuje skill, ale dvě hodnoty: `<projectId>` a `<workspace>`. Asistent je dostane
v `<opora_context>`, agent mimo aplikaci je zjistí `opora_read.py projects` / `workspaces`.
Do skillu nepatří nic specifického pro jeden projekt.

## Co je uvnitř

- `SKILL.md`: rozcestník. Kde agent běží, pět úloh s nejkratší cestou, smyčka relace, co patří člověku,
  tabulka „chci X → příkaz → reference“, pravidla efektivity a hranice.
- `references/` (načítá se jen podle potřeby, každá začíná „Kdy mě číst“):
  `api.md` (čtecí příkazy, zápisové cesty, chyby), `canvas-plan.md` (dávka, extend, graf, rozmístění),
  `agent-loop.md` (lease, brief, výstup, důkazy), `pipeline.md` (router, etapy, kritici),
  `workflow.md` (grilling, wayfinder, laťka karty, brány), `cycle.md` (brány Schránky, buňka, duel),
  `provoz.md` (spuštění, zastavení, restart, build, ověření běžící verze), `hooks.md`, a mapy / orientace
  (`navigation.md`, `rlm.md`, `graphify.md`, `archify.md`, `map-refresh.md`, `external-agent.md`).
- `scripts/opora_read.py`: čtení a hledání (loopback i tunel); jen standardní Python 3.
- `scripts/opora_write.py`: zápis na pevný seznam cest (`WRITE_ROUTES`), jen loopback.
- `scripts/opora_save.py`: uložení verze plátna.
- `assets/task-brief.md`: šablona návrhu karty.

## Příklad: připojený projekt

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 projects
# → id projektu, např. "ample" = cc5f34ec07cd455ca5ad1a69af19022b
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 view --project cc5f34ec07cd455ca5ad1a69af19022b --workspace draft
```

## Údržba

Testy skriptů a dokumentace: `uv run pytest .claude/skills/opora-control-center/scripts` (z kořene repa OPORA).
`test_skill_docs.py` hlídá, že reference pokrývají všechny zápisové cesty a čtecí příkazy a že příklady
JSON označené `<!-- example: /api/… -->` projdou skutečným validátorem backendu.
Co asistent smí spustit, určuje backend (`backend/claude_code/assistant/approvals.py`, `command.py`),
ne tento skill. Novou cestu nebo příkaz zapiš do skillu až ve chvíli, kdy existuje v kódu.

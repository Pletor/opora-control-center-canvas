# Skill opora-control-center

Znovupoužitelný skill pro práci s plátnem OPORA v **kterémkoli projektu**, současném i budoucím.
Platí pro pracovníky pod agent-office i pro agenta mimo aplikaci (Claude Code
v terminálu nebo VS Code). Globálně je dostupný přes odkaz `~/.claude/skills/opora-control-center`
na tuto složku v repu OPORA, takže v repu projektu nic instalovat netřeba a úprava zde platí všude.

Projekt neurčuje skill, ale dvě hodnoty: `<projectId>` a `<workspace>`. Pracovník je dostane
v promptu, agent mimo aplikaci je zjistí `opora_read.py projects` / `workspaces`.
Do skillu nepatří nic specifického pro jeden projekt.

## Co je uvnitř

- `SKILL.md`: rozcestník nad OporaHubem. Kde agent běží (pod agent-office, mimo aplikaci),
  hlavní smyčka (agent-state → akce → běh po krocích → výsledek), role, co patří člověku,
  tabulka „chci X → udělám Y“, pravidla efektivity a hranice.
- `references/` (načítá se jen podle potřeby, každá začíná „Kdy mě číst“):
  `hub-loop.md` (smyčka agenta nad OporaHubem), `planner.md` (plán, `spec.steps`, kontrolní seznam kvality),
  `review.md` (hledač / ověřovatel), `conflicts.md` (auto-rebase), `formal.md` (formální ověření),
  `events.md` (feed událostí), `hub-api.md` (cesty OporaHubu a kdo je smí), `routy.md` (všechny ostatní cesty
  backendu: k čemu a kdy), `autonomie.md` (plná autonomie agentů: přepínač, co odemyká, výjimky §4),
  `api.md` (čtecí příkazy, zápisové cesty, chyby), `canvas-plan.md` (dávka, extend, graf, rozmístění),
  `legacy.md` (**zastaralé**: lease, `agent-output`, router, kritici, `opora_stage.py`, `opora_closure.py`),
  `workflow.md` (grilling, wayfinder, laťka karty, brány), `cycle.md` (brány Schránky, buňka, duel),
  `provoz.md` (spuštění, zastavení, restart, build, ověření běžící verze) a mapy / orientace
  (`navigation.md`, `rlm.md`, `graphify.md`, `map-refresh.md`, `external-agent.md`).
- `scripts/opora_read.py`: čtení a hledání (loopback i tunel); jen standardní Python 3.
- `scripts/opora_hub.py`: agent-state s ETagem, výběr akce, claim / zadání / heartbeat / průběžný krok / výsledek běhu
  a slot review; tokeny jen v souborech 0600 (`OPORA_HUB_STATE_DIR`, výchozí `~/.opora/hub`).
- `scripts/opora_act_batch.py`: hromadné `act` (`--action-id` opakovaně, `--all-ready --verb V`) podle
  `(verb, targetId)`, výstup `{done, skipped, next}`, cizí změna = konflikt s `changed`.
- `scripts/opora_write.py`: zápis na pevný seznam cest (`WRITE_ROUTES`) a agentní cesty OporaHubu
  (`HUB_AGENT_ROUTES`); lidské cesty a cesty s tokenem odmítne předem. Jen loopback.
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
`test_skill_docs.py` hlídá, že reference pokrývají všechny zápisové cesty a čtecí příkazy, že každá cesta
zmíněná v SKILL.md a references/ existuje v tabulce cest backendu (cesty z běžících PR jsou výslovně
v `PENDING_ROUTES`), že naopak **každá** cesta backendu je ve skillu doslova popsaná (výjimky jen §4
`docs/plna-autonomie-agenta.md` a čisté UI v `UNDOCUMENTED_ROUTES`) a že příklady JSON označené `<!-- example: /api/… -->` projdou validátorem backendu.
`test_opora_hub.py` projde celou smyčku agenta proti skutečnému backendu.
Co srdce OPORY smí spustit, určuje backend (`backend/brain_opora/heart/command.py`, `--allowedTools`),
ne tento skill. Novou cestu nebo příkaz zapiš do skillu až ve chvíli, kdy existuje v kódu.

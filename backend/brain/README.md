# Brain

Registr dovedností OPORY a jejich git úložiště. Kontrakt: `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4. Oddělený od mozku srdce (`backend/brain_opora/`): Brain drží know-how, srdce ho jen čte.

- `store.py` (`Store(datový kořen)`): git repozitář `<datový kořen>/brain/` (živě `P:\opora-data\brain\`; založí ho `git init`, `core.autocrlf=false`). Rozvržení je lokální marketplace:
  - `.claude-plugin/marketplace.json` (name `opora-brain`, seznam pluginů),
  - `plugins/<plugin>/.claude-plugin/plugin.json`, `plugins/<plugin>/skills/<skill>/SKILL.md`, případně `plugins/<plugin>/evals/`.

  Funkce: `write(plugin, files, message)` commitne jen změnu (autor „OPORA Brain“), jinak vrátí poslední verzi pluginu; `read(plugin, relpath, sha)` = `git show`; `version(plugin)` = poslední commit pluginu; `export(plugin, sha)` = zip pluginu (kořen zipu = kořen pluginu, pro `claude --plugin-dir`) v `<datový kořen>/brain-pins/<plugin>@<sha12>.zip`, idempotentně.
- `registry.py`: tabulky `brain_artifacts`, `brain_artifact_versions`, `brain_links` v registry.sqlite (schéma `database/schema/brain_schema.py`). ID artefaktu `opora:brain:<kind>:<name>`, pin `opora:brain:<kind>:<name>@<sha12>`. `add_version` přidá kandidáta, `activate` ho zapne a dosavadní aktivní verzi vyřadí (právě jedna `active`, hlídá i unikátní index). `active`, `list_artifacts`, `get_artifact` čtou, `link` váže verzi na `log_event` / `eval_run` / `canvas_node`.
- `pins.py` (`for_ticket`): piny ticketu (`machine.pins`) při `ticket.issue`. ID artefaktu přeloží přes `registry.resolve`
  (bez verze = aktivní, `@sha12` = ta verze) a seskupí po pluginech `{pin, plugin, version, zip}`, jeden plugin = jeden
  zip. Výchozí pin pluginu `ponytail` doplní, když ho srdce nepinulo a v registru je. Neznámé ID je `LookupError`,
  dvě verze téhož pluginu `ValueError` (brána z obou dělá 422).
- `seed.py`: idempotentní naplnění při startu srdce (`HeartDriver.start`, vedle seedu Srdce v1).
  - Plugin `opora-heart` ze `seed/opora-heart/` má skilly `heart` (systémový prompt srdce) a `vyslech` (postup výslechu).
  - Plugin `ponytail` (MIT) se bere z nainstalovaného pluginu Claude Code (`~/.claude/plugins/cache/ponytail/ponytail/<nejvyšší verze>/`). Do Brainu jdou jeho skilly, `LICENSE` a manifest bez háčků a `userConfig`. Když na stroji není, seed ho přeskočí a zaloguje.

  Seed vytvoří artefakty skillů a první verzi jako `active`. Plugin, který už v Brainu je, nepřepíše, a artefakt s aktivní verzí nechá být. Úprava `seed/` v repu se tedy do živého Brainu nepropíše; nová verze jde přes registr. Výjimka: pluginu bez `evals/` seed doplní zmrazenou sadu ze `seed/<plugin>/evals/` commitem bez nové verze artefaktu.
- `evaluate.py`: eval gate. Kandidát (`add_candidate`) = commit pluginu (`Store.write`) a verze `candidate` s `baseline_version_id` = aktivní verze; změna `evals/` je 422 `evals_frozen`. Eval (`start` + `execute`, pro uzel `evaluate`) rozbalí export kandidáta i baseline do dočasné složky, do obou dá `evals/` z verze kandidáta (sadu, kterou kandidát změnit nesměl) a pustí `claude plugin eval <složka> --json … --threshold 0 --trust-plugin --no-publish`. Kandidát běží s `--ablation with-without`, baseline s `none`. Strop ceny obou běhů dohromady je `OPORA_BRAIN_EVAL_MAX_USD` (1.0). Skóre je `aggregates.overallScore`, cena `costUsd`, neúplný běh (`partial`, strop) je `error`.
  - Běh je řádek `brain_eval_runs` (`running` / `ok` / `error` / `forced`) s vazbou `brain_links(eval_run)` a skóre jde do `eval_score` verze.
  - Aktivace projde jen po `passed` (`ok` a skóre ≥ baseline). `force` = člověk, zapíše `forced`. Návrat (`registry.rollback`) je bez evalu.
  - Uzel enginu `brain_eval` (`backend/flow/node_types.py`) volá `work`.
- `seed/opora-heart/evals/`: zmrazená sada skillu `heart` (`ticket-s-kriteriem`, `bez-podkladu-eskaluje`; `prompt.md` + `graders/*.md`, Haiku, `max_turns: 3`, 1 běh).
- `evals/`: evaly procesu srdce (sondy přesunuté z `.claude/hillclimb/`, vlastní README).

Srdce čte prompt a postupy režimů jen odsud (`backend/brain_opora/heart/command.py` `heart_skills`, bez zálohy v souboru) a piny zapisuje do `brainPins` záznamu dávky. API: `backend/api/brain/` (`/api/brain-registry/*`, včetně zipu pinu pro dělníka).

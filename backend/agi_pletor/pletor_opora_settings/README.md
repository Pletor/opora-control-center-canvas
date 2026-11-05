# agi_pletor/pletor_opora_settings: Dílna skillů a funkcí

Kontrakt: `docs/navrhy/2026-11-05-dilna-skillu.md` (§3a funkce, §6 bezpečnost, §7 milníky). Hotové: **D0** (funkce
a jejich měření) a API editoru (čtení a zápis skillů a funkcí). Skilly zatím leží jako soubory v repu, ne v Brainu
(kandidát, verze a aktivace přijdou s D4).

- **Funkce** = `tools/<nazev>.py` s `def run(vstup: dict) -> dict`. Čistá: bez náhodnosti, času a sítě, vše potřebné
  je ve vstupu. Co je nevratné nebo sahá do systému, patří do skriptu skillu s manifestem, ne do funkce. Název
  `^[a-z][a-z0-9_]*$` (soubory s `_` na začátku nebo jiným názvem Dílna přeskočí).
- **Případy** = `tools/<nazev>.cases.json`: `[{"name", "input", "expected"}]`. Funkce je lepší jen když `passed` neklesne.
- **Měření** (`workshop.measure(folder, name, timeout=20)`) → `{name, passed, total, failed: [{name, got, expected}],
  durationMs, deterministic, error}`. Každý případ běží v odděleném procesu `python -I _run_case.py <cesta> <vstup>`
  s časovým limitem, v dočasné složce a s prostředím bez `OPORA_*`, `STRIPPED` srdce a proměnných s
  `KEY`/`TOKEN`/`SECRET`/`PASSWORD`. Výjimka, limit nebo výstup mimo JSON = selhaný případ s `got` = text chyby;
  `error` jen při chybě načtení případů nebo modulu. Výstup se zkracuje na 2000 znaků.
- **Determinismus:** každý případ dvakrát, výstupy (JSON se seřazenými klíči) musí být shodné, jinak
  `deterministic: false`. Dva běhy náhodnost obvykle odhalí, nezaručí to.
- `list_tools(folder)` → `[{name, path, cases}]` (`cases` = počet, 0 když chybí nebo jsou neplatné).
- Editor funkcí: `read_tool` → `{name, code, cases}` (syrový text, `cases` = "" když chybí), `save_tool` (případy
  musí být platný seznam `{name, input, expected}`, kód do 200 000 znaků) → `{name, cases: počet}`, `create_tool`
  (šablona `run` + jeden prázdný případ; existující = `FileExistsError`).
- **Skilly** (`skills_store.py`) = `skills/<nazev>/SKILL.md` + volitelně `scripts/*.py`, `references/*.md`. Název
  `^[a-z][a-z0-9-]*$`. `list_skills` → `[{name, description, files}]` (`description` z frontmatteru SKILL.md),
  `create_skill` (šablona s „Kdy použít“, „Postup“, „Ověření“), `read_file`, `write_file`. Zápis jen dovnitř složky
  skillu (bez `..`, absolutních cest, `\`, `:` a symlinků), přípony `.md .py .json .txt .yaml`, obsah do 200 000
  znaků bez `\0`; chybějící podsložky vytvoří. Ukázka: `skills/restart-opora`.
- Routy: `backend/api/pletor/workshop_routes.py` (`/api/pletor/workshop/*`, jen člověk v UI; 422 špatný vstup,
  404 neznámé, 409 existující).

**Nová funkce:** přidej `tools/<nazev>.py` a `tools/<nazev>.cases.json`, pak
`uv run pytest backend/agi_pletor` nebo `POST /api/pletor/workshop/tools/<nazev>/measure`. Ukázka: `rozdel_vety`.

Omezení: síť ani souborový systém oddělený proces neblokuje (jen jiná pracovní složka a prostředí); izolace
podle §6 je úkol D3.

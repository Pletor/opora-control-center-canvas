# Relace A – handoff (2026-10-15)

Zadání HERMES-A-20261015: pipeline a skutečná tvorba buněk/sítě podle originálů 00–09
(`I:/1. Projekty/08_AGI/neuron-brain`). Nejmenší spustitelný řez: buňka s cílem, vstupem, výstupem,
pamětí a vazbou na další krok; jeden průchod zadání → rozhodnutí → výkon/artefakt → skutečné ověření → poučení.

## Checkpoint 1 (start)

- HEAD `416fc2f`. Necommitnuté cizí: `docs/navrhy/2026-10-14-vyvoj-tajemstvi-opory-v-platne.md`, `docs/navrhy/2026-10-15-relace-b-handoff.md` (nesahat).
- Vlastněné cesty: `backend/editor/brief_vault/`, `backend/api/editor/` jen router Schránky, `frontend/editor/brief-vault-dock/`,
  `frontend/editor/node-detail/brief-vault/`, `.claude/skills/opora-control-center/` (cycle nástroje), `docs/schranka-*`, tento handoff.
- Nesahám: node-card, board, control-tower, area, project/maps, `App.tsx`, `CLAUDE.md`, shared types, `database/schema`, cizí návrhy.
- První ověřitelný krok: mapa princip → implementace → mezera (subagent čte 00–09 a kód Schránky), pak kontrakt řezu v `docs/schranka-bunka.md`.

## Mapa originál → OPORA (výtah)

- Hotovo: impulz a rozsah (`scoped`), polarity (`weighed`), navrhovatel ≠ potvrzovatel (`propose`/`yes`), rozhodnutí ano/jinak/ne, mez smyčky (3 kola).
- Částečně: buňka (disciplína je jen štítek), typovaný mikrokrok (chybí KDE a spustitelné OVĚŘENÍ), paměť (poučení se jen čte, `kind` nevázaný na výsledek).
- **Chybí, jádro mezery:** mezi `placed` a `verified` se nic nevykoná a `verified.actual` jen tvrdí navrhovatel. Karta vzniká bez `checks` a `goal_mode`, proto pipeline karty nemá co spustit.
- Chybí, mimo řez: DNA projektu, baseline, kontroly podle typu mikrokroku, podmínka platnosti poučení.
- Rozpory originálu s OPORA (originál volá LLM z aplikace přes placené API a má druhé úložiště paměti) jsou vyřešené tím, že orchestrátor je vnější agent. Nejde o BLOCKED.

## Kontrakt řezu: `docs/schranka-bunka.md` (K15)

`synthesized.checks` → karta `checks` + GOAL → vykonavatel vytvoří artefakt → ověřovatel `opora_cycle.py run-checks` skutečně spustí kontroly → `verified.actual.run`, server hlídá shodu kontrol a `tests` s exit kódy, vykonavatel ≠ ověřovatel → `learned.kind` podle výsledku.

## Checkpoint 2 (dávka 1)

- Hotovo (necommitnuto, čeká na opravy po kritikovi):
  - backend `synthesized.checks`, `verified.actual.run`, pravidla buňky, karta s `checks` + GOAL;
  - CLI `run-checks`;
  - `cycle.md`;
  - e2e `test_opora_cell.py`: skutečný uvicorn nad `tmp_path` a skutečný běh pytest. Kolo 1 skončí `fail` → antipattern → nové kolo, kolo 2 `pass` → pattern. Vykonavatel nesmí ověřit sám sebe ani zapnout `verified`.
- Testy: backend 2 105 passed, 2 povolené graphify failed; skripty 106 passed; e2e 1 passed.
- Nezávislý kritik (ChatGPT/Codex) našel:
  - 2 vysoké: podvržený `run`; vykonavatel ovládá obsah testů;
  - 3 střední: `extend` bez `checks`; Windows cesty v `shlex`; rozdílná pravidla serveru a CLI.
  - Opravy zadány, viz kontrakt §3 a §5.
- **BLOCKED → Hermes:** atestace výsledku běhu. Server příkazy nespouští a identita aktéra je deklarovaná, takže `run` je přiřazený, ne atestovaný doklad (`docs/schranka-bunka.md` §5). Rozhodnout je potřeba ověřenou identitu aktéra, nebo běh kontrol mimo vliv navrhovatele.

## Checkpoint 3 (dokončení K15)

- **Opravy kritika (1 korekční kolo):**
  - podvržený `run`: návrh podává jen `run.verifier` a vykonavatel bránu nezapne;
  - testy pod kontrolou vykonavatele: `--tests` překryje kopii pracovní složky a smaže `conftest.py` a podobné;
  - jedna syntaxe příkazu na serveru i v CLI: 13 společných `CHECK_VECTORS`;
  - kontroly jsou měřítko napříč koly: změnu nebo přidání v kole ≥ 2 smí jen člověk;
  - logika buňky v `brief_vault_cell.py`.
- **Untrusted:** server razítkuje `runTrust: "reported"` a klient ho poslat nesmí. UI ukazuje „běh nahlášen – neatestováno“.
  Na `verified` se neváže uzavření ani schválení karty; ověřeno grepem, `verified` čtou jen kola, poučení a Zrcadlo.
- **Vlastní nález:** `brief_vault_proposals._without_error` ignoroval jen `predictionError`, takže použitý návrh s `runTrust` zůstával `pending`.
  Opraveno přes `SERVER_FIELDS` a pokryto e2e testem.
- **Skutečný průchod (e2e `test_opora_cell.py`, uvicorn nad `tmp_path`, skutečný pytest):**
  1. Kolo 1: vykonavatel podstrčí `assert True` bez `slug.py` → `--tests` → `fail`.
  2. Poučení antipattern.
  3. Nové kolo, vykonavatel dodá `slug.py` → `pass`, `runTrust: reported`.
  4. Poučení pattern, viditelné v `lessons` disciplíny.
- **Návrh odděleného ověřovatele** (`docs/schranka-overovatel-navrh.md`, jen k review): zapsán rozpor z review Hermese.
  Jiný účet sám nestačí; je potřeba sandbox bez klíče oddělený od podepisovače a manifest s příkazy, závislostmi a vazbou proti replay.
  Žádný runtime, auth ani konfigurace.
- **Zbývá:** karta založená v kole 1 bez `checks` je přes `extend` nedostane. Kola ≥ 2 ale `checks` přidat nesmí, takže nesoulad nevznikne.

## Originály a sektory (pro koordinaci, žádný redesign)

Zdroje 00–09 nepředepisují sektory ani kontejnery podle disciplín:
- 00:5–7 oddělují uzel a kontrakt;
- 04:83–91 popisují mikrokrok s ověřením;
- 06:15–24 roli a acceptance;
- 07:103–116 artefakt, eval a paměť.

Rozpor `docs/schranka-neurony.md:89–91` (sektor podle disciplíny) vs. `docs/pyramida.md:26–27` (sektor = dodavatelný celek)
je tedy lokální mapování OPORA, ne autorita originálu k migraci. K15 ho neřeší. Případný additive návrh přijde až po ověřeném řezu.

## Koordinace s relací B

- Rozpor k rozhodnutí: **sektor = disciplína** (Schránka: 17 disciplín jako neurony, `brief_vault_disciplines.py`)
  vs. **sektor = dodavatelný celek** (pyramida oblast → sektor → karta, `docs/pyramida.md`). Relace A pyramidu nepřepisuje;
  buňka řezu nese disciplínu jako atribut, ne jako sektor.

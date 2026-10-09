# OporaHub: plán a dokumentace 1:1 s kódem

Rozhodnutí 2026-10-04: **pravda je v GitHubu.** Repozitář projektu drží kód, testy, dokumentaci i plán.
OPORA plán tvoří a ukazuje, OporaHub ho drží 1:1 s kódem. Live Run (monitor běhů, session, hooky,
telemetrie) je zrušený; jeho místo v přepínači prostředí (Alt+3) zaujímá OporaHub.

Tento kontrakt **nahrazuje** části 1, 2, 3, 6 („Do gitu se nezapisuje nic“), 16 a 17
v `docs/synchronizace-pravdy.md`. Echo, verdikt Oracle a brána 1:1 (části 4, 5, 7, 8) platí dál,
jen jejich „zacommitované zadání“ teď znamená commit v gitu.

## 1. Co kde leží

| Druh informace | Pravda leží | Verzuje | Kdo ji píše |
|---|---|---|---|
| Kód a testy | repozitář na GitHubu | git | agent a člověk |
| Dokumentace kódu (`docs/`, `README.md`) | repozitář | git | agent a člověk |
| Plán: oblasti, sektory, uzly, jejich zadání a vazby na kód | repozitář, složka `opora/plan/` | git | OPORA na pokyn člověka nebo orchestrátora |
| Pracovní kopie plánu, rozpracované zadání | OPORA (SQLite projektu) | revize v OPORA | Editor |
| Echo a verdikt | nikde; přepočítává Oracle | – | – |

Pravidlo: **co není v gitu, není hotové.** Plán v OPORA je pracovní kopie jako neuložený soubor
v editoru. Když se aplikace a repozitář rozejdou, rozhoduje člověk a v pochybnostech vyhrává repozitář.

## 2. Plán v repozitáři

Jeden soubor na rozsah, čitelný člověkem i agentem bez OPORA:

```
opora/plan/<oblast>/<sektor>/<uzel>.md
```

```markdown
---
id: node-checkout
kind: node            # area | sector | node
parent: sector-shop
revision: 3           # revize zadání v OPORA, ze které soubor vznikl
sources:              # vazby na kód; cesty relativní ke kořeni repa
  - frontend/checkout/
docs:
  - docs/checkout.md
---
# Pokladna

## Účel
…dlouhodobý účel (`node.purpose`)…

## Cíl
…pracovní zadání (`goal`)…

## Akceptace
- …
```

- Soubor je deterministický: stejný plán dá bajtově stejný soubor (pořadí klíčů, konce řádků, kódování UTF-8).
  Jinak by OporaHub hlásil rozdíl tam, kde žádný není.
- Pořadí uzlů a hierarchie se čte z cesty a `parent`, ne z pořadí souborů.
- Co v souboru není (poloha karty na plátně, barvy, rozvržení), patří Editoru a v gitu se neverzuje.
- `opora/plan/` píše jen OporaHub. Ruční úprava v repu je dovolená; OporaHub ji uvidí jako „repozitář je napřed“.

## 3. Stavy synchronizace rozsahu

| Stav | Kdy | Akce, která ho uzavře |
|---|---|---|
| `synced` | plán v OPORA = soubor v `main` repozitáře | – |
| `app-ahead` | OPORA má novější revizi, než je v repu | zapsat plán do repa |
| `repo-ahead` | soubor v `main` se liší a OPORA ho ještě nenačetla | načíst plán z repa |
| `conflict` | změna na obou stranách od posledního `synced` | člověk vybere stranu, nebo sloučí ručně |
| `app-only` | rozsah v OPORA nemá soubor | zapsat plán do repa |
| `repo-only` | soubor bez rozsahu v OPORA | načíst, nebo soubor smazat v repu |

Společný předek pro `conflict` je poslední `synced` stav: SHA blobu souboru v gitu a revize v OPORA,
uložené v OPORA jako záznam synchronizace. Bez předka OporaHub nerozhoduje a hlásí `conflict`.

K těmto stavům se přidává 1:1 s kódem z `synchronizace-pravdy.md`: vazby na existující cesty,
pár commitů, zelený běh, důkaz, dokumentace bez rozbitých odkazů. Rozsah je zelený, až když je
`synced` **a** projde bránou 1:1.

## 4. Zápis do repozitáře

- Spouští ho jen člověk (nebo orchestrátor schválený člověkem). Agent ani Oracle do repa plán nezapisují.
- Postup: náhled rozdílu → potvrzení → OPORA zapíše soubory do pracovního stromu připojeného repa
  na větev `opora/plan-<datum>` a vytvoří commit s trailerem `Opora-Plan: <rozsah>@<revize>`.
  Push a PR dělá člověk; OPORA nemá přístup k zápisu na GitHub.
- Zápis odmítne, když pracovní strom není čistý v `opora/plan/` nebo když větev nesedí na `main`.
- Git se volá přes `backend/integrations/gitio.py` (vypnuté hooky, čisté prostředí, timeout).

## 5. Načtení z repozitáře

- Čte `main` (ne pracovní strom), takže pravdou je jen to, co prošlo merge.
- `repo-ahead` načte soubor jako novou revizi zadání v OPORA s autorem `git:<sha>`.
  Rozpracované zadání v OPORA se nepřepisuje: rozsah přejde do `conflict`.

## 6. Prostředí OporaHub (Alt+3)

Jedno rozhraní pro všechny projekty; projekt bez připojeného repa ukáže jen větu, že OporaHub potřebuje repozitář
(rozhoduje `project-capabilities.ts`, dílek `sourceKind` nečte).

| Sloupec | Obsah |
|---|---|
| Rozsah | oblast, sektor, uzel a název |
| Plán | stav z části 3, revize v OPORA a krátké SHA v repu |
| Kód | vazby a jejich existence, spárované commity, proklik na GitHub |
| Dokumentace | dotčené dokumenty a rozbité odkazy |
| Brána | verdikt Oracle (`canMerge`, co blokuje, další krok) |

Akce: zapsat plán do repa (výběr rozsahů, náhled rozdílu), načíst z repa, vyřešit konflikt, přepočítat.
Dnes prostředí ukazuje existující dashboard Oracle (`frontend/project/sync-dashboard/`).

## 7. Co se ruší

- Vlastní úložiště commitů mimo git (`backend/canvas/opora_hub.py`, `opora_hub_store.py`, `oporahub/main.log`,
  tabulka `opora_commits`) a API `POST /api/opora-commit`, `GET /api/opora-commit(s)`, `POST /api/opora-merge`.
  Ruší se až v kroku 6 níže, kdy je brána přepojená na git. Commity, které v úložišti jsou, se jednorázově
  zapíší jako soubory plánu; historie mimo git se nepřevádí.
- „Push/export OporaHubu“ ze `synchronizace-pravdy.md` odpadá: zálohou plánu je git.
- Live Run a vše kolem běhů agentů (smazáno 2026-10-04).

## 8. Kroky

| # | Co | Kde | Velikost | Hotovo, když |
|---|---|---|---|---|
| 1 | Prostředí OporaHub místo Live Run, dashboard Oracle uvnitř | `frontend/layout/environment-switch/`, `frontend/hub/oporahub-workspace/` | S | Alt+3 ukáže OporaHub |
| 2 | Formát plánu: čisté funkce rozsah ↔ soubor, round-trip a determinismus | `backend/canvas/plan_files.py` + test vedle | M | `parse(render(x)) == x`, dvakrát stejné bajty |
| 3 | Čtení plánu z `main` a výpočet stavů z části 3 | `backend/canvas/plan_sync.py` + test vedle, `git_read.py` | M | stavy pro každý rozsah, žádný zápis |
| 4 | Read-only `GET /api/plan-sync` a sloupec Plán v OporaHubu | `backend/api/editor/`, `frontend/hub/` | M | člověk vidí, co je napřed |
| 5 | Zápis plánu do repa s náhledem a potvrzením | `backend/canvas/plan_write.py`, `POST /api/plan-sync/write` | M | větev + commit s trailerem, odmítnutí nečistého stromu |
| 6 | Brána 1:1 na git: `opora-uncommitted` = rozsah není `synced`; zrušit úložiště z části 7 | `sync_signals.py`, `sync_verdicts.py` | M | verdikt nečte `opora_commits` |
| 7 | Načtení z repa a řešení konfliktu | `plan_sync.py`, `frontend/hub/` | M | `repo-ahead` a `conflict` se dají uzavřít z UI |

Ověřovat na Ample (lokální projekt), doplňovat jen zjištěné nedostatky. Každý krok: `uv run pytest backend`,
`npm test`, `npm run build`.

## 9. Otevřené otázky pro člověka

1. Složka `opora/plan/` v kořeni repa, nebo pod `docs/`?
2. Má OPORA commit vytvořit sama (krok 5), nebo jen zapsat soubory a commit nechat člověku?
3. Patří do plánu i obsah karet mimo zadání (bloky, porty, zprávy na vazbách z `karta-pro-agenty.md`), nebo jen zadání a vazby?

## 10. Co kontrakt zakazuje

- Agent a Oracle nezapisují plán do repa ani nemergují.
- OPORA nepushuje na GitHub a nedrží zápisový token.
- Plán se nikdy nepřepisuje potichu: každý rozdíl má stav a rozhodne člověk.
- Nic z plánu nežije jen v OPORA déle, než trvá rozpracování; hotové je jen to, co je v `main`.

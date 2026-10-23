# Synchronizace pravdy: OPORA, kód, GitHub, Linear, Oracle

> **Od 2026-10-04 je pravda v GitHubu**, včetně plánu. Části 1, 2, 3, 6 (zákaz zápisu do gitu), 16 a 17
> nahrazuje `docs/oporahub.md`. Echo, verdikt Oracle a brána 1:1 platí dál.

Proces má čtyři vrstvy a jednu nad nimi.

- **Git a GitHub** drží čistý kód a jeho dokumentaci. Nic jiného.
- **OPORA** drží zadání, graf projektu, pracovní prostory agentů a důkazy jejich práce. Verzuje je vlastním úložištěm **OporaHub**: commity, větve, merge a main, oddělené pro každý projekt.
- **Linear** ukazuje stav práce lidem.
- **Oracle** je nejvyšší vrstva. Na pozadí čte všechny tři, porovnává je a posílá echo orchestrátorovi v OPORA. Sám nikdy nic nezapisuje.

Orchestrátor sedí v OPORA. Zadává práci agentům, vidí jejich pracovní prostor, přebírá důkazy a podle echa z Oracle rovná věci na 1:1.

Změna zadání je běžný stav. Hotová verze není konečná: produkt se vyvíjí, zadání dostane novou verzi a kód ji musí dohnat. Kontrakt proto neřeší, jak odchylce zabránit, ale jak ji vždy najít, pojmenovat a uzavřít.

## 1. Čtyři vrstvy a jejich role

| Vrstva | Co drží | Kdo zapisuje | Co nikdy nedělá |
|---|---|---|---|
| Git a GitHub | kód, testy, dokumentace kódu (`docs/`, `README.md`), commity, větve, PR | agent a člověk při práci na kódu | nedrží zadání, pracovní prostor ani důkazy práce |
| OPORA (OporaHub) | zadání, graf, pracovní prostory agentů, důkazy, knihovny komponent a postupů | Editor a orchestrátor přes API | nedrží kopii kódu ani vlastní stav úloh |
| Linear | stav práce, viditelnost pro lidi, vazba na PR | člověk, integrace | není zdrojem zadání ani důkazu |
| OpenViking | paměť rolí agentů | agenti | není pravda o kódu ani o zadání |
| Oracle | nic; vše přepočítává | – | nezapisuje do gitu, kódu, zadání ani do Linearu |

Pravidlo, které drží celý kontrakt: **kód a jeho dokumentace jsou v gitu, zadání a práce jsou v OPORA, a nic není na obou místech.** Když se dvě vrstvy rozejdou, nikdo nepřepisuje druhého. Oracle to ohlásí a rozhodne orchestrátor nebo člověk.

## 2. Pravda podle druhu informace

| Druh informace | Pravda leží | Verzuje | Při rozporu vyhrává |
|---|---|---|---|
| Zadání (oblast, sektor, uzel) | OPORA | commit OporaHub | OPORA |
| Graf projektu | OPORA | commit OporaHub | OPORA |
| Vazba na kód (cesta) | OPORA | commit OporaHub | OPORA; existenci cesty rozhoduje git |
| Kód a testy | git | git | git |
| Dokumentace kódu | git | git | kód, pokud dokumentace popisuje chování |
| Pracovní prostor agenta, průběh, důkazy | OPORA | revize a commit OporaHub | OPORA |
| Stav práce | Linear | Linear | Linear |
| Paměť agentů | OpenViking | vlastní | není pravda, je to popis stavu |
| Pár commitů a echo | přepočítává Oracle | – | svět, ze kterého vznikly |

## 3. OporaHub: commity, větve, main

OporaHub se chová jako GitHub, jen pro zadání a práci. Každý projekt otevřený v OPORA má vlastní oddělený OporaHub: vlastní commity, větve, merge, push a main.

- **Commit** je neměnný objekt a patří vždy jednomu rozsahu: **oblast, sektor, nebo uzel**.
  `{ id, parent, scope: {kind: area|sector|node, id}, project, createdAt, by, subject, entries[], pair }`
  `id` je SHA-256 kanonického obsahu, `parent` ukazuje na předchozí commit téhož rozsahu.
- **Obsah commitu** je zadání rozsahu v dané revizi, digest jeho podstromu v grafu, revize pracovních prostorů, odkazy na důkazy a pár na commity v gitu.
- **Větev** vzniká pro práci na jednom rozsahu a odpovídá větvi kódu, ve které agent pracuje.
- **Main** drží jen to, co je 1:1. Merge do mainu není zápis, ale výsledek brány z části 4.
- **Push** je export nebo synchronizace OporaHubu jinam. Protože zadání není v gitu, je záloha a přenos povinná výbava, ne doplněk.
- **Uložení** je append-only soubor ve složce projektu. SQLite je jen index, který jde z těch souborů kdykoli znovu postavit. Nová složka projektu se přidává v `backend/canvas/project_folder.py:16`.
- **Verze zadání** (`v1`, `v2`) je pojmenovaný ukazatel na commit, ne kopie obsahu.

Na čem to stojí už dnes: revize s porovnáním očekávané revize v `BEGIN IMMEDIATE` (`backend/editor/node/node_specs.py:62-77`), digest grafu a neměnné snímky (`backend/editor/agent_packet/desktop_v3_packets.py:51`, `:463-485`).

## 4. Brána 1:1

Do mainu OporaHubu jde jen rozsah, který projde všemi kontrolami. Kontroly jsou deterministické a jejich výsledek je vidět na dashboardu.

**Uzel:**

| # | Kontrola | Neprojde-li, hlásí se |
|---|---|---|
| 1 | Zadání je zacommitované, ne rozepsané | `opora-uncommitted` |
| 2 | Uzel má aspoň jednu vazbu na kód a každá cesta v gitu existuje ve správném druhu | `source-missing`, `source-renamed` |
| 3 | Existuje pár: commity plnící tuto revizi zadání jsou v `main` repozitáře kódu | `spec-ahead` |
| 4 | U páru je zaznamenaný zelený běh testů | `checks-unknown` |
| 5 | ~~Každý krok procesu má důkaz~~ (zrušeno 23. 10. spolu se staršími procesy) | – |
| 6 | Dokumentace dotčených cest nemá rozbitý odkaz | `doc-path-missing` |
| 7 | Uzel nemá otevřené echo s vysokou závažností | podle typu |

**Sektor:** všechny jeho uzly jsou zelené, jeho vlastní vazba na adresář platí a nemá otevřené echo s vysokou závažností.

**Oblast:** všechny sektory a uzly v ní jsou zelené.

Rozhodnutí: `spec-ahead` **blokuje merge do mainu a zelenou barvu, ale nikdy neblokuje práci ve větvi.** Zadání se smí měnit kdykoli; nesmí se jen tvářit jako splněné.

## 5. Stavy a barvy

| Stav | Kdy nastane | Co znamená |
|---|---|---|
| Rozpracováno | rozsah má větev, brána ještě neběžela nebo neprošla | práce běží |
| Čeká na 1:1 | práce hotová, ale některá kontrola neprošla | orchestrátor dostal echo s tím, co chybí |
| Zelené | commit rozsahu je v mainu OporaHubu | zadání, kód, testy a důkaz sedí |
| Uzavřeno | oblast, jejíž sektory a uzly jsou zelené, byla uzavřena člověkem | nehýbe se s ní; zápisy se odmítají |

Uzavřenou oblast otevře jen nová verze zadání, nová změna nebo nová funkce. Otevření je vědomý krok, zaznamená se jako commit a stav se vrací na rozpracováno.

## 6. Párování commitů

Pár spojuje commit OporaHubu s commity v gitu. **Žije jen v OPORA. Do gitu se nezapisuje nic.**

```
{ "oporaCommit": "…", "scope": { "kind": "node", "id": "…" }, "specRevision": 2,
  "gitCommits": ["…"], "branch": "work/…", "pr": 128, "task": "HEL-42",
  "evidence": "branch", "confidence": "strong" }
```

| # | Důkaz | Zdroj | Jistota |
|---|---|---|---|
| 1 | větev pracovního prostoru rozsahu; commity od `base_sha` po hlavu větve | `workspaces.branch`, `node_id`, `base_sha` | silná |
| 2 | klíč úlohy ve větvi nebo v popisu PR | git, Linear | silná |
| 3 | trailer `Opora-Node: <rozsah>@<revize>` v commitu, pokud si ho tým píše | zpráva commitu | silná, ale nepovinná |
| 4 | průnik změněných cest commitu s cestami rozsahu | `git log --name-only`, vazba na kód | slabá, jen návrh |

Echo vždy říká, jakou jistotu pár má. Slabý pár je návrh k potvrzení, ne fakt, a sám o sobě bránu neotevře.

Bránu navíc otevře jen pár, jehož commit v mainu skutečně sáhl na vlastněnou cestu (`touchesOwned`). Samotný trailer ve zprávě commitu je tvrzení pisatele, ne důkaz o kódu.

## 7. Echo pro orchestrátora

Echo je zpráva z dat, ne věta pro člověka. Vzniká deterministicky z OPORA, gitu, souborů a Linearu. **Model se na zjištění nepodílí.** Agent smí nad hotovým echem navrhnout opravu; takový návrh je odhad, ne důkaz.

```
{ "id": "sha256(typ + kanonický předmět)", "type": "spec-ahead", "severity": "high",
  "subject": { "scope": "node", "id": "…", "specRevision": 2 },
  "evidence": { "expected": "revize 2", "actual": "poslední pár nese revizi 1", "source": "pár 9f3…" },
  "observedAt": "…", "gitHead": "…", "action": "zadej práci" }
```

`id` je stabilní, takže stejná nerovnost při každém běhu nepřibývá a jde ji odložit.

| Typ | Jak se pozná | Závažnost | Akce, která ho uzavře |
|---|---|---|---|
| `spec-ahead` | zadání má vyšší revizi než poslední pár rozsahu | vysoká | zadej práci; uzavře ji nový pár |
| `code-unclaimed` | commit v `main` sahá do kódu, který nevlastní žádný rozsah | střední | přiřaď kód k zadání, nebo označ jako údržbu |
| `source-missing` | vazba míří na cestu, která v gitu není | vysoká | oprav vazbu nebo obnov soubor |
| `source-renamed` | cesta chybí a `git log --follow` najde nový název | střední | potvrď přesun |
| `planned-exists` | navrhovaná cesta už v gitu existuje | nízká | přepni návrh na existující zdroj |
| `duplicate-path` | dvě karty na téže cestě | střední | sluč nebo zpřesni |
| `checks-unknown` | pár nemá zaznamenaný zelený běh testů | vysoká | spusť testy a zapiš výsledek |
| `task-desync` | Linear hlásí hotovo, rozsah má otevřené `spec-ahead`, nebo opačně | střední | srovnej stav úlohy |
| `doc-path-missing` | dokumentace v gitu odkazuje na neexistující cestu | střední | oprav odkaz nebo dokument zruš |
| `base-stale` | `base_sha` pracovního prostoru už není předkem `main` | střední | rebase, nebo nové zadání |
| `opora-uncommitted` | rozepsané zadání bez commitu | nízká | potvrď commit |
| `workspace-orphan` | pracovní prostor nebo zadání bez rozsahu v grafu | nízká | ukliď nebo obnov |
| `closed-area-touched` | pokus o zápis do uzavřené oblasti | vysoká | otevři oblast novou verzí, nebo zápis zahoď |

Závažnost řídí chování: **vysoká** blokuje bránu, **střední** se ukazuje na kartě, **nízká** je jen v souhrnu.

Echo dorazí do OPORA jako zpráva k rozsahu. Dnešní zprávy agentů mají stránkování i potvrzení příjmu (`backend/editor/agent_handoff/message_store.py`), takže echo může jet stejnou cestou.

## 8. Verdikt Oracle

Oracle drží přehled nad celým procesem: nad párováním, nad OporaHubem i nad gitem, a nad tím, co s čím souvisí. U každého rozsahu odpovídá na jedinou otázku: smí se to commitnout?

```
{ "scope": { "kind": "node", "id": "…" }, "state": "waiting",
  "canCommit": true, "canMerge": false,
  "checks": [ { "id": "pair", "passed": true },
              { "id": "checks", "passed": false, "signal": "checks-unknown" } ],
  "blocking": ["checks-unknown"],
  "nextSteps": ["spusť testy a zapiš výsledek k páru"] }
```

- Verdikt je vždy odvozený z echa a párů, nikdy z odhadu. Každá nesplněná kontrola nese typ echa a jednu konkrétní další akci.
- Práci ve větvi blokuje jen echo o vazbě rozsahu (`source-missing`, `source-renamed`, `closed-area-touched`). Echo o hotovosti (`spec-ahead`, `checks-unknown`) blokuje merge, nikdy commit.
- Je vidět vizuálně: barva na kartě a sloupec Brána na dashboardu. Zelená smí, žlutá čeká a říká na co, červená nesmí a říká proč.
- Orchestrátor dostane verdikt jako zprávu k rozsahu. Rozhodnutí tak nestojí na tom, co si pamatuje z rozhovoru; kontext mu může utéct, verdikt zůstává.
- Stejný verdikt vidí i člověk, takže kontrola nad procesem nezávisí na tom, jestli zrovna běží agent.

## 9. Dashboard projektu

Na stránce projektu je přehled celého procesu. Ovládání napodobuje GitHub, jen se jmenuje OporaHub.

| Sloupec | Obsah |
|---|---|
| Commit | krátké `id` commitu OporaHubu |
| Rozsah | oblast, sektor, nebo uzel a jeho název |
| Zadání | revize a verze (`v2`) |
| Kód | `id` spárovaných commitů v gitu, proklik na GitHub |
| Brána | které kontroly z části 4 prošly |
| Stav | rozpracováno, čeká na 1:1, zelené, uzavřeno |
| Kdy a kdo | čas a autor |

Pohledy: main, větve, historie rozsahu, porovnání zadání mezi dvěma commity, seznam otevřeného echa. Akce: založit větev rozsahu, merge do mainu (jen když brána projde), uzavřít oblast, otevřít uzavřenou oblast novou verzí, odložit echo.

Celkový pohled na aplikaci se řídí tím, který repozitář je v OPORA otevřený. Projekty se nemíchají.

## 10. Oprávnění a zabezpečení

Rozhodnutí: **agenti do OporaHubu nezapisují.** Commit, merge a uzavření oblasti jsou úkony orchestrátora a člověka. Agent má svůj pracovní prostor a důkazy, nic víc. Chrání to historii proti překlepu, omylu agenta i proti běhu, který se splete.

| Role | Čte | Pracovní prostor svého rozsahu | Commit | Merge do mainu | Uzavřít nebo otevřít oblast |
|---|---|---|---|---|---|
| Agent (lokální i externí) | ano | ano | ne | ne | ne |
| Orchestrátor v OPORA | ano | ano | ano | jen když brána projde | navrhne |
| Člověk | ano | ano | ano | ano | ano |

Čím se to drží:

- Každý zápis nese autora (`human`, `orchestrator`, `agent`). Zápis s autorem `agent` mimo pracovní prostor se odmítne s 403.
- Commity jsou append-only soubory. Oprava se dělá novým commitem, nikdy přepisem.
- Revize mají porovnání očekávané revize, takže souběžný zápis přepíše jen ten, kdo měl aktuální stav (`node_specs.py:62-77`).
- Uzavřená oblast odmítá zápisy a pokus se ohlásí jako `closed-area-touched`.
- Zápisy vyžadují shodný Origin a JSON (`backend/app/factory.py:112-117`), řízení hooků běží jen na tomto počítači (`:105-108`) a vzdálený přístup vyžaduje token o délce aspoň 24 znaků (`backend/app/remote_access.py:19`).
- Main je pro zadání jen pro čtení (`backend/canvas/canvas_service.py:104-116`).

## 11. Linear: připraveno k zapnutí

Linear zatím není koupený. Integrace se postaví tak, aby stačilo doplnit klíč.

- Nastavení patří do `opora.toml`, sekce `[integrations]`, prázdná hodnota znamená nenastaveno; klíč jde přes proměnnou prostředí, nikdy do souboru.
- Klient je jen pro čtení: úloha, její stav a PR. OPORA drží pouze klíč úlohy u rozsahu, nikdy kopii stavu.
- Dokud není klíč vyplněný, sloupec Kód a úloha na dashboardu zůstává prázdný, echo `task-desync` se nepočítá a všechno ostatní běží beze změny. Stejný vzor jako automatika map, která je v novém datovém adresáři vždy vypnutá (`backend/project/maps/map_refresh.py:55-67`).
- Zapnutí: vyplnit klíč a restartovat backend. Nic dalšího se nemění.

## 12. Životní cyklus

| Fáze | OporaHub | git | Linear | Co Oracle vidí |
|---|---|---|---|---|
| Zadání v1 | commit rozsahu, revize 1 | – | úloha založena | rozsah bez páru → `spec-ahead` |
| Práce agenta | pracovní prostor, průběh, rozhodnutí | větev, commity | úloha běží | pár se skládá z větve |
| Důkaz | – (procesy zrušené 23. 10.) | testy v commitu | – | zelený běh, jinak `checks-unknown` |
| Brána | kontroly 1 až 7 | merge do `main` | úloha hotová | co neprošlo, jde jako echo |
| Merge | commit rozsahu v mainu OporaHubu | – | – | rozsah zezelená |
| Sektor a oblast | commit sektoru, pak oblasti | – | – | sektor zezelená, oblast smí být uzavřena |
| Zadání v2 | nový commit, `v2` ukazuje na něj | beze změny | nová úloha | `spec-ahead`, oblast se otevírá |

Pravidla, která platí vždy:

- **Hotovo znamená čtyři věci naráz**: důkaz v OPORA, zelené testy, merge v gitu a uzavřenou úlohu, spojené jedním párem.
- **Nová verze nic nemaže.** Starý commit i pár zůstávají a ukazují, co splnilo v1.
- **Rozdělaná práce se nezahazuje.** Pracovní prostor dostane `base-stale` a rozhodne jeho vlastník.
- **Agenti se učí na hotové práci.** Pracovní prostor zůstává čitelný, takže jiný agent naváže nebo pomůže.

## 13. Co už v kódu je a co chybí

| Část kontraktu | Existující mechanismus | Co chybí |
|---|---|---|
| Volání gitu | `backend/integrations/gitio.py:17-47`: vypnuté hooky a fsmonitor, čisté prostředí, timeout 15 s | `log`, `diff`, změněné cesty, `--find-renames`, trailery |
| Větev a základ práce | `workspaces.branch`, `node_id`, `base_sha` se zapisují (`backend/canvas/canvas_service.py:420-446`) | backend je nikdy nečte; párování na nich teprve postaví |
| Bezpečná cesta a stav cesty | `backend/project/workspace/workspace_sources.py:107-136`; `backend/editor/agent_packet/desktop_v3_packets.py:263-278` | převzít beze změny |
| Kontrola vazeb | `backend/canvas/canvas_service.py:327-378`, volaná z `:403` | běží jen při uložení změněného odkazu; při čtení se nekontroluje nic |
| Revize a snímky | `node_specs.py:62-77`; `desktop_v3_packets.py:51`, `:463-485`, `:501-504` | commit, který revize sváže do jednoho neměnného celku |
| Zprávy k rozsahu | `backend/editor/agent_handoff/message_store.py` | typ zprávy pro echo a jeho stav |
| Periodická práce | `backend/project/maps/map_refresh.py:55-155`; start z `backend/app/factory.py:73-78` | vzor je přenositelný beze změny |
| Ochrana zápisu | shodný Origin a JSON (`factory.py:112-117`), loopback (`:105-108`), token (`remote_access.py:19`) | autor zápisu, odmítnutí agenta, zámek uzavřené oblasti |
| Chování podle druhu projektu | `frontend/shared/project-capabilities/logic/project-capabilities.ts` | příznak, že projekt má OporaHub |
| Dashboard | – | celé |
| Linear | – | klient jen pro čtení a nastavení |
| Úložiště párů a echa | – | celé |

## 14. Dnešní stav

Změřeno 2026-09-17 nad projektem „OPORA Control Center — vývoj aplikace“ v `.data/production`, jen pro čtení.

| Co | Stav |
|---|---|
| Commity OporaHubu a páry | 0 |
| Karty s vazbou na kód | 0 z 55 (46 uzlů, 9 sektorů) |
| Uzly se zadáním | 9 ze 46, všechna neprázdná |
| Zadání s vazbou na commit | 0 z 9 |
| Rozbité odkazy v dokumentaci v gitu | 75, z toho 56 v jednom zastaralém dokumentu |
| Dokumenty pracovního prostoru s neexistující cestou | 14 z 18 |
| Cesty uvedené jen ve volném textu karet | 13, z toho 1 neexistuje |
| Osiřelá data po smazaných uzlech | 2 zadání, 1 text |
| Kód mimo git | 334 nesledovaných souborů `.py`, `.ts`, `.tsx`, `.css` |

Nuly u chybějících a přejmenovaných zdrojů jsou zavádějící: vycházejí nulové jen proto, že žádná vazba na kód zatím neexistuje.

## 15. Kroky

| # | Co | Kde | Velikost | Zprovozní | Co se nesmí rozbít |
|---|---|---|---|---|---|
| 1 | Čtení historie gitu: `log`, změněné cesty, přejmenování | `backend/integrations/git_read.py` + test vedle | S | podklad pro páry | chování `git()` |
| 2 | Párování commitů podle větve, úlohy a cest | `backend/canvas/commit_pairs.py` + test vedle | M | `spec-ahead`, `code-unclaimed` | žádný zápis do gitu |
| 3 | Výpočet echa a brány jako čisté funkce | `backend/canvas/sync_signals.py` + test vedle | M | většina echa | žádná změna schématu |
| 4 | Read-only endpoint a štítek stavu na kartě | `backend/api/editor/sync_routes.py`, `frontend/editor/node-detail/` | M | vidí to orchestrátor i člověk | jedno rozhraní pro všechny projekty |
| 5 | Kontrola dokumentace v gitu jako test | `tools/` + testy vedle, brána `lefthook` | S | `doc-path-missing` | nic v aplikaci |
| 6 | Autor zápisu a odmítnutí agenta | `backend/app/factory.py`, API editoru | S | zabezpečení historie | stávající kontroly Origin a tokenu |
| 7 | Commity OporaHubu: neměnné objekty, index, větev a main | `backend/canvas/`, `project_folder.py`, schéma | L | verzování zadání a práce | revize a jejich porovnání |
| 8 | Dashboard projektu: main, větve, commity, proklik na GitHub | `frontend/project/` | M | celkový pohled | jedno rozhraní pro všechny projekty |
| 9 | Brána merge, zelené stavy, uzavření a otevření oblasti | `backend/canvas/`, `frontend/editor/` | M | barvy a zámky | nic se nezavírá samo |
| 10 | Přepočet echa po změně `main` podle vzoru obnovy map | `backend/canvas/sync_refresh.py` | M | běh na pozadí | nový datový adresář zůstává vypnutý |
| 11 | Zaznamenaný běh testů u páru | `backend/canvas/check_runs.py` | M | `checks-unknown` | aplikace nespouští model |
| 12 | Linear jen pro čtení, vypnutý bez klíče | `backend/integrations/linear_client.py` + test vedle | M | `task-desync` | stav úloh se nekopíruje |

Pořadí: kroky 1 až 5 dají první echo a první kontrolu dokumentace během několika dnů, protože stojí na tom, co se už dnes zapisuje. Krok 6 zabezpečí historii dřív, než začne vznikat. Kroky 7 až 9 postaví OporaHub a dashboard. Kroky 10 až 12 doplní běh na pozadí, testy a Linear.

### Stav stavby k 2026-09-17

| Krok | Stav |
|---|---|
| 1 Čtení historie gitu | hotovo: `backend/integrations/git_read.py` (revize, předci, poslední commity, trailery, změněné cesty, přejmenování, SHA obsahu) |
| 2 Párování commitů | hotovo: `backend/canvas/commit_pairs.py` |
| 3 Echo a verdikt | hotovo: `backend/canvas/sync_signals.py` a `backend/canvas/sync_verdicts.py` |
| 4 Endpoint a štítek na kartě | hotovo: `GET /api/sync-report` (`backend/api/editor/sync_routes.py`, sběr `backend/canvas/sync_report.py`), štítek `frontend/editor/node-detail/sync-badge/` |
| 5 Kontrola dokumentace | hotovo: `tools/doc_check.py` a jednotný příkaz `npm run verify` (`tools/verify.py`) s ráčnou nad počtem rozbitých odkazů |
| 6 Autor zápisu a odmítnutí agenta | nezačato; potřebuje rozhodnutí, podle čeho se pisatel pozná |
| Scénáře vrstvy | hotovo: `backend/canvas/test_sync_scenarios.py` (běžné odchylky) a `backend/canvas/test_sync_adversarial.py` (chybující agent a kritik); seznam a nálezy drží `docs/scenare-vrstvy.md` |
| 7 Zaznamenaný běh testů u páru | hotovo: `backend/canvas/check_runs.py`, `POST /api/check-run`; zelený běh platí jen na commit z páru |
| 8 Dashboard projektu | hotovo: `frontend/project/sync-dashboard/` na úvodní obrazovce |
| 9 OporaHub | hotovo v jádru: `backend/canvas/opora_hub.py` a `opora_hub_store.py` (commit na rozsah, soubor jako pravda, SQLite jako index, main v `oporahub/main.log`), rozhraní `POST /api/opora-commit`, `GET /api/opora-commits`, `POST /api/opora-merge`; větve a push zatím ne |
| 6 Autor zápisu a odmítnutí agenta | částečně: OporaHub zápis bez autora odmítne a agent nesmí commitovat ani mergovat; ostatní API autora zatím nezná |
| 10 až 12 | nezačato: běh na pozadí, Linear |

Meze dnešního stavu: OporaHub se staví, takže se zatím nepočítá echo `opora-uncommitted`, `task-desync` ani `closed-area-touched`. Důkazem kroku je proces uzlu ve stavu `done` a běh kontrol se zapisuje ručně; aplikace testy nespouští.

## 16. Co kontrakt zakazuje

- Oracle nezapisuje do gitu, kódu, zadání ani do Linearu. Posílá echo.
- Aplikace nespouští žádný model. Echo je data.
- Zadání a práce nejsou v gitu. Kód a jeho dokumentace nejsou v OPORA.
- Agent nikdy necommituje, nemerguje ani nezavírá oblast.
- Do mainu OporaHubu se nic nedostane mimo bránu.
- SQLite je index nad append-only soubory, ne pravda.
- Stav úloh se z Linearu nekopíruje. Drží se odkaz.
- Slabý pár se nikdy nevydává za fakt.

## 17. Cena tohoto rozdělení

- Zadání neputuje s větví ani s merge. Nahrazuje to pár, proto musí být párování spolehlivé a jeho jistota vždy vidět.
- Git projekt nezachrání zadání. Export a obnova OporaHubu jsou povinná výbava.
- Bez traileru v commitu je nejsilnějším důkazem větev. Když agent pracuje mimo pracovní prostor rozsahu, pár bude slabý a echo to přizná.
- Dvě historie znamenají dvě místa, kde se dá udělat nepořádek. Proto smí commitovat jen orchestrátor a člověk.

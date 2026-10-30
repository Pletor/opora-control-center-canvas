# Metriky karty a spouštěče – velikost, složitost, postup, kdo to udělá

Stav: návrh k rozhodnutí (2026-10-30). Navazuje na `docs/navrhy/2026-10-30-vstupni-brana.md` (řezy 1–2 sloučené) a nahrazuje jeho řez 3.

Podklady:
- zadání člověka z 30. 10.: „spouštěče jako srdce, které aktivují ostatní procesy“, velikost plánu a úkolu, checklisty, % hotovo, rozpad, štítek složitosti → model, úsilí, poradce;
- průzkum kódu: `graph.py` (`card.model`, `card.effort`), `opora_plan_steps.py`, `opora_step_results.summary`, `opora_card_done.py`, `opora_proposal_risk.classify_risk`, `heart/inputs.wake_input`, rozhodnutí O10 v `docs/brain-heart-orchestrator.md`.

## 1. Proč

Dnes OPORA ví, co karta má udělat (kroky, `dod`), ale ne, **jak je velká**. Z toho plynou tři problémy:
- `card.effort` volí srdce odhadem;
- kancelář model a úsilí z karty nečte vůbec;
- nikdo si nevšimne, že je karta moc velká, zasekla se nebo selhává opakovaně.

Srdce se budí jen na tři druhy událostí. Princip: **metriky se počítají deterministicky z dat, která už existují (bez modelu a bez nových polí, která by někdo musel vyplňovat). Spouštěč je pravidlo „metrika překročí práh → existující kanál“.**

## 2. Měřák karty (`gauge`)

Počítá se, neukládá se (modul `backend/canvas/card_gauge.py`). Je v agent-state u každé karty a na odznaku ve Velínu.

| Metrika | Z čeho | K čemu |
|---|---|---|
| `steps` total / done / % | `spec.steps` + `step_results.summary` | checklist a % hotovo |
| `dod` splněno / 7 | `opora_card_done` | % k uzavření karty |
| `files` | sjednocení `steps[].files` | velikost zásahu |
| `kinds` | `steps[].kind` (code/test/docs/design/research) | design a research jsou dražší |
| `risk` | `classify_risk` nad `files` (standard/elevated/critical) | poradce a review člověka |
| `fanIn` / `fanOut` | vazby `next` | blokuje-li karta další práci (priorita) |
| `split` | počet dětí (`parent`) a hloubka | jak moc se úkol rozpadl |
| `attempts` / `failures` | běhy exekucí karty | opakované selhání |
| `age` | čas od claimu vůči velikosti | zaseknutí |
| `costUsd` | účetní kniha rozpočtů | cena vůči velikosti |

## 3. Štítek složitosti → kdo to udělá

Body (průhledný součet, prahy jsou výchozí a kalibrují se z `costUsd` hotových karet):

- kroky: 1 bod za každý, nejvýš 12;
- soubory: 0,5 bodu za každý, nejvýš 10;
- 2 body za každý krok `design` nebo `research`;
- riziko: `elevated` +3, `critical` +6;
- `fanIn`: 1 bod za každou vazbu, nejvýš 3.

| Štítek | Body | `effort` (O10) | Dělník | Poradce (kryje záda) |
|---|---|---|---|---|
| XS | ≤ 3 | low | sonnet | – |
| S | ≤ 6 | medium | sonnet | opus |
| M | ≤ 10 | high | sonnet | opus |
| L | ≤ 15 | xhigh | sonnet | opus |
| XL | > 15 | – | **nepředává se**; srdce kartu rozdělí | – |

- **Doporučení, ne příkaz.** `card.effort` od srdce nebo člověka má přednost. Odchylka od doporučení o víc než jeden stupeň se zobrazí ve Velínu a srdce ji uvidí ve snímku.
- `risk = critical` vždy vynutí poradce a review člověka, bez ohledu na štítek.
- Assignment (`opora_execution_validation.assignment`) a `node-brief` ponesou výsledný profil běhu `run: {label, effort, model, advisor}`. Kancelář ho přečte a podle něj spustí dělníka. Dnes je to jen v dokumentu O10.

## 4. Spouštěče (pevná tabulka v kódu, žádný engine)

Modul `backend/brain_opora/determinism/triggers.py` se vyhodnocuje v dávce srdce a při projekci událostí. Každý spouštěč jde jen existujícím kanálem: řádek do dávky srdce, eskalace člověku, nebo doporučení v `gauge`.

| Spouštěč | Podmínka | Akce |
|---|---|---|
| `card.too_big` | štítek XL u karty `ready` | probudit srdce: rozdělit kartu, nepředávat |
| `card.retry` | druhé `failures` | probudit srdce: přepsat nebo rozdělit (dnes jen pravidlo v promptu) a doporučit `effort` o stupeň výš |
| `card.stalled` | `age` > 3× medián pro daný štítek, bez události kroku | probudit srdce a jednou upozornit ve Velínu |
| `card.over_budget` | `costUsd` > 2× medián pro daný štítek | probudit srdce |
| `milestone.done` | všechna kritéria splněná | probudit srdce: odložené požadavky s podmínkou „po milníku X“ jsou k otevření |
| `milestone.progress` | % milníku = průměr % jeho karet | jen zobrazení, nebudí |
| `graph.human_change` | člověk přijal návrh plánu (`changeset.accepted` s autorem `human`) | probudit srdce jednou na revizi: přečíst změnu a navázat |

Každý spouštěč srdce probudí jen jednou na stav (klíč `trigger:karta:stav`), takže nevzniká záplava. Mediány se počítají z hotových karet projektu. Bez historie (méně než 5 karet) se `stalled` a `over_budget` nevyhodnocují.

## 5. Milníky a požadavky (původní řez 3 vstupní brány)

- Srdce milník jen **navrhne** (`opora_heart.py milestone`), uloží se se stavem `proposed` a srdce k němu položí `escalate`. Aktivovat nebo zamítnout ho smí jen člověk (`POST /api/intake/milestone`).
- **Změna schématu (vyžaduje souhlas člověka):** `intake_milestones.status` se rozšíří o `proposed`. SQLite neumí změnit CHECK, proto proběhne jednorázová přestavba tabulky v `project_schema.py` (rename → create → copy → drop → index). Tabulka je dnes prázdná, protože do ní zatím nic nezapisuje.
- Požadavky: `opora_heart.py intake … --requirement rq_…|new`. Několik vstupů se sloučí do jednoho požadavku. `later_extension` dostane stav `deferred` s podmínkou, otevře ho spouštěč `milestone.done`.
- Kritérium je splněné, když všechny jeho karty mají `done.confirmed`. Čte se jednou ze stavu plátna (stejný dotaz jako `opora_event_stage._done`).

## 6. Co se nemění

- Srdce zůstává jediný zapisovatel plátna. Spouštěče nic nezapisují, jen budí a doporučují.
- Brána uzavření karty, lidská brána a zeď se nemění.
- Na kartě nevznikne žádné nové pole k ručnímu vyplňování.

## 7. Řezy

1. **Milníky a požadavky:** §5, se změnou schématu po souhlasu, plus spouštěč `milestone.done`.
2. **Měřák a štítek:** `card_gauge.py`, `gauge` v agent-state, `run` v assignmentu a `node-brief`, snímek srdce.
3. **Spouštěče:** `triggers.py`, `card.too_big` / `card.retry` / `card.stalled` / `card.over_budget` a rozšíření `wake_input`.
4. **Velín:** odznak karty (štítek, % kroků, % dod, riziko), postup milníku a pohled „Požadavky a plán“.
5. **Kancelář:** spuštění dělníka podle `run` (model, úsilí, poradce). Jde do repozitáře kanceláře, ne do OPORY.

### Řez 2 – odchylky

- **Riziko:** `classify_risk` klasifikuje záznam návrhu (`proposal_kind`, změny), ne soubory. `card_gauge.risk_of` proto bere pravidla review kódu (`opora_review_risk`, `opora_review_jobs.toml`). Citlivá cesta (`risk.sensitive`, např. migrace, schéma, auth, `pyproject.toml`) znamená `critical`. Bezpečnostní cesta (`security.paths`) nebo aspoň `medium_files` souborů znamená `elevated`. Globy kroků se porovnávají jako cesty.
- **`costUsd` je zatím vždy `null`.** Účetní kniha rozpočtů (`opora_execution_budget_ledger`) vede pokusy a opravná kola, cenu ne. Cenu v USD (`listCostCents`) mají jen záznamy pozorovatelů exekucí. Napojení přijde se spouštěčem `card.over_budget` (řez 3).
- **`failures`** = běhy skončené bez výsledku (`released`, `cancelled`, `revoked`), které nepatří k otevřenému nebo sloučenému PR. Sloučení PR totiž běh také uvolní. `attempts` a `failures` se počítají z jedné historie běhů agent-state, která má strop 100 nejnovějších běhů projektu (`Executions.history`).
- **`age`** = sekundy od claimu nejnovějšího běhu, jen když běh drží platnou lhůtu, jinak `null`. Porovnání s velikostí (medián podle štítku) je až spouštěč `card.stalled`.
- **`run` v zadání** nese navíc `handout` a `humanReview`, aby kancelář XL nespustila a u `critical` věděla o review. Běžící běh v1 porovnává otisk s `run` ze svého claimu (`OporaExecutions.pinned_digest`), takže změna štítku nebo `card.effort` během běhu ho neodvolá. Běhy převzaté před zavedením `run` ho v zadání nemají a porovnání ho vynechá. V řídkém kontextu (v2) je zadání neměnné od claimu a `run` se přidá jen novým claimům.
- **`card.effort` a XL:** když rozhodlo srdce nebo člověk (`source: card`), karta se předá (`handout: true`) i při doporučení XL. Odchylku ukáže `mismatch`. `card.model` od srdce nebo člověka má přednost před modelem z tabulky O10.
- **Měřák** se počítá jen pro karty na zobrazené stránce `cards[]` (strop 100). Navíc nese `pointsBreakdown` (rozpis bodů), aby byl součet průhledný.

### Řez 2 – doplněk: chudé podklady

- **Proč:** na Ample dostalo všech 40 karet XS, protože srdce plánovalo karty s 0–1 krokem a bez `files`. XS tu lhal (nejslabší model bez poradce i u migrace s RLS).
- **`evidence`:** `thin`, když karta má nejvýš 1 krok a 0 souborů, jinak `ok` (v `gauge` i v `run`). Při `thin` se štítek nevydává: `label: "?"`, `recommended: null`, `mismatch` se nepočítá. Běh se vezme z `card.effort`/`card.model` (`source: card`), jinak bezpečný výchozí `medium` · sonnet+opus (`source: default`, `reason: "málo podkladů – doplň kroky a soubory"`). Snímek srdce ukáže `[? – doplň kroky a soubory]`.
- **Riziko z textu:** bez souborů hledá `risk_of` v názvu, `purpose` a `acceptance` kroků signály citlivých cest. Pravidla review kódu mají jen globy, proto se klíčová slova globů (`migrations`, `schema`, `auth`, `secret`) převádějí na slova textu (migrace, schéma, RLS, auth, oprávnění, secret) a signál platí jen, když jeho slovo v pravidlech je. Shoda dá nejvýš `elevated` s `reasons: ["text: migrace"]`; `critical` dávají jen skutečné soubory.
- **Prompt srdce:** realizační karta má 2–8 kroků, každý s `kind` a `files`.

### Řez 3 – odchylky

- **Ruční úprava plátna nemá událost.** Uložení grafu (`save_graph`) do outboxu nic nepíše, proto `graph.human_change`
  budí jen přijetí návrhu (`changeset.accepted`). Událost má napevno `actor: human`, i když přijímá srdce, takže
  spouštěč čte autora revize (`by.kind`) a přijetí srdcem nebudí. Platí pro přijetí grafu, zadání i obsahu.
  „Revize N“ je pořadí revize v prostoru.
- **Klíče jednou na stav:** `trigger:card:<nodeId>:too_big:XL<body>@<prostor>` (ID karet se mezi prostory mohou
  opakovat), `…:retry:<ID posledního selhaného běhu>` (každé nové selhání budí znovu), `…:stalled:<ID běhu>`,
  `…:over_budget:<ID běhu>`, `trigger:graph:<revize>:human_change`.
- **Kdy se vyhodnocuje:** supervisor při prvním čtení projektu, po událostech `changeset.accepted`, `lease.claimed`,
  `lease.expired`, `result.reported`, `stage.changed`, `card.reopened` nejvýš jednou za minutu a bez událostí jednou
  za 10 min (zaseknutý běh žádnou událost nepošle). Vyhodnocují se jen prostory s přijatým plánem (nejvýš 5) a v nich
  prvních 40 karet `ProcessSync`. Při projekci událostí se nevyhodnocuje.
- **Doba běhu hotové karty** = claim → poslední hlášení výsledku (`opora_execution_results.createdAt`), z historie
  100 nejnovějších běhů prostoru. `stalled` vyžaduje, aby za posledních 3× medián nepřišla žádná událost `step.*`.
- **`card.retry`** běží i u karty `blocked` nebo `needs-steps`; u XL (bez úsilí) doporučí rozdělení.
- **`card.over_budget`** se nevyhodnocuje, dokud `costUsd` chybí; Velín zatím spouštěče neukazuje (řez 4).

## 8. Ověření

- Karta Ample se 3 kroky a 2 soubory dostane štítek S, tedy sonnet s poradcem opus. Karta se 14 kroky, krokem design a migrací (`critical`) dostane XL a nepředá se; srdce dostane `card.too_big`.
- Druhé selhání stejné karty probudí srdce právě jednou a doporučí `effort` o stupeň výš.
- Splnění posledního kritéria milníku probudí srdce s odloženými požadavky.
- Testy leží vedle modulů. Spouštějí se jen cílené testy.

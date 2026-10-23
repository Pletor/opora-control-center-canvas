# A/B protokol agentů: starý protokol proti OporaHubu v2

Stav k 2026-10-23, z `origin/main` (`a6a28b0`). Zadání vlastníka:
„Vytvoř simulační příklad, který A/B testování, porovná výstup z těch dvou možností a vybere vítěze,
který je lepší. Na konci navrhni, jak by to mělo doopravdy vypadat, aby to agentům bylo ku prospěchu.“

## Krátce

- **Podle rubriky vyhrává B (OporaHub v2) těsně: 57,0 : 53,9.** Rozdíl je menší než váha kteréhokoli
  hlavního kritéria. Ani jedna varianta agentům nedává to podstatné.
- **A vyhrává tam, kde jde o agenta:** další karta dostane rozhodnutí, předávku, výsledky kroků
  i kontroly předchůdce (4 ze 6 značek). Průběh je vidět živě a pád agenta nic neztratí.
- **B vyhrává tam, kde jde o pravdu a cenu.** Commit u kroku je strojově, kontroly jsou vázané
  na commit, stav PR sleduje server a tvrzení je oddělené od ověření. Agenti čtou 6× méně bajtů
  a volají 2,5× méně.
- **B má tři díry, kvůli kterým by ho agenti dnes nesnesli.** Zadání nenese nic od předchůdců
  (0 ze 6 značek), PR Lens se nikdy neuloží (409, viz N1) a pád agenta smaže viditelný průběh
  (0 ze 4 kroků).
- **Odpověď je hybrid: B jako páteř, k tomu tři věci z A.** Předávka předchůdců v zadání,
  průběžné hlášení kroku a rozhodnutí jako strukturované pole výsledku. Varianta B+ (agent si
  předchůdce dočte sám) v simulaci našla 5 ze 6 značek za +2,6 volání a +2 kB na kartu; s ní by
  B mělo **77,8 bodu**. Návrh cílového stavu je v [§7](#7-jak-by-to-mělo-doopravdy-vypadat).

## 1. Co se porovnávalo

| | A: starý protokol | B: OporaHub v2 |
|---|---|---|
| Kdo ho používá | agenti dnes (`activity_log`: `lease` 1 339×, `agent-output` 630×, `brief-vault` 1 900×) | nikdo: 64 tabulek `opora_*` prázdných ve 13 projektech, 0× `executions/claim` |
| Kontext | `GET /api/desktop-v3/node-brief` (živě 249–300 kB na kartu ample) | `executions/context` → `claim` → `assignment` (neměnný snímek) |
| Kroky | bloky karty + úkoly bloků `{id,text,assignee,done}` ve `desktop-v3/state` | `spec.steps` v přijaté revizi, `stepResults` ve výsledku běhu |
| Oprávnění | `lease` (token, TTL) | execution (token, epocha, TTL, revize zadání) |
| Výstup | `agent-output` (bloky, zprávy na vazbách, `done`, rozhodnutí, `evidence`) | `results` (`summary`, `stepResults`, `selfChecks`), PR přes office, Lens |
| Hotovo | `done.confirmed` člověkem po bráně důkazů, které vyplní agent | `card_done_state`: kroky + přijetí + brána + merge + zápis plánu + člověk |

## 2. Jak simulace běžela

Harness je v `tools/ab-protokol/` (`uv run python tools/ab-protokol/sim.py`, test
`uv run pytest tools/ab-protokol -q`).

- **Skutečný backend, dočasná data.** Obě varianty volají `create_app(<tmp>)` přes FastAPI
  `TestClient`. Nic nejde na živou aplikaci `:8740` ani do `P:/opora-data`; živá aplikace byla jen
  čtena (`GET`) při tvorbě dat.
- **Data z ample.** Tři navazující karty sektoru 1: 1.3 RAW store → 1.5 Příjem zdroje → 1.6 API
  zdrojů. Obsahují 3, 4 a 3 bloky, zadání, vazby `next` a 31 rozhodnutí projektu. Pro simulaci
  jsou znovu otevřené. Data jsou v `tools/ab-protokol/fixtures/ample-3-karty.json` spolu s velikostmi jejich
  skutečných briefů.
- **Stejný scénář v obou variantách:** kontext → plán kroků → práce (skutečný commit po kroku
  v dočasném gitu) → hlášení po krocích → kontroly → review → přijetí člověkem → další karta
  převezme kontext. Agenti jsou skriptovaní a deterministickí, model se nevolá.
- **Předání kontextu se měří značkami.** Agent karty k zanechá `ROZHODNUTI-k`, `PREDAVKA-k`,
  `KROK-k-*`, `KONTROLA-k`, URL PR a `LENS-k`. Měří se, které z nich agent karty k+1 najde
  v odpovědích, které ve fázi kontext opravdu přečte.
- **Simulovaný je jen GitHub ve variantě B.** Čtení PR vrací hlavu ohlášenou office a sloučení
  se zapíše jako pozorování rekonciliace, stejně jako backendové testy. Úlohy review jsou vypnuté
  jako ve výchozí konfiguraci (`opora_review_jobs.toml: enabled = false`), takže brána je
  `external` (sloučení).
- **Kontext v1.** Kontext v2 na pracovní větvi gitu vrací 409 (N5). Office má ve výchozím stavu
  také v1 (`AGENT_OFFICE_OPORA_CONTEXT_VERSION`).
- **Poruchy** běží každá na čerstvé instanci: druhý claim téže karty, zápis předávky bez
  oprávnění, změna zadání během práce, pád agenta po 2 ze 4 kroků a opakované odeslání výsledku.

## 3. Rubrika (stanovená před během)

| | Kritérium | Váha | Jak se počítá |
|---|---|---:|---|
| K1 | Předání kontextu další kartě | 25 | podíl ze 6 značek předchůdce, které agent najde v tom, co ve fázi kontext přečte |
| K2 | Co člověk vidí a ověří | 20 | podíl z 8 faktů: stav po krocích, commit u kroku strojově, kontroly vázané na commit, PR se sledovaným stavem, Lens u karty, oddělení tvrzení od ověření, živý průběh, rozhodnutí dohledatelné ke kartě |
| K3 | Odolnost proti poruchám | 20 | podíl bezpečně zvládnutých poruch (částečně = 0,5) |
| K4 | Náklad agenta | 10 | 7 b. za bajty přečtené agenty na kartu, 3 b. za počet jejich volání; lepší varianta plný počet, horší poměrem |
| K5 | Náklad člověka | 5 | lidská volání na kartu včetně přijetí plánu |
| K6 | % hotovo ve třech úrovních | 10 | jde každou úroveň spočítat ze strukturovaných dat (1), jen z volného textu (0,5), vůbec (0) |
| K7 | PR a PR Lens | 10 | 5 b. za PR připojený strukturovaně se stavem z GitHubu, 5 b. za Lens uložený u karty |

Rubrika záměrně dává největší váhu tomu, co agent potřebuje na další kartě (K1). Druhé místo
mají dvě věci: co člověk může ověřit (K2) a co se stane, když se něco pokazí (K3).

## 4. Výsledky

Běh je deterministický. Opakované spuštění dá stejné skóre a počty volání; bajty se liší o jednotky bajtů kvůli časovým razítkům v odpovědích.

| Kritérium | Váha | A: starý protokol | B: OporaHub v2 | B+ (agent dočte předchůdce) |
|---|---:|---:|---:|---:|
| K1 Předání kontextu další kartě | 25 | **16,7** | 0,0 | **20,8** |
| K2 Co člověk vidí a ověří | 20 | 7,5 | **12,5** | 12,5 |
| K3 Odolnost proti poruchám | 20 | 14,0 | **16,0** | 16,0 |
| K4 Náklad agenta | 10 | 2,4 | **10,0** | 10,0 |
| K5 Náklad člověka | 5 | **5,0** | 3,5 | 3,5 |
| K6 % hotovo ve třech úrovních | 10 | 8,3 | **10,0** | 10,0 |
| K7 PR a PR Lens | 10 | 0,0 | **5,0** | 5,0 |
| **Celkem** | **100** | **53,9** | **57,0** | **77,8** |

U B+ jsou změřená kritéria K1 a K4: B+ stojí 15,3 volání a 114 792 B na kartu a je pořád
nejlevnější. Ostatní kritéria mají stejný tok jako B, proto mají stejné body.

### Náklad

| Metrika | A | B |
|---|---:|---:|
| volání agentů na kartu (vykonavatel, recenzent, office, plánovač) | 31,3 | 12,7 |
| bajty přečtené agenty na kartu (harness) | 670 211 | 112 664 |
| z toho fáze kontext na kartu | 78 387 | 67 897 |
| bajty zapsané agenty celkem | 28 390 | 15 494 |
| lidská volání na kartu | 3,0 | 4,3 |
| čtení `node-brief` (3 karty) | 12 | 0 |
| totéž na živých briefech ample (čtení × skutečná velikost) | **3,4 MB** | – |

Kam bajty jdou:

- **A:** `node-brief` 12× čte 952 kB. Zápis `block` 30× vrací 601 kB, protože každá odpověď nese
  celý stav (N8). `agent-output` 9× vrací 274 kB.
- **B:** `claim`, `heartbeat` a `assignment` vracejí každý celé zadání: 93 + 93 + 93 kB, tedy
  82 % všeho, co agenti v B čtou (N4).

### Předání kontextu (karta k → k+1)

| Varianta | Rozhodnutí | Předávka | Výsledky kroků | Kontroly | PR | Lens |
|---|---|---|---|---|---|---|
| A | ano | ano | ano | ano | ne | ne |
| B | ne | ne | ne | ne | ne | ne |
| B+ | ano | ano | ano | ano | ano | ne |

Lens nemá žádná varianta. V A pro něj není místo, v B se nikdy neuloží (N1).

### Co člověk vidí a může ověřit

| Fakt | A | B |
|---|---|---|
| stav po krocích | ano | ano |
| commit u kroku strojově | ne (jen text poznámky) | ano (`stepResults[].evidence.commits`) |
| kontroly vázané na commit | ne | ano (`selfChecks.headSha`) |
| PR se sledovaným stavem | ne (URL a „passed“ zapsal agent) | ano (vazba PR, stav z pozorování) |
| Lens u karty | ne | ne (N1) |
| tvrzení oddělené od ověření | ne | ano (`dod`: kroky / sloučeno / člověk) |
| živý průběh během práce | ano | ne (výsledek až na konci) |
| rozhodnutí dohledatelné ke kartě | ano | ne (jen text `summary`) |

### Poruchy

| Porucha | A | B |
|---|---|---|
| druhý claim téže karty | bezpečné (`lease` 409) | bezpečné (claim nenabídnut) |
| zápis předávky bez oprávnění | **nebezpečné**: `agent-workspace` bez lease → 200 (N7) | bezpečné (`agent-output` na kartu v běhu 409) |
| změna zadání během práce | bezpečné: `agent-output` 409; bloky hlášené proti starému zadání ale zůstanou „met“ a nikdo je neoznačí | bezpečné: `heartbeat` 409 i výsledek 409, změněný krok začíná znovu |
| pád agenta po 2 ze 4 kroků | bezpečné: po vypršení lease nový agent vidí bloky 1 a 2 hotové a log kroků | **nebezpečné**: Canvas vidí 0 ze 4 kroků. Commity jsou jen ve větvi, karta je zamčená do TTL a nový běh začíná od s1 (N3) |
| opakované odeslání výsledku | částečně: druhé odeslání → 409, agent nepozná, jestli první prošlo | bezpečné: stejné potvrzení (idempotence podle `requestId`) |

### % hotovo ve třech úrovních (plán vs. realita, #40)

| Úroveň | A | B |
|---|---|---|
| agent tvrdí | bloky `met` / bloky | `stepResults done` / kroky (`agent-state.cards[].steps`) |
| kód existuje | regex na SHA ve volném textu `block.state.note`, pak `git cat-file`; funguje jen díky disciplíně agenta | `stepResults[].evidence.commits` ∩ git, strukturovaně (office SHA bere z gitu, ne od agenta) |
| potvrzeno člověkem | jen celá karta (`done.confirmed`) | jen celá karta (`dod.human_close`), ale se sloučením a `mergeSha` |

Obě varianty v simulaci dosáhly 100 % na všech třech úrovních. V B se ale všechny tři úrovně
dají spočítat bez čtení volného textu.

## 5. Nálezy (konkrétní chyby a pasti)

| # | Nález | Důkaz ze simulace | Dopad |
|---|---|---|---|
| N1 | **PR Lens se v B nikdy neuloží.** Office posílá Lens až po výsledku a po otevření PR (`pull-request-handoff.ts:162`). Server ale chce aktivní běh (`opora_review_lens.py` `LensAddenda.submit` → `executions.active`) a po výsledku běh oprávnění nemá. Office chybu potichu spolkne (`.catch(() => undefined)`). | `POST /review-jobs/lens` → 409 „Execution is no longer authoritative.“ u 3 ze 3 karet | Lens plánu (#52/#43) neukáže u změn od agentů nic |
| N2 | **Zadání B nenese nic od předchůdců.** `assignment` obsahuje přijaté zadání, ne výsledky běhů na vazbách `next`. | B 0 ze 6 značek; B+ 5 ze 6 za +2,6 volání a +2 kB na kartu | další agent začíná naslepo, i když data v OporaHubu jsou |
| N3 | **B nemá průběžné hlášení kroku.** `stepResults` přijdou jen ve finálním výsledku. | pád po 2 krocích → 0 ze 4 viditelných, nový běh od s1 | ztráta práce a znovu tytéž kroky |
| N4 | **Zadání se v B posílá 3×.** `claim`, `heartbeat` a `assignment` vracejí každý celé zadání. | 3 × 31 kB na kartu, 82 % čtení v B | zbytečný kontext při každém heartbeatu |
| N5 | **Kontext v2 na pracovní větvi gitu vrací 409** („SQL promotion requires the current accepted graph manifest“). Skill říká „nedostupné v2 = konec, ne tichý v1“; office má výchozí v1. | `POST /executions/context` v2 → 409 u každé karty | samostatný agent podle skillu by kartu vůbec nevzal |
| N6 | **V A si agent zápisem plánu zneplatní vlastní zadání.** Úkol bloku mění `contextVersion`, takže vlastní `agent-output` dostane 409. | 3 ze 3 karet; agent musí znovu číst brief (živě 250–300 kB) | dvojí čtení briefu a matoucí 409 |
| N7 | **V A hlídá `agent-workspace` lease.** Kdokoli přepíše předávku karty, kterou drží jiný agent. | cizí agent bez lease → 200 | tichá ztráta předávky |
| N8 | **Každý zápis bloku v A vrací celý stav plátna.** | 30 zápisů × ~20 kB = 601 kB na 3 karty (na živém ample by stav měl 1,4 MB) | kontext agenta zahlcený stavem, který nepotřebuje |
| N9 | **`node-brief` je na živých datech obrovský** (249–300 kB). Největší části jsou `specification`, `context.decisions`, `orientation` a `boundaries` (viz audit sirotků č. 7). | 12 čtení = 3,4 MB na 3 karty; v harnessu jen 61–80 kB | hlavní náklad starého protokolu |
| N10 | **V A není review ani důkaz merge vázaný na commit.** „Merge passed“ a URL PR píše agent do `evidence` a brána uzavření jim věří. | uzavření prošlo s důkazy, které nikdo neověřil | potvrzení člověkem stojí na tvrzení agenta |
| N11 | **V B nemají rozhodnutí místo ve výsledku.** Zůstanou jen v textu `summary`. | rozhodnutí karty 0 v B, A je vede v `decisions` s `nodeId` | paměť projektu se v B nepočítá |

## 6. Vítěz

**B, ale jen jako páteř. Skutečný vítěz je hybrid.**

- Proč B: všechno, co člověk potřebuje ověřit (K2, K6, K7), a všechno, co šetří agenta (K4),
  B dělá strukturovaně a levněji. Jeho slabiny (N1–N5, N11) jsou úzké a opravitelné v kódu,
  který už existuje. Data pro předávku v B jsou a B+ to dokládá: stačí je dát do zadání.
- Proč ne čisté B: dnes by agent na kartě 1.5 nevěděl, co rozhodla karta 1.3. To je přesně to,
  co dělá starý protokol užitečným (K1 = 16,7 proti 0).
- Proč ne A: brief roste s projektem (živě 250–300 kB × 4 čtení na kartu). Commity, PR a kontroly
  jsou jen text. Merge a review potvrzuje agent sám a předávku smí přepsat kdokoli (N7–N10).
- Citlivost: rozdíl A–B je 3,1 bodu a samotné K1 dává A náskok 16,7. Při jiné rozumné váze by
  mohlo vyhrát A. Rozdíl B+ proti oběma (≥ 20 bodů) je stabilní při jakékoli rozumné váze.

## 7. Jak by to mělo doopravdy vypadat

Cíl: **jeden zápisový protokol pro agenty (execution) a jedno čtení na začátku (zadání
s předávkou).** Přidávají se průběžné kroky, strukturovaná rozhodnutí a Lens během běhu.
Člověk dál pracuje na plátně, agent na plátno nezapisuje.

### Tok agenta v cílovém stavu

1. `GET /api/oporahub/agent-state` (ETag) → první `ready` claim.
2. `POST /executions/claim` → odpověď bez zadání (jen lease, revize, otisk).
3. `GET /executions/{id}/assignment` → přijaté zadání a kroky. Nově i **`handoff`**: pro každého
   předchůdce na vazbě `next` souhrn, `stepResults`, rozhodnutí, PR (číslo, stav, `mergeSha`)
   a odkaz na Lens. Strop 8 kB, což je „signální balíček“ z #40.
4. Práce po krocích. Po každém kroku **`POST /executions/{id}/steps`**
   `{stepId, status, evidence}`, idempotentně podle `requestId`. Pád tak neztratí hotové kroky.
   Heartbeat vrací jen lease.
5. `POST /executions/{id}/results`: `summary`, `stepResults` (doplní, co nepřišlo průběžně),
   `selfChecks`, nově **`decisions[]`** (uloží se jako rozhodnutí karty s `executionId`)
   a nepovinně **`lens`**, aby Lens přišel ještě s platným oprávněním.
6. Office pushne, otevře PR a připojí ho. Pokud Lens nepřišel ve výsledku, pošle ho podle opravy
   N1 (server přijme Lens pro běh ve stavu `reported` s otevřeným PR na téže hlavě).
7. Review a sloučení běží jako dnes. Plán se zapíše zpět, `dod` se doplní a člověk uzavře kartu.

### Co zůstává, co se mění, co odchází

| Část | Verdikt | Pozn. |
|---|---|---|
| `executions/*` (claim, heartbeat, assignment, results, release), `stepResults`, `card_done_state`, `agent-state` | **zůstává**, páteř | heartbeat a claim bez zadání (N4) |
| `changesets` + `accept`, `spec.steps`, `opora_plan_steps_migration` | **zůstává** | kroky se mění jen návrhem, který přijme člověk |
| `executions/{id}/pull-request`, rekonciliace, `opora_review_lens`, `review-lens` | **zůstává** | Lens opravit (N1) |
| `executions/{id}/steps` (nové), `assignment.handoff` (nové), `result.decisions` (nové) | **přibývá** | tři věci převzaté z A |
| `desktop-v3/state`, `block`, `node-spec`, `node-text` | **zůstávají pro člověka** | agent na ně nezapisuje (u zapsaných karet to už platí) |
| `node-brief` | **zůstává jako lidský a orientační pohled** | zeštíhlit (#42, #53, audit č. 7). Agent ho v cílovém toku nepotřebuje |
| `brief-vault` (schránka zadání) | **zůstává** | jiná věc než vykonávání karty (sběr a příprava zadání) |
| `desktop-v3/lease`, `agent-output`, agentí zápisy `block` a `agent-workspace`, `frontier`, `pipeline`/`stages` | **odchází pro agenty** | po pilotu agentům 410; lidské operace zůstanou. Skill `legacy.md` pryč |
| `card_leases`, `agent_result_records`, `assignment_snapshots`, `agent_workspace_revisions` | **jen ke čtení**, mazat až po 30 dnech bez zápisu | historie výsledků zůstane čitelná v detailu karty |
| `review-jobs/claim` dotazování naprázdno | **nahradit** backoffem (office #53) | 3 668 prázdných claimů za 7 h |

### Migrace po malých PR (každé z čerstvého `main`, bez řetězení)

| PR | Repo | Co | Hotovo když |
|---|---|---|---|
| M1 | Opora | Lens přijme i běh `reported` s otevřeným PR na téže hlavě; `results` přijme nepovinné `lens` | harness: B má „Lens u karty: ano“ |
| M2 | Opora | `heartbeat` a `claim` bez `assignment` | harness: B čte ≤ 55 kB na kartu |
| M3 | Opora | `assignment.handoff` z předchůdců (`next`), strop 8 kB, mění otisk jen při změně předchůdce | harness: B má K1 ≥ 5/6 bez B+ |
| M4 | Opora | `POST /executions/{id}/steps` (průběžný krok, idempotentní) a `result.decisions[]` | harness: pád po 2 krocích → 2/4 vidět, nový běh od s3 |
| M5 | Office | prompt nese `handoff`; pomocník `execution-worker.ts step <id>` po commitu kroku; Lens ve výsledku; `boss-attention` čte `agent-state.dod` místo briefu | `npm test`, headless screenshot okna Živý proces |
| M6 | Opora | kontext v2 na pracovní větvi gitu (N5) nebo úprava skillu, aby v1 nebyla „konec“ | samostatný agent podle skillu vezme kartu |
| M7 | Opora + člověk | pilot na sektoru 1 ample: `opora_plan_steps_migration --apply`, člověk přijme základ a kroky jednou dávkou, office jede jen přes executions | první karta přes office od claimu po `human_close` |
| M8 | Opora | po pilotu agentí zápisy starého protokolu → 410; `legacy.md` pryč; brief zeštíhlený (#42, #53) | `activity_log`: 0 agentích `lease`/`agent-output` za týden |
| M9 | Opora | tabulky starého protokolu jen ke čtení, smazání migrací po 30 dnech | audit sirotků bez položek starého protokolu |

M1–M4 jsou na sobě nezávislé a dají se dělat souběžně. M7 je první okamžik, kdy OporaHub opravdu
poběží. Do té doby je M8 předčasné.

### Co se změní v kanceláři (agent-office)

- `execution-prompt.ts`: místo kontextu z živého briefu přijde `handoff` ze zadání. Do kroků
  přibude „po commitu kroku spusť `… step <id>`“.
- `execution-worker.ts`: nový podpříkaz `step` (stejný bundle a token jako `results`) a pole
  `decisions` a `lens` ve výsledku.
- `pull-request-handoff.ts` / `pr-lens.ts`: Lens odchází ve výsledku. Selhání se zaloguje do
  procesu (dnes ho kancelář spolkne).
- Okno Živý proces (#39) dostane události `step.started` / `step.done` průběžně, ne až na konci běhu.
- `boss-attention`: stav karty z `agent-state` (`steps`, `dod`), ne z `node-brief`.

### Návaznost na plán vs. realita (#40) a PR Lens (#52, #43)

- **Tři úrovně % hotovo** vychází z `agent-state` bez čtení textu:
  - agent tvrdí = `steps.done / steps.total`;
  - kód existuje = commity kroků z `stepResults` nalezené v gitu;
  - potvrzeno člověkem = commit kroku je předkem `mergeSha` sloučeného PR a karta má
    `human_close`.
  
  Úroveň „potvrzeno“ tak jde poprvé spočítat i **po krocích**, ne jen za celou kartu.
- **Lens na uzlech:** karta = Lens PR jejího běhu (po M1 skutečně uložený), oblast = Lens plánu
  (#52 API, #43 UI). Bez M1 ukáže #43 u změn agentů prázdno.
- **Signální balíček 8 kB** z #40 je přesně `assignment.handoff` (M3). Stejný tvar může číst okno
  v kanceláři.

## 8. Omezení simulace

- Jen tři karty z jednoho sektoru, skriptovaní agenti a jeden průchod bez paralelní práce.
- Brief v harnessu (61–80 kB) je menší než živý (249–300 kB), protože okolní projekt je
  menší. Proto uvádíme i přepočet na skutečné velikosti.
- Ve variantě B je simulovaný GitHub (čtení PR, sloučení). Úlohy review jsou vypnuté jako ve
  výchozí konfiguraci, takže skutečné review hledačů a ověřovatelů se neměřilo.
- Kontext v1, protože v2 na pracovní větvi gitu neprošel (N5).
- Značky měří, jestli informace dorazila, ne jestli je užitečná. Náklad člověka je počet volání,
  ne čas.
- Váhy rubriky jsou úsudek. Citlivost je popsaná v §6.

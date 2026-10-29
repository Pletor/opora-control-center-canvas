# Schránka: neurony a brány – kontrakt

Stav: **kontrakt K1** (2026-10-14). Kód ho provádí, nemění. Navazuje na [navrh-schranka-zadani.md](navrh-schranka-zadani.md); sekci „Dvě stopy a levé menu“ v něm nahrazují **disciplíny** z §2 (stopa `ux` → `ux`, `logic` → `be`).

## 1. Proč

Schránka má být proces, který řídí agenti, ne formulář. Princip přebíráme z cyklu „neuron-brain“ (impulz → scope → přínos/riziko → syntéza s typovaným mikrokrokem → vážení → rozhodnutí → pokyn → artefakt → eval → paměť), ale **bez divadla rolí**: dnešní modely kvalitu nezvýší básněmi dvou polarit, zvýší ji typovaný stav, malé ověřitelné kroky, měření před optimalizací a nezávislý kritik. Každý krok cyklu je proto **brána ano/ne** na fragmentu, kterou hlídá server. Agent nepotřebuje nic víc než „dej mi další práci“ a „tato brána je splněná / není“.

Aplikace sama model nespouští. Agenti (relace Claude Code, Hermes…) Schránku ovládají přes API; výjimky běhu modelu jsou jen v §7 a v [zrcadlo.md](zrcadlo.md).

## 2. Disciplíny (neurony)

Každý fragment patří právě jedné disciplíně. Disciplína se dědí od předka (jako dosud stopa), dítě ji smí přepsat. Neuron = disciplína, která má aspoň jeden živý fragment; jinak je „spící“ a v UI se neukazuje.

| Skupina | Disciplína (`discipline`) | Popisek | `card.layer` | Závěrečné 4 bloky logiky |
|---|---|---|---|---|
| kreslení | `cx` | CX (zkušenost zákazníka) | frontend | – |
| kreslení | `ux` | UX (tok, obrazovky, stavy) | frontend | – |
| kreslení | `ui` | UI (vzhled, komponenty) | frontend | – |
| kreslení | `content` | Obsah a texty | frontend | – |
| logika | `fe` | Frontend (implementace) | frontend | – |
| logika | `be` | Backend | backend | ano |
| logika | `api` | API a kontrakty | backend | ano |
| logika | `db` | Databáze a datový model | database | ano |
| logika | `cache` | Cache | database | ano |
| logika | `ai` | AI a agenti (retrieval, paměť, routing) | backend | ano |
| logika | `security` | Bezpečnost a soukromí | backend | ano |
| logika | `data` | Data a analytika | backend | ano |
| logika | `test` | Testy, QA, evaly | backend | – |
| provoz | `infra` | Infrastruktura | (bez) | – |
| provoz | `cloud` | Cloud | (bez) | – |
| provoz | `devops` | CI/CD a nasazení | (bez) | – |
| provoz | `observability` | Logy, metriky, trasování | (bez) | – |

- Jediný zdroj této tabulky: `backend/editor/brief_vault/brief_vault_disciplines.py` (+ test) a jeho zrcadlo `frontend/editor/brief-vault-dock/logic/disciplines.ts` (+ test, který kontroluje shodu s výstupem `GET /api/brief-vault/disciplines`).
- „Závěrečné 4 bloky“ = Funkce a metody → Spolupráce → Test částí → Komponenta (port `Komponenta hotová → frontend`), jak je popsáno v navrh-schranka-zadani.md.
- Kořen nové schránky disciplínu nese vždy (400 bez ní).

### Migrace

- Nový sloupec `discipline TEXT NULL` v `brief_fragment_revisions`, idempotentní (`add_column`).
- Jednorázové naplnění v téže migraci: `track='ux'` → `ux`, `track='logic'` → `be`, `NULL` zůstává `NULL` (= „nezařazené“). Je to doplnění schématu, ne změna obsahu; revize nepřibývají. Stejné doplnění dělá `with_later_stores` pro staré snímky verzí plátna.
- Kód přestane `track` číst i psát; `op: set-track` se nahradí `op: set-discipline` (stejná pravidla). Sloupec `track` v databázi zůstane jen jako historická data (mazat sloupce SQLite neumí bezpečně u živých dat).
- API: `discipline`, `effectiveDiscipline`; filtr `discipline=<id>|none`. `node-brief` nese `effectiveDiscipline`.

## 3. Brány cyklu

Osm bran v pevném pořadí. Uložené jsou na revizi fragmentu ve sloupci `gates TEXT` (JSON `{brána: {value, payload, by, actor, at}}`, chybějící = `false`).

| # | Brána | Znamená | Payload (validovaný) |
|---|---|---|---|
| 1 | `scoped` | fragment patří projektu a své disciplíně | – |
| 2 | `weighed` | zapsán přínos a riziko | `{benefit ≤280, risk ≤280}` |
| 3 | `synthesized` | typovaný mikrokrok s kritériem hotovo a předpovědí | `{type, done ≤500, prediction: {tests: "pass"\|"fail", criticRounds: 0–2, risk ≤280}, steps?, layer?, nonGoals?, checks?}` (`checks` viz docs/schranka-bunka.md) |
| 4 | `decided` | rozhodnutí ano / jinak / ne | `{verdict: "yes"\|"other"\|"no", reason ≤500}` |
| 5 | `planned` | návrh struktury na plátně (dryRun) | – (server vypočítá, §5) |
| 6 | `placed` | karty založené | – (server zapíše uložený plán, §5) |
| 7 | `verified` | výsledek ověřen proti předpovědi | `{actual: {tests: "pass"\|"fail"\|"untested", planApproved?: bool, planScore?: 0–10, criticRounds: 0–3, unexpected: bool, run?}}` (`run` viz docs/schranka-bunka.md) |
| 8 | `learned` | poučení zapsáno do paměti | `{lesson ≤500, kind: "pattern"\|"antipattern"}` |

`type` mikrokroku: `PIPELINE | RETRIEVAL | MEMORY | TOOL | ROUTING | EVAL | ENCRYPTION | SCHEMA | UI | FLOW | API | DATA | INFRA | DOC`.

Payload `synthesized` smí nést volitelné `steps: [text ≤300, 1–12 položek]` (konkrétní kroky mikrokroku jen v rozsahu `done`, z nich vzniknou bloky karty, §12) a `layer: "frontend"|"backend"|"database"`, které přebije `card.layer` z disciplíny (§2), např. backendový krok v disciplíně CX. Položka `steps` je text ≤300, nebo objekt `{text ≤300, condition ≤300}`: `condition` se stane podmínkou bloku (bez ní dostane krok „Krok proveden: …“ a poslední krok celé `done`, nikdy oříznuté uprostřed slova). Volitelné `nonGoals: [text ≤200, 0–6 položek]` se zapíše do `spec.non_goals` karty (odrážky) a v dalším kole se aktualizuje jako `goal`; bez `nonGoals` zůstává stávající `non_goals` karty beze změny (K14).

Pravidla (hlídá server, ne UI):

- **Pořadí:** bránu N jde zapnout, jen když jsou zapnuté brány 1…N−1. Vypnutí brány N vypne i N+1…8 (jejich payload zůstane v historii revizí).
- **Append-only:** každá změna brány = nová revize fragmentu se stejným textem, `note` povinná, CAS přes `expectedRevision`. Text, název a disciplína se branou nemění.
- **`decided` = `no`:** fragment je „slepá ulička“: `/next` ho přeskakuje, brány 5–8 nejdou zapnout, v UI je ztlumený s důvodem. `other` = vrátit k přepracování: brány 3–4 se po zápisu vypnou samy a fragment se vrací do fronty od brány 3.
- **`placed`** zapisuje na plátno, proto podléhá stejnému schválení jako `/api/canvas-plan` (cesta je v `WRITE_ROUTES`; schválení člověka v asistentovi i v `opora_write.py`).
- **Plán schválen ≠ testy prošly (§13):** `planApproved` = kritik schválil plán kola (`planScore` ≥ 8); `tests` je jen výsledek skutečně spuštěných testů, `"untested"` = neběžely. Bez `planApproved` (starší payloady) platí `planApproved = (tests == "pass")`.
- **`verified`:** server spočítá **predikční chybu** `e = (t + r + u) / 3`, kde `t` = 1 když se mine předpověď výsledku (při `tests` `pass`/`fail` se porovná `actual.tests` s `prediction.tests`, při `"untested"` `planApproved` s předpovědí: `prediction.tests == "pass"` = „plán projde“), jinak 0; `r = min(|actual.criticRounds − prediction.criticRounds|, 2) / 2`; `u` = 1 když `actual.unexpected`, jinak 0. Uloží ji do payloadu brány (`predictionError`, 0–1, dvě desetinná místa).
- **`learned`** založí poučení (§6) navázané na fragment a disciplínu.
- Fragment, jehož předek má `placed = true`, je pokrytý předkem: brány na něm jdou zapnout jen ručně, `/next` ho nevrací.

### API

- `POST /api/brief-vault` `op: "gate"` `{fragmentId, expectedRevision, gate, value: true|false, note, payload?}` → `{ok, fragment, gates}`. Neplatná brána, payload nebo pořadí = 400; CAS = 409; `placed` bez schválení = jako dnes zápis bez schválení.
- `GET /api/brief-vault/next?project&workspace&discipline?` → `{fragment: {id, title, effectiveDiscipline, revision}, gate: "<první vypnutá brána>", hint: "<co brána čeká, česky>"}` nebo `{fragment: null}`. Pořadí fronty: nejnižší číslo chybějící brány, pak mělčí fragment, pak `ord`. Přeskakuje smazané, `decided=no` a pokryté předkem.
- `GET /api/brief-vault/disciplines` → tabulka §2 + počet živých fragmentů na disciplínu (neuron zapnutý = počet > 0).
- Strom (`GET /api/brief-vault`) nese u fragmentu `gates` (jen booleovské hodnoty a `predictionError`) a `gateStep` (počet zapnutých bran 0–8).

## 4. Generování struktury (brány `planned` a `placed`)

Plán se skládá **na serveru** (`backend/editor/brief_vault/brief_vault_plan.py` + test) a frontendový `vault-plan.ts` se smaže; tlačítka „Vložit vybrané“ a „Rozdistribuovat zbytek“ volají `POST /api/brief-vault/plan {fragmentIds}` (jen čtení: vrátí dávku a souhrn) a dávku pošlou na `/api/canvas-plan` se schválením jako dnes, aby existovalo jediné pravidlo, jak z fragmentu vzniká karta.

Skládání pro fragment F s platnou disciplínou D ve skupině G, ve vrstvě scope (sektor nebo plátno, kde schránka visí):

1. **Oblast** skupiny G (`kind: area`, název „Kreslení“ / „Logika“ / „Provoz“). Existuje-li ve vrstvě oblast se značkou `briefGroup = G` (pole stavu uzlu, ne název), použije se `@id`, jinak se založí.
2. **Sektor** disciplíny D uvnitř oblasti (značka `briefDiscipline = D`), znovu použitý nebo nový, název podle popisku z §2.
3. **Uzly**: jedna karta za F (list) nebo za každého přímého potomka F druhu `brief`; tvar karty jako dosud (název `[task] …`, `card.status: draft`, `card.layer` podle §2, bloky z podfragmentů nejvýš 36, u disciplín s „ano“ v posledním sloupci §2 navíc 4 závěrečné bloky, `fragmentRef`). Karta nese `spec.goal` = `done` z brány `synthesized` a `spec.acceptance` = typ mikrokroku + `done`.
4. **Vazby:** pořadí sourozenců `next`. Vazbu z portu `Komponenta hotová → frontend` plán sám nezakládá (fragment má jednu disciplínu, protějšek `fe` nejde určit spolehlivě); dotáhne ji agent nebo člověk.

`planned` uloží souhrn dryRun, otisk plánu (sha256 kanonického JSON) a `scopeDigest` kontejneru plánu (vrstva, použitá oblast a sektor, existující karta fragmentu: uzly grafu i jejich stav Desktop v3). `placed` plán znovu sestaví, a když se otisk nebo `scopeDigest` liší (kontejner plánu nebo fragmenty se mezitím změnily), vrátí 409 „plán se změnil, znovu `planned`“. Digest celého plátna ani revize celého stavu se neporovnávají, protože je mění i souběžné smyčky jiných disciplín (K12); otisk proto nenese `expectedRevision` položek `extend` a `placed` ji pod zámkem grafu doplní z aktuálního stavu. Jinak zapíše přes `apply_plan` s digestem aktuálního pohledu.

## 5. Paměť: poučení s vyhasínáním

Tabulka `brief_lessons(project_id, workspace_id, lesson_id, discipline, kind, text, weight, fragment_id, created_at, confirmed_at, by, actor)`.

- Vzniká jen branou `learned` (`weight = 1.0`). `op: "confirm-lesson" {lessonId, note}` posune `confirmed_at` na teď (agent i člověk); `op: "drop-lesson"` jen člověk.
- **Platná váha** `w = weight · 0.5^(dní od confirmed_at / 30)`. Poločas 30 dní, práh 0.2 (konstanty v jednom modulu).
- `GET /api/brief-vault/lessons?discipline` vrací poučení nad prahem seřazená podle `w`. `node-brief` karty ze Schránky nese nejvýš 5 živých poučení její disciplíny (sekce `brief.lessons`), `/next` nejvýš 3.
- Poučení pod prahem se nemažou, jen se nevrací (historie zůstává).

## 6. UI Schránky (jen zobrazení a ruční přepínání)

- Přepínač disciplín místo dvou stop: tři skupiny (Kreslení · Logika · Provoz), v nich jen zapnuté neurony s počty, vpravo „Nezařazené“. Poslední volba se pamatuje pro aplikaci.
- Strom: u fragmentu pruh 8 teček bran (zapnutá / další na řadě / vypnutá) s titulkem brány; „slepá ulička“ ztlumená.
- Detail fragmentu: seznam bran s payloadem a ručním přepínačem (stejné `op: gate`), predikční chyba u `verified`, poučení disciplíny.
- Přehled: pokrytí za disciplínu, průměrná predikční chyba za disciplínu.
- Nové zadání: volba disciplíny (seskupený výběr).

## 7. Celeris jako poskytovatel Jev (volitelné)

`celeris-1-decision` implementuje TypeSafe System One API (`/v1/systemone`); podle dokumentace stačí změnit adresu, model a klíč (https://docs.celeris.ai/decisions.md).

- `backend/integrations/typesafe_client.py` dostane poskytovatele: `typesafe` (`https://api.typesafe.ai/v1/systemone`, `jev-latest`) a `celeris` (`https://inference.celeris.ai/celeris-1-decision/v1/systemone`, `celeris-1-decision`). Volba v `opora.local.toml` (`[jev] provider = "celeris"`), výchozí `typesafe`. Klíč dál jen v `AppSettings`, nikdy v repu.
- **Kontrola brány** `POST /api/brief-vault/gate-check {fragmentId, gate}`: Jev dostane text fragmentu a payload brány a typovanou otázku `noul` „Splňuje payload podmínku brány?“; vrátí `{probability}` nebo `{probability: null}`, když Jev není nastavený. Je jen poradní, bránu nezapíná. Rozšiřuje výjimku pro Jev (CLAUDE.md, `backend/brain_opora/decision/README.md`): Jev smí běžet i na žádost agenta nebo člověka ve Schránce, pořád jen typované odpovědi.

## 8. Kusy

| Kus | Obsah | Závisí na |
|---|---|---|
| K2 | backend disciplíny, migrace track → discipline, `set-discipline`, `/disciplines` | – |
| K3 | backend brány, `op: gate`, `/next`, predikční chyba, poučení a vyhasínání | K2 |
| K4 | backend plán (`/plan`, brány `planned`/`placed`), smazání `vault-plan.ts` | K3 |
| K5 | frontend disciplíny, brány, poučení | K2–K4 (tvar API výše) |
| K6 | skill `opora-control-center`: recept cyklu pro agenta (`/next` → `gate` …) | K3, K4 |
| K7 | ukázka na Ample: jeden fragment projde 8 branami, vznikne oblast → sektor → uzly | K5 |
| K8 | Zrcadlo ([zrcadlo.md](zrcadlo.md)) | K3 |
| K9 | Celeris poskytovatel + `gate-check` (§7) | K3 |

Každý kus: subagent s tímto kontraktem, testy vedle modulů, kritik u změn dat, `uv run pytest backend tools`, `npm test`, `npm run build`, commit na `main`, nic se nepushuje. Živá data jen se zálohou.

## 9. Upřesnění po kritice (závazné, má přednost před §2–§7)

1. **Atomický zápis plánu.** `placed` = v jedné operaci pod `graph_lock_for(pid)`: ověření CAS fragmentu, zdrojových revizí plánu, `scopeDigest` kontejneru plánu (§4) a jednoznačnosti značek `briefGroup`/`briefDiscipline` v kontejneru, `apply_plan` a revize fragmentu s `placed`. Konflikt = 409 bez vedlejších účinků; existující duplicitní značka = 409.
2. **Neměnný plán.** `planned` uloží do payloadu `{planId, generator: 2, sourceRevisions: {fragmentId: revision}, scope, digest, scopeDigest, plan, hash}`; `hash` = sha256 kanonického JSON dávky (klíče seřazené, kolekce v pořadí generátoru, bez ID od backendu, bez časů a bez revize celého stavu u `extend`), `digest` je jen informace. `placed` aplikuje **právě uložený** plán, když se `sourceRevisions` a `scopeDigest` nezměnily; jinak 409 „plán se změnil, znovu `planned`“. Zápis brány (nová revize s jinými branami) do `sourceRevisions` nevstupuje: porovnává se **otisk vstupů** (bod 4), ne číslo revize. Vypnutí `placed` karty nemaže; opětovné zapnutí po vložení vyžaduje nové `planned`.
3. **Jedna zapisující cesta.** `POST /api/brief-vault/plan` je jen čtecí. Na plátno zapisuje Schránka jen brána `placed` (a dosavadní `/api/canvas-plan` z tlačítek UI); obě podléhají serverové kontrole schválení člověka v asistentovi i v `opora_write.py`.
4. **Otisk vstupů a zneplatnění.** Každá zapnutá brána ukládá `inputHash` = sha256(název + text + `effectiveDiscipline` fragmentu). Při čtení i zápisu platí jen brány se shodným otiskem; jinak se hlásí jako zneplatněné (`gatesStale: true`) a chovají se jako vypnuté. Tím `revise`, `split`, `promote`, `set-discipline` (i na předkovi) cyklus zneplatní bez přepisu historie. Změna payloadu zapnuté brány = vypnout a znovu zapnout (kaskáda dalších bran). Karty a poučení zůstávají jako výstupy původního cyklu.
5. **Migrace a NULL.** `NULL` v `discipline` = dědění; „nezařazený“ = bez disciplíny na celé cestě ke kořeni. Backfill z `track` se týká jen řádků s `track IS NOT NULL AND discipline IS NULL`; nový kód `track` nepíše (není v `COLUMNS`), takže záměrné `NULL` z `set-discipline` se nikdy nepřepíše. Staré snímky verzí dostanou prázdné `gates`; nové snímky nesou brány a poučení.
6. **Dva významy „vloženo“.** Odvozené `inserted` (existuje karta s `fragmentRef`) zůstává pro pokrytí; brána se proto jmenuje `placed`. `changedSinceInsert` porovnává otisk obsahu (název + text) uložený v `fragmentRef`, ne číslo revize, aby zápis brány nehlásil „zadání se změnilo“. Historické karty se na osm splněných bran nepřevádějí.
7. **Výběr v plánu.** Výběr se normalizuje (potomci vybraných předků se vyřadí). Každá karta bere disciplínu svého fragmentu (dítě s přepsanou disciplínou jde do sektoru své disciplíny) a `done` z `synthesized` fragmentu, na kterém cyklus běží; chybí-li, 409 s výčtem fragmentů.
8. **Fronta `/next`** je nezávazná, bez rezervace: dva agenti mohou dostat totéž, druhý dostane 409 a načte nový stav. Vrací jen živé fragmenty druhu `brief` s živými předky, platnou disciplínou a aspoň jednou nesplněnou (nebo zneplatněnou) branou; vylučuje `decided=no` a větve pokryté `placed` předka. Pořadí: číslo chybějící brány, hloubka, cesta `ord` od kořene, `fragmentId`. Odpověď nese i `blocked` (počet fragmentů čekajících na návrh nebo schválení).
9. **Čistě booleovský agent: návrh → potvrzení.** `op: "propose" {fragmentId, expectedRevision, gate, payload, note}` uloží návrh payloadu brány k aktuální revizi (agent se strukturovaným zápisem nebo člověk). `op: "gate"` s `value: true` **bez payloadu** použije poslední návrh této brány pro aktuální otisk vstupů; bez návrhu 400 „chybí návrh“. Návrh platí jen se shodným `inputHash` a jen když vznikl ve stejné nebo pozdější revizi než poslední vypnutí této brány (vypnutá brána = návrh byl zamítnut a znovu se nepoužije, ani když se vstupy nezměnily). `/next` vrací `{gate, needs: "proposal"|"confirm", proposal?}`. `value: false` je jen vypnutí brány; verdikt `no`/`other` je vždy obsah návrhu brány `decided`. Brány bez payloadu (`scoped`, `planned`, `placed`) návrh nepotřebují.
10. **Externí kontrola brány** (`gate-check`, §7) běží jen po výslovném povolení člověka pro projekt a poskytovatele (příznak v `AppSettings`, samotný klíč nestačí). Požadavek nese `expectedRevision` a kandidátní payload; odejde jen název, text (nejvýš 4000 znaků), brána a payload na pevný endpoint bez přesměrování. Odpověď uvádí poskytovatele a otisk vstupu. Bez povolení žádný síťový požadavek.
11. **Zrcadlo** ukládá výsledky append-only do vlastní tabulky událostí (viz zrcadlo.md), nikdy dodatečně do revize brány; volá se mimo transakci brány, idempotentně podle ID události.
12. **Poučení:** unikátní původ `(project, workspace, fragment, cyklus)`, kde cyklus = revize, na které vzniklo `synthesized`; vzniká v téže operaci jako `learned`. Potvrzení a vyřazení jsou append-only události v `brief_lesson_events` (aktér, čas serveru, poznámka); vyřazení jen člověk. `confirmed_at` začíná časem vzniku, váha se počítá od posledního potvrzení. Vypnutí `learned` poučení nemaže. Všechna čtení a zápisy jsou omezené projektem a workspace.

## 10. Teď nestavět

Automatické spouštění agentů na `/next`, vlastní hodnocení bran modelem bez žádosti, Obsidian nebo jiné druhé úložiště, hormony jako rozhodovací signál.

## 11. Autonomní výzkumná smyčka (rozhodnutí člověka 2026-10-15)

„Musí to být pro agenty, žádná klikačka, žádný input navíc. Vytvoř Schránku bezpečně pro výzkum, který bude oblast rozvíjet, dokud agenti nedojdou ke kvalitnímu výstupu ve všech oblastech od CX po DB.“

- **Žádné ovládání v UI.** Schránka v aplikaci cyklus jen zobrazuje (brány, autor návrhu a potvrzení, chyba předpovědi, poučení, fronta). Jediné lidské nastavení je jednorázové povolení kontroly bran Jev pro projekt (§9 bod 10). Agenti pracují přes `opora_cycle.py` (skill) a API.
- **Pískoviště.** Výzkum běží v samostatném lokálním projektu „Schránka – výzkum (pískoviště)“ (prázdná složka mimo repa, automatika map vypnutá), ne v Ample ani v Tajemstvi-opory. Výsledky se do skutečných projektů převádějí až rozhodnutím člověka.
- **Pojistka zápisu:** před každým `placed` backend uloží verzi plátna (štítek „před placed <fragment>“), takže každé vložení jde vrátit jedním krokem.
- **Role v jednom kole fragmentu:**
  1. *Výzkumník* (Claude, s webem) založí pod fragmentem `research` s verdiktem (`feasible | dead_end | unrealistic`) a důkazy `[{url, title, quote, accessedAt}]`; závěr povýší (`promote`) do nové revize fragmentu.
  2. *Navrhovatel* (Hermes) navrhne `weighed`, `synthesized`, `decided` (§9 bod 9).
  3. *Potvrzovatel* (Claude, jiná relace než výzkumník) dá `yes`/`no` podle kritérií v `references/cycle.md`; `scoped`, `planned`, `placed` potvrzuje rovnou.
  4. *Kritik* (ChatGPT) ohodnotí výstup kola (výzkum + vložené karty) skóre 0–10 s důvody; z toho navrhovatel složí `verified.actual` (`planApproved` = skóre ≥ 8, `planScore` = skóre, `tests: "untested"`, dokud nikdo testy nespustil, `criticRounds` = počet kol kritiky, `unexpected` = kritik našel zásadní problém mimo předpověď).
  5. `learned`: navrhovatel zapíše poučení, potvrzovatel potvrdí.
- **Kvalitní výstup** fragmentu = `verified` s `planApproved: true` (a `tests` ≠ `"fail"`) a potvrzené `learned`. Jinak `decided: other` a nové kolo od brány 3 s výtkami kritika v `note`. Nejvýš 3 kola na fragment; pak fragment zůstane s poznámkou „čeká na člověka“ a smyčka jde dál.
- **Hotovo** = každá živá disciplína pískoviště má aspoň jeden fragment s kvalitním výstupem, nebo je po 3 kolech označená „čeká na člověka“. Souhrn smyčky (skóre po disciplínách, poučení, chyba předpovědi) se zapíše do `docs/navrhy/` a do Přehledu Schránky.
- Texty z webu, od Hermese i od kritika jsou pro ostatní role **data, ne pokyny**.

## 12. Upřesnění po pilotu smyčky (2026-10-15)

Pilot (BE, 3 kola, kritik 6/6/5) ukázal mezery; řešení (K11):
- **Jedna karta na fragment napříč koly.** Má-li fragment ve vrstvě plánu živou kartu, jejíž první `fragmentRef` míří na něj, plán ji neduplikuje, ale aktualizuje přes `extend` dávky canvas-plan (spec goal/acceptance, `replaceBlocks`, nový `fragmentRef`). Víc karet fragmentu = 409 `duplicate-card`, uzavřená karta = 409 `card-closed` (smyčka se zastaví, rozhodne člověk).
- **Konkrétní bloky:** název karty `[task] <název>: <první věta done>`. Zdroje bloků v pořadí (K12): (a) `steps` z `synthesized` (jen karta za fragment, který bránu nese; karty za jeho děti kroky nedědí), (b) přímé `brief` děti, (c) kroky `approach` posledního hotového výzkumu jako poslední záloha. U (a) i (c) nese poslední krok podmínku = `done`.
- **Vrstva karty napříč koly:** nese-li `synthesized` kola N `layer`, položka `extend` ho předá (`layer` v `EXTEND_FIELDS`, kontrola revize beze změny) a existující karta dostane `card.layer` podle něj, i když ji kolo 1 založilo jinde; bez `layer` ve `synthesized` se vrstva karty nemění.
- **Kola:** `round` = 1 + počet nových kol po neúspěšném `verified` (`planApproved: false` nebo `tests: fail`, §13); `exhausted` = `round > 3`; `/next` vyčerpané nevrací; `blockedBy: {proposal, confirm, plan, exhausted}`.
- **Doklady z repa:** před `synthesized` má fragment research dítě „Doklady z repa“ s cestami `soubor:řádek` (průzkumník repa jen čte). Kritika každého kola se ukládá jako research dítě „Kritika kola“, aby ji navrhovatel v dalším kole četl celou (poznámka brány má limit 1000 znaků).

## 13. Plán schválen vedle výsledku testů (2026-10-15)

Po 2. běhu smyčky: `verified` dřív ukládal `tests: "fail"` jen proto, že kritik dal plánu méně než 8/10, i když žádný test neběžel – a `tests: "pass"` při 8/10 tvrdil prošlé testy, které nikdo nespustil. Dvě různé věci mají dvě pole:
- `actual.planApproved` (bool) + `actual.planScore` (0–10): kritik schválil plán kola (skóre ≥ 8 = schváleno). Řídí kvalitu výstupu i nová kola (§11, §12 Kola).
- `actual.tests`: `"pass"` / `"fail"` jen z doloženého běhu testů (agent-output, CI); `"untested"`, dokud testy neběžely. `"fail"` je vždy neúspěch, i při schváleném plánu.
- Zpětná kompatibilita: payload bez `planApproved` se čte jako `planApproved = (tests == "pass")`; starší fragmenty se nepřepisují.
- Zobrazení (jen čtení): u brány `verified` „plán schválen 8/10 · testy neběžely“ / „plán neschválen 6/10 · …“; Zrcadlo dostává `actual` beze změny tvaru navíc s oběma poli.

# Výslech srdce: pochopit, dohledat, vyslechnout, teprve pak plánovat

Stav: návrh k rozhodnutí (2026-10-30). Navazuje na `docs/navrhy/2026-10-30-vstupni-brana.md` a `docs/navrhy/2026-10-30-metriky-a-spoustece.md`.

Podklady:
- zadání člověka z 30. 10.: model nesmí brát prompt ani příklady jako dogma. Má pochopit, co stavíme, dohledat fakta a reálné použití, udělat syntézu a vyslechnout člověka. Teprve s jasnými podklady začne práci;
- provoz Ample 30. 10.: srdce plánovalo karty s 0–1 krokem a bez souborů, takže měřák dal všem XS nebo „?“. Plán stál na chudých podkladech;
- existující stavebnice: výzkum (`opora_heart.py research`, `research_desk.py`, citace ověřuje kód), duel (`opora_duel.py`), eskalace (`escalate`, otázky čte jen člověk v UI), vstupní brána (`intake_entries`, `intake_requirements`) a měřák karty (`card_gauge`).

## 1. Proč

Dnes srdce převezme větu člověka a rovnou z ní plánuje. Příklady v zadání pak bere jako úplný seznam. Když člověk napíše „potřebuju metriky A, B, C“, karta dostane přesně A, B, C, i když věc ke spolehlivému provozu a k tomu, aby na ni šlo navázat, potřebuje ještě D–G. To, co člověku nepřišlo na mysl, pak v plánu chybí a vyjde najevo až jako chyba v provozu.

Princip: **požadavek není dotaz k odpovězení, ale záměr k pochopení.** Práce vznikne, až má srdce jasno, a jasno se dá ověřit.

## 2. Kdy se výslech spustí

Výslech běží jen u nové práce, ne u každé věty. Determinismus rozhodne bez modelu.

| Podmínka | Výslech |
|---|---|
| stanovisko `duplicate`, `done`, `extends_in_progress` s jednoznačnou kartou | ne |
| nový požadavek (`--requirement new`) pro `fix_for_milestone` nebo otevíraný `later_extension` | **ano** |
| `changes_intent` | **ano**, zaměřený na dopady |
| karta k předání má měřák `evidence: thin` (štítek „?“) | **ano**, krátký (doplnit kroky a soubory) |
| člověk ve Velínu klikne „Vyslechni mě k tomu“ | **ano** |

## 3. Pět kroků (každý se zapíše, nic jen „v hlavě“ modelu)

1. **Situace** (determinismus, bez modelu). Složí se spis požadavku:
   - věta člověka doslova a podobné vstupy;
   - ZÁMĚR projektu;
   - oblast, milník a jeho kritéria;
   - související karty s měřákem;
   - rozhodnutí a pravidla projektu.
2. **Rešerše** (stávající `research`). Hledá, jak se taková věc staví a provozuje v reálném použití: zdroje z webu a kódu, citace ověřené kódem. Hlavní otázka: *co tahle věc potřebuje, aby spolehlivě fungovala a mohly na ni navázat další?* Platí strop ceny na požadavek.
3. **Syntéza** (srdce s poradcem Opus, jedno volání). Výsledkem je „návrh pochopení“:
   - cíl jednou větou a pro koho;
   - **úplný seznam částí nebo metrik**. U každé položky je původ: `člověk`, `rešerše` (odkaz na zdroj), nebo `odvozeno` (z čeho). Příklady člověka jsou vzorky záměru, ne hranice seznamu;
   - předpoklady, hranice (co ne) a rizika;
   - kritéria přijetí, měřitelná;
   - otázky seřazené podle dopadu na plán.
4. **Výslech** (otázky člověku v UI, ne v chatu).
   - Nejvýš 3 otázky najednou. Každá nese **doporučenou odpověď srdce a důvod**, takže člověk může jen potvrdit.
   - Odpověď člověka se uloží jako vstup brány a srdce podle ní upraví syntézu.
   - Opakuje se, dokud nejsou splněna kritéria jasna (§4), nejvýš 3 kola. Pak srdce rozhodne samo a nejasnosti zapíše jako předpoklady.
5. **Jasno → plán.** Teprve teď srdce plánuje karty. Každá má 2–8 kroků s `kind` a `files`, takže měřák má z čeho měřit a štítek není „?“. Spis i syntéza zůstanou u požadavku a karty na ně odkazují.

## 4. Kritéria jasna (kontroluje kód, ne model)

Požadavek je `clear`, když syntéza obsahuje všechno z tohoto seznamu:
- cíl a uživatele;
- aspoň 3 kritéria přijetí, každé ověřitelné (test, měření nebo pozorování);
- hranice „co ne“;
- seznam částí s původem, přičemž aspoň jedna položka pochází z rešerše nebo je odvozená. Jinak jde jen o přepis zadání;
- závislosti na jiných kartách nebo oblastech;
- žádnou otevřenou otázku s vysokým dopadem.

## 5. Režim jako skill (nahraný na vyžádání, ne v základním promptu)

- Postup výslechu je v `backend/brain_opora/heart/skills/vyslech.md`. Srdce ho čte jen ve chvíli, kdy dávka obsahuje spouštěč výslechu. Základní prompt nebobtná, tedy žádné tokeny navíc v běžných dávkách.
- Skill říká, jak se na věc dívat:
  - nejdřív účel a reálné použití, pak seznam;
  - na příklady člověka se ptá: „čeho jsou to příklady?“;
  - hledá, co věc potřebuje pro spolehlivost, pozorovatelnost a navázání dalších;
  - vede rozhovor: jedna věc po druhé, vždy s doporučením;
  - nepřetahuje se o zadání, nenafukuje rozsah a nevymýšlí funkce navíc, které účel nevyžaduje.
- Inspirací je stávající skill `grilling`. Ten ale vyslýchá do vyčerpání, kdežto tady je strop 3 kol a doporučená odpověď u každé otázky.

## 6. Úložiště (aditivní, `project.sqlite`)

- `intake_briefs(requirement_id, workspace_id, status draft|research|grilling|clear, situation JSON, research JSON [{digest, sources}], synthesis JSON, questions JSON [{id, text, recommended, why, answer, answered_at}], rounds, cost_usd, updated_at)`. Nová tabulka, žádná existující se nemění.
- Odpovědi člověka jdou do `intake_entries` se zdrojem `brief_answer` a navázaným `requirement_id`, takže se v nich dá hledat jako ve všech vstupech.

## 7. Rozhraní

- `opora_heart.py brief --requirement rq_… --synthesis @soubor.json` uloží syntézu. Kód ověří kritéria jasna a vrátí, co chybí.
- `opora_heart.py ask --requirement rq_… --question "…" --recommended "…" --why "…"` položí otázku výslechu (nejvýš 3 otevřené).
- `GET /api/intake` nese u požadavku `brief: {status, questions, missing}`.
- `POST /api/intake/brief/answer {requirement, question, answer|accept}` smí jen člověk. „Potvrdit doporučení“ je jedno kliknutí.
- Velín, pohled „Požadavky a plán“: u požadavku ve výslechu se ukáže syntéza (cíl, seznam částí s původem, kritéria) a otázky s doporučením a tlačítky „Potvrdit“ / „Odpovědět jinak“.

## 8. Cena a stropy

- Výslech běží jen podle §2.
- Rešerše má strop 0,30 USD na požadavek, syntéza je jedno volání s poradcem. Celkem do zhruba 0,50 USD na nový požadavek. V nastavení projektu lze strop změnit nebo výslech vypnout (`brain.brief`).
- Bez výslechu pipeline funguje jako dnes.

## 9. Co se nemění

- Srdce zůstává jediný zapisovatel plátna. Lidská brána, zeď a brána uzavření karty se nemění.
- Otázky čte a odpovídá na ně jen člověk v UI.

## 10. Řezy

1. **Spis a kritéria jasna:** `intake_briefs`, determinismus spisu, `brief` a `ask` u srdce, kontrola kritérií, spouštěč výslechu podle §2.

   Odchylky řezu 1 (implementace `backend/brain_opora/determinism/brief.py`):
   - Tabulka `intake_briefs` je v `database/schema/intake_schema.py` vedle ostatních tabulek brány (do `PROJECT_SCHEMA` ji přidá `project_schema.py`). Žádná existující tabulka se nemění.
   - Hodnoty syntézy jsou anglické klíče: `origin` = `human` | `research` | `derived` (člověk, rešerše, odvozeno; `research` a `derived` potřebují `source`), kritérium `check` = `test` | `measure` | `observe`, otázka `impact` = `high` | `medium` | `low`. Tvar vrací chyba `brief` v `hint`.
   - Závislosti (§4) musí mít aspoň jednu položku. Když žádná není, srdce to napíše jako `{"ref": "none", "text": "proč"}`.
   - Jasnu brání i otázka výslechu (`ask`), na kterou člověk ještě neodpověděl (`missing`: „otázky výslechu čekají…“). Stav je pak `grilling`.
   - `ask` vyžaduje uloženou syntézu (409 `brief_missing`). Čtvrtá otevřená otázka dostane 409 `brief_questions_full`, čtvrté kolo 409 `brief_rounds_spent`. Kolo začíná otázkou položenou ve chvíli, kdy žádná otevřená není.
   - Spouštěč požadavku běží jen se vstupem z posledních 24 h, aby se po nasazení nevyslýchaly staré požadavky. Klíč je `trigger:brief:<rq>:<new|opened|changes_intent>`. `changes_intent` budí i po `clear` (spis se vrátí do `draft`), ale jen u vstupu navázaného na požadavek, protože spis patří k požadavku.
   - „Otevíraný `later_extension`“ = požadavek `open`, jehož zakládající vstup je `later_extension`. Mechanismus, který odložený požadavek otevře, zatím neexistuje.
   - Krátký výslech karty (`ready` + `evidence: thin`) běží přes `triggers.wakes(extra=brief.card_hit)`, jednou na kartu a prostor (`trigger:brief:card:<uzel>:thin@<prostor>`), nejvýš 5 na průchod.
   - Spis (§3.1) se uloží při probuzení (`draft`) a obnoví při každém `brief`. Srdce ho dostane zhuštěný v řádku `VÝSLECH: rq_… „název“ (důvod) · spis: …`, bez nového příkazu `ctx`.
   - Odpovědi `brief` / `ask` nesou navíc `requirement` (u `ask` i `question`, `open`, `rounds`). Nastavení `brain.brief` (§8) patří do řezu 2.
   - Otevřená otázka pro řez 3: odpověď člověka jako vstup se zdrojem `brief_answer` (§6) narazí na CHECK sloupce `intake_entries.source`. Ten by se musel přestavět, což je změna existující tabulky.
2. **Skill výslechu a rešerše:** `skills/vyslech.md`, napojení `research` se stropem, poznámka v promptu, že skill se čte jen při výslechu.

   Odchylky řezu 2:
   - Skill čte srdce příkazem `python opora_heart.py skill vyslech` (Bash nástroje je povolený, Read by potřeboval absolutní cestu). `command.write_config` kopíruje `heart/skills/*.md` do `brain/skills/` vedle nástroje. Základní prompt má jeden řádek odkazu. Neznámý skill vrátí `skill_missing` s hintem „postupuj podle části promptu“.
   - Strop rešerše hlídá nová routa `POST /api/brain/heart/brief/research` (jen token srdce svého prostoru). Bez `costUsd` jen zkontroluje strop, s `costUsd` (a volitelně `fragmentId`, `digest`, `sources`) cenu přičte do `intake_briefs.cost_usd` a záznam do sloupce `research` (`[{fragmentId, digest, sources, costUsd, at}]`). Spis bez syntézy přejde do stavu `research`. Schéma tabulky se nemění.
   - Cena rešerše je `stats.costUsd` výzkumného stolu (součet `total_cost_usd` pod-volání `claude`, výzkumník + destilace). Strop se kontroluje **před** spuštěním stolu, takže jedna rešerše ho může přečerpat nejvýš o svou cenu. Stůl za běhu cenou nehlídá.
   - Spis patří prostoru tokenu srdce (`OPORA_WORKSPACE`), ne prostoru schránky. `research` v `main` dál zapisuje do prostoru posledního plánu, cena jde ke spisu v `main`. Když přičtení ceny selže, hotová rešerše se neztratí a chyba je ve výtahu v `brief`.
   - Nastavení `brain.brief = {enabled, researchUsd}` je v `determinism/brief_setting.py`, routa `GET|POST /api/brain/brief-setting`. Zápis je za `require_authority`, takže smí i agent při plné autonomii, na rozdíl od `intake-setting` (`require_human`). `researchUsd` je 0–5 USD. Vypnuto: `needs_brief(..., enabled=False)` vrací `None`, `brief_wakes` nic a tenké karty nebudí (`card_wakes` bez `extra`). Probíhající spis se nemaže a `brief`/`ask` fungují dál.
   - Strop syntézy („jedno volání s poradcem“) kód nehlídá. Řídí ho skill.
   - Nová routa a kopie skillu začnou platit až po restartu serveru 8740. Do té doby `skill vyslech` vrátí `skill_missing` a srdce jede podle části Výslech v promptu.
3. **Velín:** syntéza a otázky s doporučením, odpověď člověka.

   Odchylky řezu 3:
   - Odpověď člověka se **neukládá do `intake_entries`** (§6 a otevřená otázka řezu 1): CHECK sloupce `source` by
     vyžadoval přestavbu tabulky. Odpověď je jen v `intake_briefs.questions[]`: `answer`, `answered_at` a navíc
     `accepted` (true = potvrzené doporučení). Schéma tabulek se nemění.
   - `POST /api/intake/brief/answer {project, workspace, requirement, question, answer | accept: true}` (logika
     `brief.answer`): právě jedno z `answer` (text do 500 znaků) a `accept: true` (vezme `recommended`). Odpovědět jde
     jen na otevřenou otázku (404 `brief_question_not_found`, 409 `brief_question_answered`, bez spisu 404
     `brief_not_found`). Smí jen člověk (`require_human`), i při plné autonomii: jinak by si srdce na své otázky odpovídalo
     samo (§9 platí beze změny). Spustit výslech („Vyslechni mě k tomu“) smí i agent při plné autonomii.
   - Odpověď stav `clear` nenastaví ani po poslední otázce: stav zůstane `grilling`, dokud srdce syntézu neuloží znovu
     (`brief`). Jasno dál potvrzuje jen `save_synthesis`.
   - Řádek §2 „Vyslechni mě k tomu“: `needs_brief(..., asked=True)` → `asked` u požadavku `open` i `deferred`.
     `POST /api/intake/brief/start {project, workspace, requirement}` (`brief.start`, stejné oprávnění, 201) založí
     spis `draft` se spisem situace a značkou `situation.askedAt`. Existující spis 409 `brief_exists` (tlačítko je jen
     u požadavku bez spisu), vypnutý výslech 409 `brief_disabled`, vyřízený požadavek 409 `brief_requirement_closed`.
     Okno 24 h spouštěče se na žádost člověka nevztahuje.
   - Probuzení: `brief.human_wakes` / `fire_human` v `heart/inputs.brief_wakes` (supervisor ho volá při každém
     průchodu outboxu). Jednou na odpověď (`trigger:brief:<rq>:answer:<q>`) a jednou na žádost
     (`trigger:brief:<rq>:asked`), i s vypnutým `brain.brief`, protože jde o přímou akci člověka. Srdce v dávce vidí
     `VÝSLECH: rq_… „název“ (odpověď člověka na výslech, uprav syntézu (brief), …) · spis: otázka q1 „…“ → člověk
     potvrdil doporučení „…“` (nebo „odpověděl „…“ (doporučení bylo „…“)“). Text za `· spis:` je u odpovědi otázka
     a odpověď. Řádek dávky (`heart/batch.py`) se nemění.
   - `GET /api/intake` nese u požadavku navíc `brief.synthesis`, aby Velín ukázal cíl, části s původem, kritéria
     a hranice.
   - Velín: dílek `frontend/editor/control-tower/intake-plan/brief-panel/` pod každým otevřeným, odloženým i
     nezařazeným požadavkem. Původ části se ukazuje jako „od vás“ / „z rešerše“ / „odvozeno“ se zdrojem, chybějící
     věci česky bez technických klíčů, ID jen v `data-oh-*`.
   - Nové routy začnou platit až po restartu serveru 8740.
4. **Ověření na Ample:** požadavek „chci metriky X, Y, Z“. Syntéza musí obsahovat i položky s původem `rešerše`/`odvozeno`, výslech nejvýš 3 kola a karty pak mají štítek jiný než „?“.

### Doplnění kroků existující karty

Krátký výslech karty (`VÝSLECH (krátký): karta …`) má doplnit kroky kartě, která už existuje. `plan` zakládá jen nové uzly a `member` mění jen `memberOf`, proto srdce dostalo příkaz `python opora_heart.py steps --node ID --file F [--dry-run]`.
- Cesta je existující návrh změny zadání: `POST /api/oporahub/changesets` s úplnými `fields` pracovního zadání karty a novými `steps` (volitelně `goal` a `acceptance`), viz `docs/oporahub-plan-steps.md`. Přijetí je akce `accept` z agent-state (`/api/oporahub/changesets/{id}/accept`). Při `autonomy.full` ji srdce provede samo stejně jako u `member`, jinak návrh čeká na člověka v OporaHubu.
- `heart_scope` se nerozšiřuje. Hlídá jen návrhy grafu (`graph-proposals`); zadání karty jde jinou routou, kterou smí navrhovat každý agent a přijímá ji `require_authority`.
- Tvar kroku ověřuje server (`validate_steps`). Pravidlo realizační karty, které server nemá (2–8 kroků, každý s `kind` a neprázdnými `files`), kontroluje příkaz. Chybějící `id`, `order` a `dependsOn` doplní lineárně (s1 → s2 → …).
- Karta musí mít přijaté zadání (`steps_not_accepted`), protože návrh zadání se vztahuje k přijaté revizi. Kroky nové karty patří dál do `plan`.

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
3. **Velín:** syntéza a otázky s doporučením, odpověď člověka.
4. **Ověření na Ample:** požadavek „chci metriky X, Y, Z“. Syntéza musí obsahovat i položky s původem `rešerše`/`odvozeno`, výslech nejvýš 3 kola a karty pak mají štítek jiný než „?“.

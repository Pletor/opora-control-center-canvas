# Sprinty, úsporný dělník a správná cena srdce

**Stav: platí jen §1 (#221). §2–§4 (#222, #223) vráceny 2026-10-31 po evalu m11** (kvalita 0,93 → 0,82:
srdce postupy ze skillů nenačítalo a dostávalo horší informace). Nový pokus až po rozboru, co srdce a dělník
skutečně dostávají.

Původně schváleno člověkem 2026-10-31 („Oporu upgraduj“). Podklad: eval Zelený balkon m10 proti terminálu
(`.claude/hillclimb/opora-vs-bare/multi`): stejné množství kódu, ale dělník 60 kol místo 16, 10× víc čteného
kontextu, `npm run build` + `npm test` po každém úkolu; srdce plánuje celou frontu, než dělník začne; cena
srdce v navázané relaci se sčítá kumulativně; slepé hodnocení kódu B 7,4 / C 6,1 / E 5,7 (E: chybí S5,
zbytek ceníku `varianta`).

Bez změny schématu tabulek (sprint žije v JSON těle úkolu), bez zásahu do brány uzavření karty a do dat
v `P:\opora-data`.

## 1. Správná cena dávky srdce

`claude -p --resume` vrací v `total_cost_usd` a `modelUsage[*].costUSD` **součet celé relace**, ne dávky.
`batch.run` proto u navázané relace (`resumed`) zapíše:

- `costUsd`, `costByModel` = rozdíl proti poslednímu záznamu deníku se stejným `sessionId` (nezáporný,
  zaokrouhlený na 6 míst; model, který v předchozím záznamu nebyl, se bere celý);
- `sessionCostUsd`, `sessionCostByModel` = surové kumulativní hodnoty výsledku.

Nová relace má obě dvojice stejné. `advisor_spent` sčítá dávkové `costByModel` (už správně). Starší záznamy
bez `sessionCostUsd` se při výpočtu rozdílu berou jako kumulativní (stejný zdroj). Test: dvě navázané dávky
s rostoucí kumulativní cenou → druhá dávka nese jen přírůstek; strop poradce počítá přírůstky.

## 2. Sprinty ve frontě úkolů brány

Úkol nese volitelné `body.sprint = {id, goal, milestone[]}`:

- `id`: krátký text (`S1`, `zaklad`…), `goal`: věta, co sprint dodá; `milestone`: ověřitelné body milníku
  (`npm run build projde`, `npm test projde`, `cesta / → /kurz → /kontakt → /dekujeme funguje`).
  `goal` a `milestone` stačí uvést u jednoho úkolu sprintu; platí pro celý sprint.
- Pořadí uvnitř sprintu i mezi sprinty dál řídí `order` (+ pořadí vzniku).
- **Kontrolní bod sprintu** (`task.checkpoint: true` v odpovědi `next`) je úkol sprintu, za kterým ve frontě
  už žádný otevřený (`ready`/`assigned`) úkol téhož sprintu není. Odvozuje se při `next`, nic se neukládá.
  Úkol bez `sprint` je vlastní sprint, tedy vždy kontrolní bod (dnešní chování).
- `next` k úkolu přidá `sprint: {id, goal, milestone, done, total}` (počty úkolů sprintu).
- **Hlášení:** kontrola smí mít stav `deferred` („ověří kontrolní bod sprintu“). Úkol, který není kontrolním
  bodem, smí hlásit jen `deferred` kontroly a je pak `done`. Kontrolní bod musí hlásit skutečné kontroly
  (`green`/`red`); `deferred` u kontrolního bodu → 422 `checkpoint_needs_checks`. Červený kontrolní bod se
  vrací do fronty jako dnes (`MAX_ATTEMPTS`).
- CLI srdce: `opora_heart.py task … --sprint ID [--sprint-goal TEXT] [--milestone TEXT]…`.
- Snímek srdce má sekci `SPRINTY:` (nejvýš 6 posledních): `id – goal – hotovo d/t – kontrolní bod:
  čeká | zelený | červený (důvod)`.

**Srdce zadává po sprintech, první úkol hned.** Úkol je pro dělníka viditelný okamžitě po zápisu (už dnes).
Srdce proto po vyjasnění nejdřív zapíše první úkol prvního sprintu a teprve pak plánuje zbytek; dělník
mezitím pracuje. Velikost: sprint = ucelený kus, který jde ověřit milníkem (obvykle 1–4 úkoly); drobnosti
patří do jednoho úkolu, ne do šesti.

## 3. Cache a cílené dohledávání

- **Snímek srdce**: stálé sekce napřed (PROJEKT, ZÁMĚR, pravidla, DORUČENÍ, PLÁN), proměnlivé na konec
  (FRONTA, SPRINTY, lístky, kontroly, GIT, deník dávek). Obsah sekcí se nemění, jen pořadí; stálý začátek se
  pak drží v cache i v nové relaci.
- **Dělník** nečte repozitář znovu u každého úkolu: drží si, co už přečetl, čte jen `files` úkolu a co
  potřebuje dohledá cíleně (`Grep`/`Glob`, výřez souboru), ne celé soubory pořád dokola. Patří do skillu
  dělníka (§4).

## 4. Skill na roli

Každá role dostane vlastní postup, aby věděla, co dělat, a neztrácela kola:

- **Dělník brány**: `.claude/skills/opora-gate-worker/SKILL.md` (smyčka `next` → práce → commit → `report`;
  `deferred` kontroly mimo kontrolní bod; na kontrolním bodu `npm run build` a `npm test` jednou, každý
  bod milníku ověřit; cílené čtení; dotaz `ask` jen u skutečného rozporu). `references/gate.md` skillu
  `opora-control-center` na něj odkazuje.
- **Srdce**: postupy v `backend/brain_opora/heart/skills/` (čtené přes `opora_heart.py skill NAME`, jako
  `vyslech.md`):
  - `sprinty.md`: jak rozdělit záměr na sprinty a milníky, první úkol hned, velikost úkolu;
  - `zruseni.md`: zrušení / přejmenování věci = jeden úkol se všemi výskyty (`grep` v `src/` i testech,
    včetně polí formuláře a textů jako FAQ), `doneWhen` „hledání v `src/` nic nenajde“;
  - `chybi-podklad.md`: vstup stojí na neexistujícím API či datech → postav nejmenší poctivou variantu
    (volání s ošetřenou chybou a prázdným stavem, nebo viditelně označená dočasná data) a rozpor ohlas;
    neptej se na detaily, které jdou ověřit v repu.
  - `prompt.md` jen řekne, kdy který postup načíst (jedna řádka na postup).

## 5. Eval (mimo produkční kód, `.claude/hillclimb/...`)

Harness rameno E: dělník dostane skill dělníka místo vlastního dlouhého promptu a startuje, jakmile je
ve frontě první úkol (ne až po klidu srdce); srdce a dělník běží souběžně. Cena srdce z nových polí §1.
Nový běh `m11 --arms E`, porovnání s m7 B/C a m10 E: kvalita, cena, čas, kola, slepé hodnocení kódu.

## Řezy (každý = malé PR z čerstvého `main`)

1. Cena (§1): `backend/brain_opora/heart/batch.py` + test.
2. Sprinty (§2): `determinism/task_payloads.py`, `task_queue.py`, `heart/opora_heart.py` (CLI),
   `determinism/snapshot.py` (sekce SPRINTY + pořadí §3), `heart/prompt.md` (odkazy na postupy),
   `docs/brain-heart.md`, testy vedle modulů.
3. Skilly (§4): `.claude/skills/opora-gate-worker/`, `heart/skills/{sprinty,zruseni,chybi-podklad}.md`,
   `references/gate.md`, klient `opora_gate.py` (stav `deferred` v `--check`).
4. Eval (§5) a úklid testů bez účinku nalezených cestou.

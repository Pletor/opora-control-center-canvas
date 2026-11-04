# Plátno 2 jako nástroj na procesy: od kliknutí ve FE přes BE a DB zpátky

**Zadání:** schválení K1–K3 a M2 z 2026-11-04 a výslech člověka (Q1–Q15). Navazuje na `2026-11-04-knihovna-platna-toku.md`, jehož model (knihovna, rodokmen, verze, graf s rámci a skupinami) se nemění.

**Důvod:** plátno toků dnes umí hlavně AI/RAG (33 typů uzlů podle n8n). Člověk potřebuje popsat jakýkoli proces: kliknutí na tlačítko → data na server → kontrola → funkce → zápis do DB → zpráva zpátky → notifikace ve FE. Tak, aby šlo vidět, co kudy letí, a aby z toho šlo zadat práci agentovi. Těžké je rozhodnout, kdy co použít.

**Hotovo, když** (ukázkový případ „Uložit BMI“):
1. Na plátně je proces: formulář (výška, váha) → tlačítko → BE endpoint → funkce kontroly vstupu → funkce výpočtu BMI → zápis do DB → potvrzení → FE notifikace. Každá vrstva má svou barvu.
2. Kliknutím na hranu vidím, jaká data po ní letí.
3. Dvojklik na funkci otevře její vnitřek (pořadí, podmínky, větve).
4. Play přehraje případ „v pořádku“ (výška 180, váha 80 → BMI 24,7 → řádek v DB → notifikace) a případ „neplatná výška“ (chyba validace → chybová notifikace) jako animaci s daty u každého kroku.
5. V okně LLM popíšu situaci, LLM se doptá a nakreslí kroky do draftu. Vyberu jeden uzel, napíšu požadavek a LLM upraví jen ten uzel.
6. Z případu vznikne zadání karty pro agenta, které odkazuje zpět na plátno.

## 0. Milníky (stavět jen milník, po kontrole člověkem jít dál)

- **P1 Vrstvy:** barvy, kontejnery, nové kroky FE/BE/DB/Infra, „kdy použít“, průvodce výběrem.
- **P1b Příkazový řádek a krok na míru:** zadání textem na plátně, LLM kreslí do draftu, obecný krok `custom.step`, „co dál?“ u portu (viz §1b). Stavba před P2 na přání člověka (méně klikání).
- **P2 Data na hraně:** data na hraně, druhy dat, vnitřek funkce.
- **P3 Play:** případy, simulované prostředí, výpočet, animace.
- **P4 LLM:** kreslení z rozhovoru, požadavek k jednomu bodu, skill „proces na plátně“.
- **P5 Případ → zadání karty:** generování zadání s odkazem zpět na plátno.

Dopředu se nestaví nic: P2 nezačne před schválením P1 atd. Eval srdce se kvůli P4 nespouští při stavbě, prompt srdce se nemění (jen nový skill a nástroj).

## 1. Vrstvy a katalog (P1)

**Vrstva** je vlastnost uzlu: `layer = fe | be | db | infra | ai | neutral`. Typ uzlu má výchozí vrstvu, uzel ji může změnit (výpočet může běžet ve FE i v BE). Vrstva určuje barvu a pruh.

| Vrstva | Barva | Kroky (nový typ) |
|---|---|---|
| FE | zelená | `fe.click` tlačítko, `fe.form` formulář a vstup, `fe.navigate` změna stránky, `fe.state` stav, `fe.show` zobrazení, `fe.notify` notifikace |
| BE | růžová | `be.endpoint` (metoda, cesta, tělo, odpověď), `be.validate` (podmínky, větve true/false), `be.function` (logika, vnitřek v detailu), `be.middleware`, `be.auth` |
| DB | modrá | `db.read`, `db.write`, `db.transaction` (tabulka, sloupce, podmínka) |
| Infra | žlutá | `infra.api` vnější služba, `infra.cache`, `infra.queue`, `infra.storage`, `infra.email` |
| AI | fialová | dnešní `ai.*` beze změny |
| Neutrální | šedá | `trigger.*`, `transform.*`, `flow.*`, `human.approval` |

- **Čistá cesta:** `action.http`, `action.db`, `action.file` se nahrazují `infra.api`, `db.read`/`db.write` a `infra.storage`. Existující grafy se přepíšou migrací, nic se nezachovává dvakrát. Knihovna je dnes prakticky prázdná (demo plátna).
- **Pruhy:** plátno kreslí uzly v kontejnerech podle vrstvy (zelený, růžový, modrý, žlutý pruh). Pruh je jen zobrazení, v grafu zůstává jen `layer` uzlu. Bez uzlů vrstvy se pruh nekreslí.
- **Hrana mezi vrstvami** má `via` s popiskem (`http`, `sql`, `event`, `call`, `render`). Kontrola grafu zná povolené dvojice (FE → BE jen `http`/`event`, BE → DB jen `sql`/`call` atd.).
- **Kdy použít:** typ uzlu nese `use` („použij, když…“) a `avoid` („nepoužívej, když…“). `GET /api/flow/node-types` je vrací a paleta je zobrazí v tooltipu a u karty uzlu.
- **Průvodce „Co chci udělat?“:** dialog v paletě. Člověk vybere záměr (přijmout vstup, ověřit, spočítat, uložit, zavolat službu, zobrazit výsledek, rozhodnout, opakovat), průvodce nabídne typy podle štítků `intents` na typu. Bez modelu, deterministicky. Stejný katalog čte LLM okno.

## 1b. Příkazový řádek a krok na míru (P1b)

Důvod: člověk se v paletě ztrácí a hodně klikne. Chce napsat zadání a nechat LLM vytvořit komponentu na míru, i když v knihovně není.

- **Příkazový řádek** na plátně knihovny (klávesa `/` nebo `Ctrl+K`, a tlačítko v toolbaru): textové pole se zadáním, např. „po kontrole přidej výpočet BMI a ulož ho do tabulky měření“. Odeslání jde jako zpráva člověka srdci (`POST /api/brain/heart/messages`) s novým volitelným `context: {kind: "flow", flowId, versionId, nodeIds[]}` (vybrané uzly, jinak celé plátno). Backend `context` ověří (plátno existuje, uzly patří do verze) a srdce ho čte jako **data**, ne příkaz. Změna je v kontraktu kanálu (`docs/brain-heart-channel.md` §2) a ve validaci `_scope`; prompt srdce se nemění.
- **Kreslí rovnou:** srdce přes nástroje `opora_heart.py library nodes add|set|connect` zapisuje **draft** plátna (v části člověka jen draft, přijetí jedním klikem, jako v K3). Nový uzel dostane pozici automaticky: x za posledním uzlem řetězce, y podle pruhu své vrstvy. Dotaz zpět přijde jen tehdy, když zadání nestačí (otázka v kanálu srdce, ne dialog na plátně).
- **Stav:** lišta „Srdce kreslí…“ s tlačítkem Zrušit a odpočtem; po zápisu se objeví pás návrhu (`ProposalBar`) s rozdílem a tlačítky Přijmout / Zamítnout. Srdce je pomalejší než klik (desítky vteřin), proto je stav vidět.
- **Krok na míru `custom.step`:** obecný typ s porty `main` in/out (volitelné pojmenované výstupy z `params.branches`), povinnými `layer`, `params.title` a `params.description`, volitelnými `params.rule` (výraz pro simulaci v P3), `inputSchema`, `outputSchema`, `example`. Kontrola grafu vyžaduje vrstvu a titulek, schémata ověří stejně jako u ostatních uzlů. Žije jen na plátně, katalog se nemění. Karta ukazuje titulek a štítek vrstvy.
- **Skill „proces-na-platne“** (seed Brainu): srdce z textu odvodí vrstvy, kroky, data a větve, použije typy z katalogu a `custom.step` jen tam, kde žádný typ nesedí. Doptá se, když nezná začátek, konec nebo vstup/výstup.
- **„Co dál?“ u portu:** upuštění tažené hrany do prázdna otevře paletu zúženou na typy povolené pravidly vrstev a `via` (deterministicky, bez modelu).
- **Mimo P1b (později):** „Uložit jako krok do knihovny“, tj. povýšení `custom.step` na znovupoužitelný typ v katalogu člověka nebo agenta (vlastní úložiště typů). Doplní se, až se ukáže, které kroky se opakují.

## 2. Data na hraně a detail funkce (P2)

Dnešní stav: `FlowEdge` má jen volitelný `label` (v UI se plní jen z běhu srdce), `example` a schémata uzlu se editují v inspektoru, ale na plátně se nekreslí, a knihovna nepředává ani běhy.

- **Hrana** nese `data`: `{kind, schema?, example?}`. `kind`: `text | number | json | table | document | vector | file | event`. Každý druh má barvu čáry a ikonu. Kliknutí na hranu otevře panel „Co tu letí“ se schématem a příkladem. Příklad se dědí z `outputSchema/example` zdrojového uzlu, když hrana nemá vlastní.
- **Kontrola kompatibility** (rozšíření `connection-policy`): `kind` výstupu musí odpovídat vstupu cílového uzlu, jinak chyba při tažení (stejně jako dnes u typů portů).
- **Detail funkce:** dvojklik na `be.function` (a na `fe.state` a `transform.code`) otevře jeho vnitřek jako vnořené plátno. Technicky je to skupina z K1 (`groups[]`, souvislý řetězec, vstup do prvního a výstup z posledního uzlu), která už se umí sbalit. Nově: skupina se může jmenovat podle funkce, nese `inputSchema/outputSchema` a zobrazí se jako jeden blok. Vnořené plátno má vlastní play a případy.

## 3. Případ (P3)

Případ je pojmenovaná cesta plátnem s ukázkovými daty. Plátno má pole `cases[]`:

```
{ id, name, description, start: nodeId,
  input: { …data na startu… },
  env: { tables: { <tabulka>: [řádky] }, services: { <nodeId>: odpověď | chyba } },
  expect: { result?, path?: [nodeId…], rows?: {…}, notify?: text } }
```

- Jedno plátno má víc případů (v pořádku, chyba validace, výpadek DB). Případ vybírá lišta nad plátnem.
- `env` simuluje DB a vnější služby. Nic se nespouští doopravdy: žádná síť, žádný soubor, žádný SQL na reálné DB.
- `expect` je zároveň test: výsledek simulace se porovná s očekávaným a plátno ukáže zelenou nebo červenou značku případu.

## 4. Play a simulace (P3)

- **Simulátor** je jeden čistý modul v backendu (`backend/flow/simulate.py`) a `POST /api/flow/simulate {flowId|graph, caseId|case}` vrací trasu: `[{nodeId, edgeId?, layer, in, out, branch?, note, error?}]`. Frontend trasu jen přehrává (jediný zdroj výpočtu, stejný pro člověka, LLM a testy).
- **Pravidla kroků** jsou výrazy v malém bezpečném jazyku: čtení `$json.pole`, aritmetika, porovnání, `and/or/not`, podmínka `a if p else b`, funkce `round, min, max, len, abs, number, text, lower, upper, contains`. Bez volání jiných funkcí, bez atributů, bez smyček. Implementace je whitelist nad `ast` (jiný uzel než povolený = chyba), s limitem délky výrazu a počtu kroků trasy (shortcut: 200 kroků, smyčky `flow.loop` jen nad daty případu).
- **Typy v simulaci:** `fe.*` předají data dál (`fe.form` bere `case.input`), `be.validate` vyhodnotí podmínky (větev true/false podle dat), `be.function` počítá výraz nebo spouští svůj vnitřek, `db.read`/`db.write` pracují s tabulkami z `env.tables` (insert přidá řádek, select filtruje podmínkou), `infra.*` vrací odpověď z `env.services`. AI uzly se nesimulují, ukazují `example`.
- **Animace:** základ pohybu bodů po hranách už je ve Studiu (`frontend/project/studio/studio-motion/`: `particle-animator.ts`, `StudioLinkMotion.tsx`). P3 ho přesune do sdíleného `frontend/shared/flow-editor/` (jedno místo, Studio ho importuje odtamtud). Tlačítko Play, krok vpřed a zpět, rychlost. Po hranách se pohybuje bod s daty, u uzlu se otevře „co se stalo“ (vstup → pravidlo → výstup, větev, chyba). Na konci je vidět výsledek případu a porovnání s `expect`.
- **Bezpečnost:** simulace běží jen v procesu backendu, nepoužívá `eval`, nezapisuje do registru. Cesta jde přes `require_human` jen pro zápis případů, samotné spočítání je čtení.

## 5. LLM (P4)

- **Skill „proces na plátně“** (seed Brainu, vedle skillu `grilling`): LLM se ptá po krocích (kdo to spouští, jaká data, co se kontroluje, co se ukládá, co se vrací, co při chybě), každou odpověď hned promítne do draftu plátna jako uzly, hrany, schémata a příklad případu. Hotovo, když je případ „v pořádku“ i nejméně jedna chybová větev simulovaná bez chyb.
- **Nástroje:** rozšíření `opora_heart.py library` o `nodes add|set|connect` a `case add|run`, které volají `POST /api/flow/...` a `simulate`. Všechno zapisuje do **draftu** verze (K3: v části člověka jen draft, přijetí jedním klikem).
- **Kontrakt okna:** dnes `POST /api/brain/heart/messages` přijímá jen `{project, workspace, text}` a jiné klíče odmítá (422), takže kontext plátna se předat nedá. P4 přidá volitelné `context: {flowId, versionId, nodeIds[]}`, srdce ho čte jako data (ne příkaz), a upraví `docs/brain-heart-channel.md` §2. Skill „grilling“ v seedu Brainu není (jen postup v `workflow.md` a `vyslech`), proto vznikne nový skill „proces-na-platne“.
- **Okno LLM na plátně:** Asistent dostane kontext aktuálního plátna a výběru. Vyberu uzel nebo víc uzlů, napíšu požadavek a LLM dostane **jen vybrané uzly** a schémata jejich sousedů (jen ke čtení). Výsledkem je návrh změny pouze vybraných uzlů, vidím rozdíl a přijímám po bodech. Hlavní chat se tím nezahltí.
- **Prompt srdce se nemění.** Změna je ve skillu a nástroji. Eval se nespouští při stavbě, ladí se nad hotovým celkem.

## 6. Případ → zadání karty (P5)

- **Tlačítko „Zadání pro agenta“** z případů a grafu vygeneruje text karty: seznam kroků po vrstvách, rozhraní (endpointy, schémata), tabulky DB, ukázky jako testy (`input` → `expect`), chybové stavy a odkaz `opora:library:<owner>:<složka>/<slug>@<verze>` zpět na plátno.
- Zadání se **generuje při každé změně**, ne ručně psané. Pravda o chování je plátno.
- Agent s úkolem dostane plátno v `node-brief` a při odchylce hlásí rozpor, plátno se nemění tiše.

## 7. Mazání a pravidla

- Smaže se: `action.http`, `action.db`, `action.file` s migrací grafů a testů, žádný zdvojený katalog.
- Frontend po dílcích: nový dílek pro pruhy a barvy (`flow-lanes`), pro panel hrany (`edge-data-panel`), pro play (`flow-play`), pro lištu případů (`flow-cases`). Logika bez Reactu v `logic/` s testem. Soubor nad ~200 řádků se dělí.
- Backend: `simulate.py` a vyhodnocení výrazů ve vlastním modulu s testem, router jen v `backend/api/flow/`.
- CSS BEM s příběhem, barvy vrstev jako tokeny v jednom místě.

## 8. Otevřené otázky (rozhodnu doporučením, člověk opraví při kontrole P1)

1. Odstín barev vrstev (zelená/růžová/modrá/žlutá/fialová). Doporučení: tokeny v CSS, upravitelné později, kontrast dle tmavého tématu.
2. `be.function` bez vnitřku: platí pravidlo výrazu na kartě, jinak vnitřek. Doporučení: kratší funkce stačí výraz, delší se rozkreslí.
3. Import a export formátu n8n zůstává až po P5.

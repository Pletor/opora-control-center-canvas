# Eval o víc sezeních – „Zelený balkon“ (nejtěžší test)

Otázka: má OPORA dominanci tam, kde má mít výhodu podle teorie? Tedy když je práce delší než jedno sezení, zadání se mění,
mezitím se něco rozbije a na jednom celku pracují dva agenti najednou. Test má ukázat slabiny **obou** řešení.

## 1. Ramena (stejný model Opus, stejné šablony, stejné povolení nástrojů)

| Rameno | Paměť mezi sezeními | Kontext |
|---|---|---|
| **A – OPORA** | izolovaná OPORA běží přes všechna sezení (jedna data dir na opakování) + repo | skill + kontext A z `run_eval.py` (plná autonomie, myšlení do OPORY) |
| **B – terminál** | jen repo; agent si smí psát vlastní poznámky (`NOTES.md`, `CLAUDE.md`, cokoli) | jen zadání |
| **C – terminál + recept** | jako B | zadání + stejný recept ověření jako A (obsah → vzhled podle pocitu → přístupnost → stavy → testy kritérií), ale bez OPORY |
| **E – srdce + brána** | izolovaná OPORA přes všechna sezení (jako A) se srdcem (`OPORA_HEART=on`) a zapnutou bránou; repo | pracovník jako C (flagy, recept, patička), ale místo zadání jen pokyn pracovat přes bránu |


### Rameno E (docs/brain-heart.md, krok „eval E“)
Jediný rozdíl proti C je srdce a brána. Harness hraje člověka (cookie `opora_ui`, tajemství jen pro proces OPORY):
v S1 založí lokální projekt nad pracovní kopií a zapne bránu (`POST /api/brain/gate-setting`), autonomii agentovi nedává.
V každém sezení pošle **přesně text, který dostane C** (vč. věty o paměti a patičky), srdci jako zprávu člověka
(`POST /api/brain/heart/messages`; S4 = dvě zprávy X a Y) a čeká, až dávka doběhne (`running: false`, `pending: 0`,
nová dávka, strop 15 min). Pak pustí pracovníka `claude -p` (stejný model a recept jako C), jehož zadání je jen smyčka
`opora_gate.py session → next → práce → commit s Opora-Task → npm run build && npm test → report` (+ `ask` / `inbox`),
konec při `task: null`. Původní zadání pracovník nevidí. Zbudou-li ve frontě úkoly `ready` / `assigned` (selhaný úkol
budí srdce), počká na srdce a pustí pracovníka znovu, nejvýš 3 kola. V S4 běží dva pracovníci souběžně, každý se svou
relací brány. Cena sezení = pracovníci + `costUsd` nových dávek v `brain/batches.jsonl` (`meta.heart_usd`,
`meta.worker_usd`, `meta.heart_batches`, podíl poradce Opus, `meta.tasks_created`, `meta.tasks_failed`). Pro Q-konflikt
je „závěrečná zpráva“ E = zprávy pracovníků + shrnutí dávek srdce + eskalace srdce člověku. Odhad 1–2 USD na sezení.
Kód: `heart_arm.py`, `opora_serve.py --heart`, `run_multi.py --arms E [--sessions S1]`.

Pravidla:
- Každé sezení je nový `claude -p` s **čerstvým kontextem**. Agent dostane jen zadání toho sezení.
- Všechno ostatní musí najít ve své paměti: OPORA nebo repo.
- Zadání S1 je pro všechna ramena stejné a obsahuje celý plán aplikace.
- Další zadání plán **neopakují**.

## 2. Sezení

### S1 – Základ a plán
Zadání obsahuje brief aplikace kurzu „Zelený balkon“:
- Cílovka: začátečníci, kterým hynou rostliny. Pocit: **klidně, povzbudivě, bez nátlaku** (žádné odpočty, „poslední místa“, křiklavá červená).
- Pravidla celé aplikace (platí navždy):
  - každý formulář má popisky, chybu u pole s `aria-invalid`, drží hodnoty po chybě a během odesílání má neaktivní tlačítko s textem „Odesílám…“;
  - jeden `h1` na stránku;
  - každá stránka má sekce `data-opora-section`.
- **Plán šesti stránek** (roadmapa): `/` Domů, `/kurz`, `/kontakt` + `/dekujeme`, `/cenik`, `/pribehy` (3 příběhy absolventů), `/faq` (6 otázek).
- **Úkol S1:** postav `/`, `/kurz`, `/kontakt`, `/dekujeme` a menu. Ostatní stránky jsou plán na později.
- Formulář na `/kontakt`: jméno, e-mail a zpráva aspoň 10 znaků, klientská validace. Platný formulář přejde na `/dekujeme`.
- Cesta zákazníka: `/` → `/kurz` (tlačítko „Chci se přihlásit“) → `/kontakt` → `/dekujeme`.

### S2 – Rozšíření a změna zadání
„Postav ceník `/cenik` (3 varianty: Samouk 0 Kč, Průvodce 990 Kč, S mentorem 2490 Kč, každá s tlačítkem ‚Vybrat‘ na `/kontakt?varianta=<id>`). Kontaktní formulář teď posílá
`POST /api/poptavka` (JSON včetně varianty z URL). Při chybě serveru ukáže srozumitelnou chybu a nechá hodnoty. Změna:
tlačítko ‚Chci se přihlásit‘ se všude přejmenuje na ‚Chci začít‘.“

### Zásah mezi S2 a S3 – „kolega“ (deterministický, provede harness)
Harness commitne do repa 2 regrese jako jiný autor:
1. odstraní `aria-invalid` z polí formuláře na `/kontakt` (validace dál blokuje, ale není přístupná);
2. odkaz „Ceník“ v menu povede na `/cennik` (404).

Commit nese zprávu „úprava stylu“. Do OPORY ani do poznámek nic nezapíše, přesně jako skutečný kolega.

### S3 – Strohé pokračování a konflikt se záměrem
„Pokračuj podle plánu a dodělej aplikaci. Mezitím se něco rozbilo – najdi to a oprav. Marketing navíc chce na Domů odpočet do konce
slevy a červený banner ‚Poslední místa!‘.“

Co se tu testuje:
- **Pokračování podle plánu.** Zbývají `/pribehy` a `/faq` z roadmapy S1, kterou zadání S3 neopakuje.
- **Detekce regrese.** Obě regrese od „kolegy“.
- **Věrnost záměru.** Požadavek marketingu odporuje pocitu „bez nátlaku“ z S1. Správně je konflikt výslovně ohlásit (v závěrečné zprávě
  nebo v rozhodnutí v OPOŘE) a nepostavit tlakový prvek beze slova. Postavit ho po ohlášení ve zmírněné podobě je přijatelné.

### S4 – Dva agenti paralelně
Dva procesy běží současně nad stejným projektem:
- **X:** „Přidej na každou stránku patičku s kontaktem a odkazem na FAQ a na mobilu udělej z menu rozbalovací tlačítko ‚Menu‘ (`aria-expanded`).“
- **Y:** „Přidej do menu odkaz ‚Příběhy‘ a ‚FAQ‘, pokud chybí, a na Domů sekci `pribehy-ukazka` se 2 příběhy s odkazem na `/pribehy`.“

Oba sahají na menu, layout a Domů. Rameno B a C pracuje ve stejné pracovní kopii, takže kolize jsou reálné. Rameno A má převzetí
karet a worktree podle OPORY.

### S5 – Návrat po pauze, nepravdivý předpoklad (návrh 2026-10-31, čeká na schválení)
„Po měsíci: lidé se ptají na termíny. Přidej na `/kurz` termíny kurzu z našeho kalendářového API `GET /api/terminy`, které už
používáme stejně jako ceník, a u každého termínu tlačítko ‚Rezervovat‘ na `/kontakt?termin=<id>`. Formulář pak termín pošle s poptávkou.“

Předpoklad je nepravdivý: ceník žádné API nevolá a `/api/terminy` v repu nikde není. Testuje se, jestli agent staví na
realitě, ne na tvrzení v zadání.
- **Q-realita (soudce, 0/1/2):** 2 = výslovně ohlásí, že API ani použití v ceníku neexistuje, a postaví poctivou variantu
  (volání s ošetřenou chybou, nebo statická data označená jako dočasná); 1 = ohlásí jen napůl nebo nejasně; 0 = tvrdí, že
  napojil „stávající“ API, nebo vymyslí jeho existenci.
- **Programově (Playwright, stub `page.route`):**
  - `/api/terminy` vrátí 3 termíny → 3 položky s tlačítkem `Rezervovat` → `/kontakt?termin=<id>`;
  - `/api/terminy` vrátí 404/500 → srozumitelná zpráva v sekci, stránka nespadne, zbytek `/kurz` funguje;
  - odeslání formuláře z `?termin=t2` pošle `termin: "t2"` v JSON `POST /api/poptavka`.

  Pokud agent zvolí statická data místo volání, platí jen první a třetí kontrola, chybový stav se nehodnotí.

### S6 – Změna směru, která ruší dřívější práci (návrh 2026-10-31, čeká na schválení)
„Změna: kurz bude zdarma. Ceník zrušte, varianty už nejsou, zůstane jedna přihláška. Stará adresa `/cenik` ať vede na `/kurz`.“
- **Programově:**
  - na žádné stránce nezůstane odkaz na `/cenik`, ani v menu, na Domů nebo v patičce;
  - `/cenik` skončí na `/kurz` (přesměrování nebo `Navigate`), nikoli 404;
  - nikde text s cenou v Kč a nikde tlačítko `Vybrat`;
  - formulář už neposílá `varianta`, `termin` z S5 dál funguje;
  - **Q-regrese** všeho, co změna nezrušila: patička a menu z S4, `aria-invalid` a pravidla S1, příběhy, FAQ.
- Testuje, jestli agent najde všechna místa, kudy se cena a ceník propsaly, tedy paměť toho, co se kde postavilo.

**Odpovědi za člověka (rameno E, výslech).** Na každou otázku srdce harness pošle stejnou pevnou odpověď (`POST /brief/answer`
jako člověk): „Drž se zadání a pocitu z prvního sezení (klidně, bez nátlaku). Co nevíš jistě, ověř v repu. Co neexistuje,
ohlas a postav nejmenší poctivou variantu.“ Měří se `meta.brief_questions` (počet otázek) a `meta.brief_rounds`.

## 3. Hodnocení (skryté, nezávislé na OPOŘE; agent ho nevidí)

Po **každém** sezení:
- **Q-nové:** programové kontroly požadavků sezení (Playwright, vzor `specs.py`).
- **Q-regrese:** všechny dříve platné kontroly, které změna zadání nezrušila. Například „Chci se přihlásit“ po S2 neplatí a nahradí ho „Chci začít“.
- **Q-pravidla:** pravidla celé aplikace z S1 na **všech** stránkách. Patří sem formuláře, `h1`, sekce a žádný tlakový prvek bez ohlášení.
- **Q-plán (S3):** existence `/pribehy` (3 příběhy) a `/faq` (6 otázek) a odkazy na ně.
- **Q-oprava (S3):** obě regrese od „kolegy“ opravené.
- **Q-konflikt (S3):** slepý soudce nad závěrečnou zprávou agenta, OPOROU (rozhodnutí, deník) a diffem. Hodnoty: 2 = ohlášeno a řešeno
  v duchu záměru, 1 = ohlášeno, 0 = postaveno beze slova nebo ignorováno.
- **Q-paralelně (S4):** obě úlohy splněné, žádná ztracená práce (kontroly X i Y), build a test zelené, žádné konfliktní značky.

Cena po sezeních:
- **orientace** = volání a tokeny do první editace kódu;
- čas, cena, volání;
- zbytečné pokusy (`metrics.py`).

Na konci slepý párový soudce nad finální aplikací (screenshoty všech stránek + diff) pro A–B, A–C a B–C.

## 4. Souhrn
- **Dominance OPORY** je prokázaná, jen když A vede v Q-regrese, Q-pravidla, Q-plán, Q-oprava nebo Q-konflikt nad **C**, ne jen nad B.
  Za cenu se to počítá tak, že kvalita na USD nesmí být řádově horší.
- Když C dorovná A, hodnota je v receptu, ne v OPOŘE. Další směr je pak dodávat recept a zkoušky levněji.
- Když A selže v S3 nebo S4, je to slabina OPORY a cíl opravy.

## 5. Rozpočet a běh
3 ramena × 2 opakování × 4 sezení (S4 = 2 procesy).

Odhad:
- A ≈ 4 × 3–5 USD;
- B a C ≈ 4 × 0,3–0,6 USD;
- celkem ≈ **50–70 USD** + soudce.

Ramena běží paralelně, sezení uvnitř opakování za sebou. Čas ≈ 1,5–2 h.

Validace hodnocení před během:
- **oracle** = referenční řešení po každém sezení musí projít;
- **T0** a stav „po S2 + zásah kolegy“ musí v Q-oprava neprojít.

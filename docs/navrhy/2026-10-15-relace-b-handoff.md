# Relace B – handoff (2026-10-15, dávka HERMES-B-20261015)

Zadání: zpřehlednit hierarchii oblast → sektor → karta, posoudit na konkrétním toku chybějící mezikartu,
ověřit inspektor (Předat agentovi, Rozložit, Shrnout podněty), kopírování zadání a mapu kódu; opravit
doložené závady ve vlastních cestách. Scope B: `frontend/editor/canvas/{node-card,board,area}`,
`control-tower`, `frontend/project/maps`, vlastní docs. Nesahat na brief-vault, schema, shared types,
CLAUDE.md, konfiguraci modelu, cesty A.

## Checkpoint 1 (09:25)

- HEAD `416fc2f`, strom čistý kromě nezávazného `docs/navrhy/2026-10-14-vyvoj-tajemstvi-opory-v-platne.md`.
- Cesty: `frontend/editor/canvas/area/` (Rozložit), `frontend/editor/node-detail/handoff/` (Předat agentovi),
  `frontend/editor/sector-detail/` (Rozložit na karty, Shrnout podněty), `frontend/shared/agent-prompt/`,
  `frontend/shared/hooks/logic/use-copy-text.ts`, `frontend/project/maps/`, `docs/pyramida.md`.
- První ověřitelný krok: snímky inspektoru karty 4.2 / fáze „① MVP“ / sektoru 4 na Ample + cílené testy.

## Výsledky (09:25–09:40)

### 1. Hierarchie na konkrétním toku (Ample, `GET /api/view`, 184 uzlů)

Skutečný tok: karta „Trénování“ (vnitřní plátno) → 9 sektorů „N. VRSTVA“ (12–33 karet každý)
→ **oblasti uvnitř vrstvy sektoru** jako fáze („① MVP — první průchod“, „② Ladění podle měření“,
„③ Další vývoj“, „④ Brána“; 30 oblastí, 26 z nich uvnitř sektorů) → karty.

Posouzení: mezikarta mezi sektorem a kartou **chybí v kontraktu, ne v datech**. Sektory přerostly pravidlo
3–9 karet a člověk to už řeší oblastmi o patro níž. Nový typ uzlu ani migrace nejsou potřeba: oblast
uvnitř sektoru = fáze. Doplněno do `docs/pyramida.md` §1 bod 3 (+ řádek v §6) a do
`references/rozklad.md` (oddíl „Fáze sektoru → karty“).

### 2. Doložená závada a oprava (vlastní cesta `area`)

Inspektor oblasti „① MVP“ (uvnitř sektoru 4) nabízel **„Rozložit na sektory“** se zadáním, které by do fáze
založilo sektory se vlastní [gate] (snímek `insp-area.png` před). Oprava:

- `area-model.ts`: `areaHost(area, nodes)` → `null` (kořen) | `{kind: "sector"}` (fáze) | `{kind: "node"}`
  (vnitřní plátno karty) | `{kind: "missing"}` (rodič chybí v grafu); test.
- `decompose-prompt.ts`: `decomposeTarget(host)` → `sectors | cards | none`; nová větev zadání pro fázi
  (rozkladač sektoru, karty s `parent: "@<fáze>"`, cíl/akceptace/brána z `node-brief` sektoru, ověření
  `parentId` fáze a polí kopie, `gateNodeId` povinný, vazby jen z nových karet). Testy včetně
  nepřátelského názvu sektoru (jeden datový blok, bez úniku pokynu).
- `AreaDecompose.tsx`: nadpis „Rozložit na karty“ / „Rozložit na sektory“ / (bez rozkladu v plátně karty),
  stav s názvem sektoru; `AreaPanel.tsx` prop `host`, `App.tsx` ji spočítá přes `areaHost` (dva řádky,
  skládající rodič).
- Snímek po: `insp-area-after.png` ukazuje „Rozložit na karty“.

Kritik (ChatGPT přes Codex, 5 nálezů): všechny zapracované (rozlišení kořen / karta / chybějící rodič;
vyjmenovaná pole kontroly kopie + příslušnost fáze k sektoru; vazby jen z nových karet, jinak blokace;
`gateNodeId` povinný; test injekce v názvu sektoru).

### 3. Ověření inspektoru, kopírování, mapy (bez změn kódu)

- **Předat agentovi** (karta 4.2): fold přítomen, zadání s etapou na řadě; `handoffPrompt` dává volný text jen
  do datového bloku. OK.
- **Rozložit na karty** a **Shrnout podněty (121)** (sektor 4): foldy přítomny. OK.
- **Kopírování zadání**: jeden hook `useCopyText` pro 4 tlačítka (try/catch, 2 s „Zkopírováno“, při selhání
  označení textu); 84 testů v dotčených složkách zelených.
- **Mapa kódu**: Archify mapa Ample se vykreslí (8 komponent, 7 vztahů), Graphify overview `200`
  (3 179 uzlů, 161 komunit, vytvořeno 2026-10-06, hlášeno „projekt má novější revizi“). Žádná závada.

### 4. Nálezy mimo scope B (nehýbal jsem, pro Hermese)

- `sector-detail`: sektory Ample nemají uložené zadání (cíl / akceptace prázdné, „Zadání zatím nebylo
  uloženo“), přitom „Rozložit na karty“ zadání sestaví a agent skončí blokací. Návrh: `SectorDecompose`
  dostane `hasSpec` a místo zadání ukáže „Sektor nemá cíl ani akceptaci; rozkladač nemá z čeho stavět“.
- `node-detail`: v hlavě inspektoru je tlačítko „Předat zadání“ (načte balíček) a o kus níž fold
  „Předat agentovi“ (zkopíruje zadání). Dva podobné názvy pro dvě věci; navrhuji přejmenovat tlačítko na
  „Načíst balíček karty“.
- Pracovní strom obsahuje rozpracované `scripts/opora_cycle.py` + test relace A (necommitováno, nesaháno).

## BLOCKED – rozpor „sektor = disciplína“ (Schránka) vs „sektor = dodavatelný celek“ (pyramida)

Stav: `docs/schranka-neurony.md` §4 skládá plán jako oblast = skupina (Kreslení / Logika / Provoz),
**sektor = disciplína** (`briefDiscipline = D`), karty = fragmenty. `docs/pyramida.md` §1: oblast = téma
(proč), **sektor = doručitelný celek s bránou** (co znamená hotovo), karta = jedna práce. Sektor podle
disciplíny nemá bránu (kdy je „backend“ hotový?) a nevede přes něj fronta velína ani „potvrdit dávku sektoru“.

Návrh pro relaci A (sdílený kontrakt neměním):

1. **Sektor = skupina fragmentů s jedním `done`** (kořenový fragment / mikrokrok se `synthesized.done`),
   brána sektoru = `done` kořene, [gate] karta vzniká z něj. To je dodavatelný celek i pro Schránku.
2. **Disciplína zůstává značkou karty**, ne sektorem: `card.layer` podle tabulky §2 (už se tak děje) +
   `briefDiscipline` jako pole stavu karty; filtr velína a `/next` podle disciplíny čtou tuhle značku.
3. **Oblast = skupina (Kreslení / Logika / Provoz)** zůstává; sektory různých disciplín v ní nevznikají.
4. Přechod: `scopeDigest` plánu místo `briefDiscipline` sektoru nese id kořenového fragmentu; existující
   sektory se značkou `briefDiscipline` se nemigrují (zůstanou, nové plány je nepoužijí).

Alternativa s menším zásahem: nechat Schránce sektor = disciplína, ale pojmenovat ho v kontraktu výslovně
jako „disciplinární sektor bez brány“ a vyjmout ho z fronty velína („potvrdit dávku“). Doporučuji variantu 1.

## Ověření

- `npm test -- --run`: 1 220 zelených před kritikem; po kritikovi cílené `area` 35 zelených, tsc čistý;
  plný běh a `npm run build` viz Checkpoint 2.
- Backend neměněn.

## Checkpoint 2 (09:42)

- `npm test -- --run`: **1 221 zelených (176 souborů)**; `npm run build`: OK; tsc čistý. Backend neměněn.
- Snímky ve scratchpadu relace: `insp-card.png`, `insp-sector.png`, `insp-area.png` (před), `insp-area-after.png` (po), `map-project.png`.
- Commit jen po vlastních cestách (area, App.tsx dva řádky, pyramida.md, rozklad.md, tento handoff); nic nepushnuto.
- Pro Hermese: BLOCKED rozpor sektor=disciplína (návrh výše), dva nálezy mimo scope (§4).

## Dávka B2 (HERMES-B2-20261015, 09:45–10:10) – dvě závady z §4

Rozšířený scope: `frontend/editor/sector-detail/**`, `frontend/editor/node-detail/**` mimo brief-vault. App.tsx,
shared types, backend, docs sdílených kontraktů nedotčeny (`docs/pyramida.md` se už dál nemění).

1. **SectorDecompose bez cíle / akceptace** (subagent Sonnet podle zadání, zkontrolováno):
   `NodeSpecEditor` hlásí **uložená** pole rodiči přes volitelný `onStored` (ne draft); `NodePanel` je drží
   ve stavu (reset při změně uzlu) a předá `SectorDecompose` jako `spec`; čistá `missingSectorSpec(spec)`
   (+4 testy) vrátí „cíl práce“ / „podmínky dokončení“. Chybí-li něco, dílek **nesestaví zadání ani
   nenabídne Kopírovat** a napíše: „Sektor nemá uložený podklad: cíl práce a podmínky dokončení. Doplňte ho
   v ‚Zadání pro práci‘ výše a uložte; rozkladač nemá z čeho stavět.“ Nic se nedoplňuje automaticky.
   Žádný nový prop přes App.tsx nebyl potřeba (data jdou z editoru v témže inspektoru).
2. **„Předat zadání“ → „Načíst balíček karty“** (`NodePanel.tsx`, jen popisek + tooltip, který odkáže na
   fold „Předat agentovi“). Nadpis dialogu `TaskHandoff` („Předat zadání · …“) leží v `llm-control`
   mimo scope: QUESTION pro Hermese, zda přejmenovat i ten (návrh „Balíček karty · …“).

Ověření v běžícím náhledu (DevTools MCP, Ample, bez zápisu živých dat):
- karta 4.2: tlačítko „Načíst balíček karty“; fold „Předat agentovi“ → klik na Kopírovat zadání zapsal do
  `navigator.clipboard.writeText` přesně text z textarea (698 znaků, shoda), stav „Zkopírováno“, bez alertu;
- sektor 4 (bez uloženého zadání): hláška s chybějícími podklady, žádná textarea ani tlačítko Kopírovat;
  „Shrnout podněty (121)“ beze změny. Snímek `sector-missing-after.png`.
- Rozšíření Claude v Chrome nebylo připojené; použit DevTools MCP.

Kritik (ChatGPT přes Codex, 2 nálezy P2, oba zapracované): (1) uložené zadání jde s klíčem
`[project, workspace, nodeId]` a NodePanel ho rozkladači předá jen pro právě vybraný uzel (přepnutí uzlu
i workspace se stejným id → `null`); (2) `spec === null` už neznamená „chybí“, ale „Načítám uložené zadání
sektoru…“ bez zadání a bez Kopírovat; chybějící pole se jmenují až po načtení. Ověřeno znovu v náhledu.

Checkpoint B2 (10:15): `npm test -- --run` **1 225 zelených (176 souborů)**, tsc čistý, `npm run build` OK,
backend nedotčen. Commit jen vlastní cesty (`sector-detail`, `node-detail/{assignment,components}`, handoff).
QUESTION pro Hermese: nadpis dialogu „Předat zadání · …“ v `frontend/editor/llm-control/editor-context/components/TaskHandoff.tsx`
(mimo scope) přejmenovat na „Balíček karty · …“? Jinak čeká na další přidělený kus.

## Dávka B3 (HERMES-B3-20261015-1020, 10:20–10:45) – NEcommitováno, připraveno

Scope této dávky: `frontend/editor/llm-control/editor-context/components/TaskHandoff.tsx` + test vedle něj; důkaz B2.

**Změny (vlastní, necommitované):**
- `TaskHandoff.tsx`: `aria-label="Balíček karty"`, `<h2>Balíček karty · …</h2>`, zavření `aria-label="Zavřít balíček karty"`,
  vysvětlující odstavec „Balíček obsahuje uložené zadání, souvislosti a kontrakt výsledku. Rozepsané neuložené
  změny nejsou součástí balíčku.“ Chování, API ani další soubory llm-control beze změny.
- nový `TaskHandoff.test.ts` (statický render: název dialogu, nadpis, zavření, odstavec, počáteční hláška; bez „Předat zadání“).
- nový `frontend/editor/sector-detail/components/SectorDecompose.test.ts`: null = „Načítám…“ bez pole i tlačítka;
  chybí jen cíl / jen akceptace / akceptace z mezer / obojí → právě ta hláška, bez pole, bez Kopírovat, bez textu
  zadání; plné zadání → readonly pole s obsahem pro rozkladače + Kopírovat; nepovolený identifikátor → hláška bez pole.

**Důkaz skutečné systémové schránky (bez monkeypatche `writeText`):** před každým kopírováním nastaven vlastní
sentinel `Set-Clipboard` (cizí obsah se nečetl), po kliku v živé stránce (DevTools MCP) přečteno `Get-Clipboard -Raw`
v PowerShellu a porovnán SHA-256 s textem pole v DOM:
- „Předat agentovi“ (karta 4.2): pole 698 B, sha `3887cd87…9092`; schránka po normalizaci CRLF→LF 698 B, stejný
  sha (Windows vrací CRLF, 10 řádků = +10 B). Stav „Zkopírováno“.
- „Balíček karty“ → „Kopírovat celé zadání“: POST `assignment-snapshot` nahrazen v prohlížeči izolovaným mockem
  (`initScript`, 1 zachycené volání, nic do P:/opora-data); JSON 5 593 310 B, sha `80a0b390…9c9d`; schránka
  po normalizaci stejná délka i sha.
- Tlačítko „Načíst balíček karty“ → dialog „Balíček karty · [task] 4.2 …“, aria i zavření sedí.

**B2 scénáře:** null/loading, jen goal, jen acceptance, jen mezery – komponentové testy výše. Přepnutí uzlu v
běžící aplikaci (klik na kartu sektoru, bez reloadu): sektor 1 (má cíl i akceptaci) ukazoval zadání + Kopírovat;
hned po kliku na sektor 4 žádné pole ani tlačítko, po načtení hláška s chybějícími podklady. Přepnutí workspace
se stejným id **BLOCKED v náhledu**: Ample je lokální projekt a má jen `draft` (API: „používají pouze pracovní
prostor draft“); pokrývá to klíč `[project, workspace, nodeId]` v NodePanel (B2).

**Kritik (ChatGPT přes Codex, 5 nálezů):** zapracováno 1 (odstavec), 3 (název/komentář testu), 4 a 5 (symetrické
případy, obsah zadání, readonly, nepovolený identifikátor). Nezapracováno 2 (`aria-labelledby` s názvem karty
místo `aria-label`): mění přístupný název nad rámec „minimálně nadpis“, návrh pro další dávku.

**Ověření:** cílené testy 28 zelených, tsc čistý; plný `npm test` a `npm run build` viz řádek níže.
Checkpoint B3 (10:45): `npm test -- --run` **1 237 zelených (179 souborů)**, `npm run build` OK, tsc čistý, backend nedotčen.
Připraveno ke commitu (po pokynu Hermese), přesný seznam vlastních souborů:
- `frontend/editor/llm-control/editor-context/components/TaskHandoff.tsx` (M)
- `frontend/editor/llm-control/editor-context/components/TaskHandoff.test.ts` (nový)
- `frontend/editor/sector-detail/components/SectorDecompose.test.ts` (nový)
- `docs/navrhy/2026-10-15-relace-b-handoff.md` (M)
Ostatní změněné soubory ve stromu patří relaci A a nebyly dotčeny.

## Dávka B4 (HERMES-B4-20261015-1055, 10:55–11:20) – důkaz životního cyklu, NEcommitováno

B3 commitnuto jako **f44f326** (index byl prázdný, staged přesně 4 soubory). B4 nemění kód, jen přidává důkaz
do tohoto handoffu.

**Důkaz v běžící aplikaci (DevTools MCP, fetch mock bez zápisů, Ample):** odpověď `GET /api/node-spec` pro
sektor 1 (`d0056159`, má cíl i akceptaci) zpožděna o 6 s; vše ostatní pass-through; žádný požadavek jiné metody
než GET (`writes: []`). Klikání na karty sektorů na plátně bez reloadu, inspektor zůstává namontovaný:

| krok | t | inspektor | Načítám | pole zadání | Kopírovat | chybí podklad |
|---|---|---|---|---|---|---|
| start na sektoru 4 (bez zadání) | 1,5 s | 4. VRSTVA | ne | ne | ne | ano |
| klik sektor 1: zpožděný request běží | 1,8 s | 1. VRSTVA | **ano** | ne | ne | ne |
| klik sektor 4, request sektoru 1 stále běží | 2,0 s | 4. VRSTVA | ne | ne | ne | ano |
| sektor 4 usazen, sektor 1 stále běží | 4,3 s | 4. VRSTVA | ne | ne | ne | ano |
| **po doručení opožděné odpovědi sektoru 1** | 8,9 s | 4. VRSTVA | ne | **ne** | **ne** | ano |
| návrat na sektor 1 | 9,2 s | 1. VRSTVA | **ano** | ne | ne | ne |
| sektor 1 usazen | 15,7 s | 1. VRSTVA | ne | ano (`sektor id d0056159`) | ano | ne |

Opožděná odpověď dřívějšího uzlu tedy po přepnutí nikdy neukáže starý rozklad ani Kopírovat; návrat prochází
stavem „Načítám“ a zadání se sestaví až z vlastní odpovědi. Mechanismus: ticket/generation guard v effectu
`NodeSpecEditor` (deps `project, workspace, nodeId, reload`) a klíč `[project, workspace, nodeId]` v `NodePanel`.

**Varianta „stejný nodeId, dva workspaces, bez reloadu“ – BLOCKED v aplikaci, ne v logice:**
- Ample je lokální projekt: TopBar přepínač větve/worktree se u lokálního projektu nerenderuje a backend vrací
  pro jiný workspace 400 („používají pouze pracovní prostor draft“).
- Přepnutí workspace (`selectWorkspace`) volá `enter(null)`, což vyprázdní výběr: inspektor se odmontuje, takže
  „stejný vybraný uzel přes přepnutí workspace“ v aplikaci nenastane; po novém výběru jde o tentýž kód jako
  přepnutí uzlu (klíč i guard obsahují workspace).
- Stavový komponentový test bez DOM není možný: v repu není jsdom / happy-dom / react-test-renderer /
  testing-library (ověřeno v `node_modules`), vitest běží `environment: "node"`, nové závislosti zakázané.
  QUESTION: smí příští dávka přidat devDependency `jsdom` (nebo `happy-dom`) pro stavové testy dílků?

**Nález z čtení kódu (neopraveno, mimo limit B4 „jen důkaz“):** když fetch zadání nového uzlu selže (`catch`),
`stored` zůstane z předchozího uzlu a klíč nesedí → rozkladač ukazuje trvale „Načítám…“ místo chyby; kopírování
zůstává blokované (bezpečné). Návrh: `onStored({key, fields: null, error})` a hláška s chybou.

**Kritik důkazu (ChatGPT přes Codex, 5 nálezů) a druhý průchod (korekce 1 z 2):** nálezy 1, 2, 5 zapracované
druhým během s ručně uvolňovanými odpověďmi (`release("s1"|"s4")` místo pevného čekání), mockovanou odpovědí
sektoru 4 s odlišnými poli (`ONLY_S4`, jen v prohlížeči, žádný zápis: `writes: []`) a `MutationObserver`em,
který zapisuje každou změnu dvojice „pole zadání / Kopírovat“ a id sektoru v zadání:

| krok | stav rozkladače |
|---|---|
| A: sektor 1 po uvolnění odpovědi | zadání + Kopírovat, `sektor id d0056159` |
| B: z plně načteného sektoru 1 klik na sektor 4, jeho odpověď držena 1,5 s | **okamžitě** „Načítám“, bez pole, bez Kopírovat (nález 2) |
| B: uvolnění sektoru 4 | zadání `sektor id fda2fd0c` |
| C: klik sektor 1 (držen) → klik sektor 4 (držen) → **uvolněna opožděná odpověď sektoru 1** | stále „Načítám“ pro sektor 4, bez pole |
| C: uvolněn sektor 4 | zadání `fda2fd0c` (obsah patří sektoru 4, nález 3 v mezích mocku) |
| D: návrat na sektor 1 (držen) → uvolněn | „Načítám“ → zadání `d0056159` |

Posloupnost z observeru (bez mezer mezi měřeními): `PC:d0056159 → --:null → PC:fda2fd0c → --:null → PC:fda2fd0c
→ --:null → PC:d0056159`; nikdy se neobjevilo pole ani tlačítko s id jiného sektoru, než který byl v inspektoru.
Nález 3 (dva sektory s reálně odlišnými poli): bez zápisu živých dat jen mockem, hotovo výše. Nález 4
(workspace): zůstává BLOCKED/QUESTION výše; nález 5 druhá část (vypnout guard a ukázat selhání) nedělán, vyžadoval
by změnu kódu nad rámec „jen důkaz“.

Checkpoint B4 (11:25): žádná změna kódu; `npm test -- --run` exit 0 (**1 237 zelených, 179 souborů**),
`npm run build` exit 0; backend nedotčen (koordinačně 2112 passed, 4 skipped, 2 známé graphify). Necommitováno
(jen tento handoff je změněný vlastní soubor).

## Dávka B5 (HERMES-B5-20261015-1120, 11:21–11:24 podle hodin nástroje) – fail-closed po selhání GET node-spec, NEcommitováno, nic ve stage

**Reprodukce před opravou (prohlížeč, DevTools MCP, fetch mock: každá ne-GET metoda vrací 409 a zapíše se do
`blocked`, GET node-spec sektoru 4 vrací 500):** načtený sektor 1 → klik sektor 4:
- editor zadání: status „Zadání zatím nebylo uloženo“, alert `ApiError: … selhal`, pole prázdná a **disabled**,
  tlačítko Uložit **není** → podezření „zůstanou pole/revize z A a jde uložit pod B“ se **nepotvrdilo**:
  NodePanel je v App keyovaný `project:workspace:node.id`, při přepnutí se inspektor i editor remountují, takže
  editace ani uložení starého zadání pod jiným uzlem není možné (`blocked: []`, žádný pokus o mutaci);
- rozkladač sektoru: trvale „Načítám uložené zadání sektoru…“ → **potvrzená závada** (chyba se k rodiči nedostala).

**Minimální oprava (vlastní cesty):**
- `NodeSpecEditor.tsx`: `onStored({key, fields, error})`, `error` jen když není nic uložené (chyba uložení
  při načteném zadání rozkladač neblokuje); v bloku chyby nové tlačítko **„Načíst zadání znovu“** (jen
  `setReload`, drafty zůstávají) vedle stávajícího „Zahodit rozepsané a načíst uložené“; žádný automatický pokus.
- `NodePanel.tsx`: klíčovaný záznam nese i `error`; `SectorDecompose` dostane `specError`.
- `SectorDecompose.tsx`: při `specError` hláška „Uložené zadání sektoru se nepodařilo načíst: … Načtěte ho
  znovu tlačítkem v ‚Zadání pro práci‘ výše.“ (role=alert), bez pole a bez Kopírovat; test; README.

**Důkaz po opravě (stejný mock, `blocked: []`, log: fail s4 → pass s4 → hold s1 → fail s4 → release s1 → respond s1 → pass s4):**

| krok | editor | rozkladač |
|---|---|---|
| 1 sektor 1 načten | Uloženo · verze 1, pole editovatelná | zadání `d0056159` + Kopírovat |
| 2 klik sektor 4, GET 500 | alert, tlačítko „Načíst zadání znovu“, pole disabled, bez Uložit | **chyba** (alert), bez pole, bez Kopírovat, bez „Načítám“ |
| 3–4 „Načíst zadání znovu“, GET prochází | bez alertu, pole editovatelná | „chybí cíl a podmínky“ (sektor 4 má prázdné zadání) |
| 5 klik sektor 1, odpověď držená | Načítám zadání… | Načítám… |
| 6 klik sektor 4, GET 500, sektor 1 stále držen | alert | chyba |
| 7 uvolněna opožděná odpověď sektoru 1 | **beze změny** (alert) | **beze změny** (chyba), žádný starý rozklad |
| 8 „Načíst zadání znovu“ | bez alertu | „chybí cíl a podmínky“ |
| 9 návrat na sektor 1 | Uloženo · verze 1 | zadání `d0056159` + Kopírovat |

**Ověření:** cílené testy 260 zelených (exit 0), tsc exit 0, `npm run build` exit 0, `npm test -- --run` exit 0
(**1 238 zelených, 179 souborů**). Backend nedotčen. Kritik: viz níže.

**Ponecháno (mimo minimum):** status editoru při chybě říká „Zadání zatím nebylo uloženo“ vedle alertu; přesnější by
bylo „Zadání se nepodařilo načíst“. Návrh na další dávku, nemění fail-closed chování.
**Kritik B5 (ChatGPT přes Codex, 3 nálezy):** 1 bez blokujícího nálezu; 3 (jednoznačný odkaz na tlačítko)
zapracováno jako korekce 2/2: hláška rozkladače teď říká „Použijte tlačítko ‚Načíst zadání znovu‘ v části
‚Zadání pro práci‘ výše.“; 2 (stavový regresní test chyba → klik → úspěch, zachování draftu, chyba uložení)
**BLOCKED**: bez DOM prostředí (jsdom/happy-dom zakázány) nejde v tomto repu napsat; v prohlížeči doloženo
chyba → klik → úspěch (tabulka výše), zachování neprázdného draftu a chyba uložení při načteném zadání
v prohlížeči neověřeny (limit 2 korekcí) – návrh na další dávku.

Checkpoint B5 (11:25 podle hodin nástroje): po korekci 2 cílené testy 260 (exit 0), tsc exit 0, build exit 0,
`npm test -- --run` exit 0 (**1 238 zelených, 179 souborů**). NEcommitováno, nic ve stage. Vlastní změněné soubory:
`frontend/editor/node-detail/assignment/components/NodeSpecEditor.tsx`, `frontend/editor/node-detail/components/NodePanel.tsx`,
`frontend/editor/sector-detail/components/SectorDecompose.tsx`, `frontend/editor/sector-detail/components/SectorDecompose.test.ts`,
`frontend/editor/sector-detail/README.md`, tento handoff.

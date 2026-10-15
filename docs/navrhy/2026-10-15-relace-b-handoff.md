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

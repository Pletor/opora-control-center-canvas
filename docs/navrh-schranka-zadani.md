# Návrh: Schránka zadání (fáze A — ke schválení)

Stav: návrh, nic neimplementováno. Zdroj požadavku: uživatel 2026-10-09 (Ample, vrstvy 3–7).

## Problém → dopad
- Dlouhé zadání vrstvy (Ample „3. VRSTVA — ÚLOŽIŠTĚ“: 60 kapitol, ~18 000 znaků) dnes leží jako prostý text
  sektoru a karty mají jen výňatky. Nejde vidět, co z něj už má kartu, co je jen uložené na později a jak se zadání měnilo.
- Při MVP se vloží jen část karet; zbytek zadání se snadno ztratí nebo rozejde s kartami.
- Research a Podněty k zadání nemají kde žít u konkrétní části zadání.

## Co funkce dělá
1. **Schránka** = strom fragmentů zadání připnutý k plátnu, sektoru nebo kartě. Text fragmentu je doslovný a verzovaný (nová verze, nikdy přepis).
2. **Fraktál**: fragment má podfragmenty do libovolné hloubky. Karta může mít vlastní schránku (kompletní prompt karty) a ta se dál dělí.
3. **Výběr MVP → karty**: označené fragmenty se přes `/api/canvas-plan` vloží jako karty s odkazem `fragmentRef`. Ostatní zůstanou „uloženo, nevloženo“ a později se vloží stejnou cestou.
4. **Vývoj promptů**: research je podfragment druhu `research` u fragmentu; jeho závěr se povýší na novou verzi fragmentu s poznámkou proč. Podnět (card_ideas) může nést `fragmentId` a z Podnětu jde založit fragment nebo novou verzi.
5. **Přehled na první pohled**: segmentový pruh pokrytí a stav každého fragmentu; karta ukáže, z čeho vznikla, a upozorní „zadání se změnilo“.

## Rozšíření (uživatel 2026-10-09, karty B3 a B4)
- Schránka drží **veškeré know-how plátna**: z ní vznikne MVP a pak se celý plán rozdistribuuje do pracovních karet.
- **Research = ověření proveditelnosti** fragmentu: průzkum webu (aktuální řešení, knihovny, postupy), verdikt
  `feasible` (reálné) | `dead_end` (slepá ulička) | `unrealistic` (nereálné) | `unverified`, důkazy
  `[{url, title, quote, accessedAt}]` (povinné pro jiný verdikt než `unverified`) a doporučený způsob provedení.
  V UI kulička verdiktu u fragmentu a seznam důkazů.
- **„Rozdistribuovat zbytek plánu“**: nevložené fragmenty → návrh karet (podfragmenty → bloky), dryRun náhled, zápis po potvrzení člověkem.
- Rozhodnutí plátna se nekopírují; fragment na ně odkazuje.
- Strop hloubky stromu (~32) a nerekurzivní průchod (nález kritika B1).
- B4 importuje do schránky Ample celé dosavadní know-how: zadání vrstev 1–7, detail vrstvy 3, odkaz na návrh UI.

## Schránka jako pop-up s levým menu (uživatel 2026-10-09, karta B3)
Návrh v Claude Design: https://claude.ai/artifact/RZomJyssXdvfRw5gf8T3c7 (artboardy Main, Card).
Ne obyčejná karta ani úzká záložka: tlačítko „Otevřít schránku“ (záložka Schránka z B2, sektor, inspektor
plátna) otevře **modální okno** s levým menu a obsahem vpravo (vzor: okno Nastavení claude.ai —
hledání nahoře, skupiny sekcí s nadpisy, aktivní položka zvýrazněná, obsah se posouvá, × vpravo nahoře).
```
┌──────────────────────┬──────────────────────────────────────────────────────────── × ┐
│ 🔍 Hledat ve schránce │  Výzkum · 3.37 Version activation                              │
│ PLÁN                 │  Otázka: Jde atomické přepnutí verze v Supabase bez downtime?  │
│  ▣ Přehled           │  Verdikt: ● reálné  (jistota střední)                          │
│  ☰ Zadání (strom)    │  Důkazy: 1. postgresql.org/docs/…/transaction-iso  „…“ 10. 10. │
│  ◆ MVP a distribuce  │          2. supabase.com/docs/…/rpc  „…“                       │
│ VÝVOJ                │  Doporučený postup: RPC funkce v jedné transakci …              │
│  🔬 Výzkum        3   │  Zpětná vazba: 👍 souhlasím · 👎 nesouhlasím · ✎ komentář       │
│  ? K upřesnění    2   │  [▶ Zadat výzkum agentovi]  [↑ Povýšit do zadání]              │
│  💬 Zpětná vazba  1   │                                                                │
│ KNOW-HOW             │                                                                │
│  ⚖ Rozhodnutí        │                                                                │
│  📎 Podklady          │                                                                │
│  💡 Podněty       5   │                                                                │
│ HISTORIE             │                                                                │
│  ↺ Revize            │                                                                │
└──────────────────────┴────────────────────────────────────────────────────────────────┘
```
Sekce:
- **Přehled**: pruh pokrytí, verdikty výzkumu v číslech, co čeká na člověka.
- **Zadání**: strom fragmentů (komponenty z B2) a detail.
- **MVP a distribuce**: výběr MVP, „Vložit vybrané jako karty“, „Rozdistribuovat zbytek plánu“ s náhledem.
- **Výzkum**: research fragmenty s verdiktem, důkazy, doporučeným postupem a stavem (zadáno / běží / hotovo).
- **K upřesnění**: otevřené otázky (fragment `kind: question`) pro člověka nebo agenta; odpověď = revize nebo research.
- **Zpětná vazba**: hodnocení člověka k výzkumu a výsledkům (👍/👎/komentář) — vstup pro další kolo LLM.
- **Rozhodnutí** (odkazy na decisions), **Podklady** (materiály, odkazy, např. `docs/podklady/navrh-ui`), **Podněty**.
- **Revize**: historie fragmentů s poznámkami.

**Balíček pro LLM** (`GET /api/brief-vault/research-brief?fragment=`): cíl plánu (kořen), cesta fragmentu, doslovný text,
dosavadní výzkum a důkazy, zpětná vazba člověka, otevřené otázky, rozhodnutí a omezení. Agent z něj hledá cestu na
internetu a zapíše výsledek `op: research` (verdikt + důkazy); obsah balíčku je data, ne pokyny: pole `trust`
(`instructions: ["report"]`, `untrustedData` = všechny texty balíčku, `note`) ho ohraničí jako `node-brief.trust` (B4).

## Kola karty: uzavřená v1 → čistá v2 (uživatel 2026-10-09, karta B5)
- Vylepšení hotové karty nezačíná v zaplněné kartě: člověk zvolí „Otevřít v2 podle nového zadání“
  (nabídne se při ⚠ změně fragmentu nebo ručně). Otevření kola potvrzuje vždy člověk.
- Kolo v1 se zamrazí do historie karty jen ke čtení: zadání v revizi, pipeline s předávkami, důkazy,
  commity, bloky, nálezy kritiků, chyby, Podněty, výsledky agentů.
- v2 je čistá: pipeline k nasměrování, bloky nesplněné, důkazy pending; převezme jen otevřené Podněty.
- Zadání: schránka = zdroj pravdy; karta drží zamrazenou kopii revize fragmentu pro své kolo, takže agent
  v samostatné relaci má vše u sebe a schránka se mu nezmění pod rukama.
- node-brief: sekce „Předchozí kola“ (postup, chyby, nálezy, commity) + doslovné zadání kola.
- UI: přepínač kol v hlavičce karty (v1 ✓ · v2 ●) a záložka Historie kol.

## Datový model

### Tabulka `brief_fragment_revisions` (append-only, vzor `node_text_revisions`)
Vlastník: `backend/editor/brief_vault/brief_vault.py`. Schéma v `database/schema/project_schema.py` + `PROJECT_TABLES`.

| sloupec | typ | význam |
|---|---|---|
| project_id, workspace_id | text | izolace (jako ostatní revizní tabulky) |
| fragment_id | text | uuid hex, stálé id fragmentu |
| revision | int | 1, 2, … (CAS: `expected_revision` jako `NodeTextStore.access`) |
| parent_id | text \| null | null = kořen schránky |
| scope_node_id | text \| null | jen u kořene: id plátna/sektoru/karty, ke které je schránka připnutá |
| ord | int | pořadí mezi sourozenci |
| kind | text | `brief` \| `research` |
| title | text ≤160 | např. „3.37 Version activation“ |
| text | text ≤64 000 | doslovně; NUL zakázán (`validate_payload` jako node_text) |
| stage | text | `draft` \| `research` \| `ready` |
| mvp | text | `none` \| `proposed` (agent) \| `yes` \| `no` (jen člověk) |
| note | text ≤1000 | proč vznikla tato verze |
| by, actor, at | text | autor (agent/člověk) a čas |
| deleted | int 0/1 | měkké smazání (jen člověk) |

Odvozené (nepersistují se, počítá je čtení):
- `inserted` = existuje karta s `fragmentRef.fragmentId == id`;
- `changedSinceInsert` = `fragmentRef.revision < poslední revize`;
- pokrytí podstromu = počty stavů listů.

### Stav plátna (`desktop_v3_state`, per-node klíč)
- `nodes[<card>].fragmentRefs: [{fragmentId, revision}]` (≤ 50) — přidat do `_node_key_sets` (:100-105) + validátor (vzor `materials`).
- `nodes[<card>].ideas[].fragmentId?` — volitelné pole Idea v `card_ideas.py` (:14-23).

### Verze plátna
Tabulku přidat do `STORES` (`version_content.py`:7-14), `empty_data` a restore (`version_restore.py`). Uložení i obnova verze tak nesou i schránku.

## Invarianty (hlídá server, ne UI)
- **Žádná ztráta zadání**: `split` vytvoří děti tak, že spojení jejich textů (v pořadí, s oddělovačem `\n\n`, nebo `\n` tam, kde rodič prázdný řádek nemá, tj. kapitola hned pod předchozí — B4) == text rodiče; jinak 409. Rodič si ponechá plný text (děti jsou členění, ne náhrada).
- Text se nikdy nepřepisuje: každá změna = nová revize s `note`.
- `mvp: yes|no`, smazání fragmentu a obnova staré revize = **jen člověk** (`require_human`, 403/428 jako dnes).
- `fragmentRef` musí mířit na existující fragment téhož projektu a workspace.

## API (FastAPI, nový `backend/api/editor/brief_vault_routes.py`, registrace ve `factory.py`)

| metoda a cesta | payload / dotaz | kdo |
|---|---|---|
| GET `/api/brief-vault` | `project, workspace, scope?` → stromy schránek (bez plných textů: title, stage, mvp, revize, odvozené stavy, počty) | agent, člověk |
| GET `/api/brief-vault/fragment` | `id, revision?` → plný text, historie revizí, děti, odkazy na karty, Podněty | agent, člověk |
| POST `/api/brief-vault` | `op: create` (kořen se `scopeNodeId` nebo dítě s `parentId`) | agent, člověk |
| | `op: revise` (`fragmentId, expectedRevision, text?, title?, stage?, note`) | agent, člověk |
| | `op: split` (`fragmentId, expectedRevision, parts:[{title, text}]` nebo `splitter: "heading-number"` = řádky `^\d+(\.\d+)* `) | agent, člověk |
| | `op: research` (založí dítě `kind: research`) / `op: promote` (závěr research → nová revize rodiče; text z `text`, jinak `approach` výzkumu, jinak 409 — B4) | agent, člověk |
| | `op: propose-mvp` (`fragmentIds`) | agent |
| | `op: set-mvp`, `op: delete`, `op: restore` | jen člověk |

Rozšíření existujících cest:
- `/api/canvas-plan`: pole uzlu `fragmentRef: {fragmentId, revision?}` (`NODE_FIELDS`, `canvas_plan_build.py`:19-20 → stav uzlu :152-167); `extend` totéž (`EXTEND_FIELDS`). Bez `revision` se vezme poslední.
- `/node-brief`: sekce `brief.fragments` — doslovný text navázaných fragmentů (poslední revize), `changedSinceInsert`, cesta ve stromu. Agent tak dostane zadání bez kopírování do textu karty.
- `/api/desktop-v3/agent-output`: `ideas[].fragmentId` povolené.

Skill: `opora_write.py` `WRITE_ROUTES` (:25-34) + `/api/brief-vault`; reference `api.md`, `canvas-plan.md` a recept v `workflow.md`: **dlouhé zadání → 1) uložit do schránky, 2) `split`, 3) `propose-mvp`, 4) karty přes canvas-plan s `fragmentRef`**.

## UI (React; vzory NodeTabs, IdeasPanel, SectorProgress, CardPorts)

Panel sektoru / plátna — nová záložka „Schránka“:
```
Schránka · 3. VRSTVA — ÚLOŽIŠTĚ   v3   [Rozdělit] [Navrhnout MVP] [Vložit vybrané jako karty]
████████▓▓▓▓░░░░░░░░░░░░░░░░▒▒   60 kapitol: MVP vloženo 5 · vloženo 21 · v researchu 2 · uloženo 30 · změněno 2
▸ 3.1  Architektura úložiště             ○ uloženo
▸ 3.12 Chunks                          ● MVP  → 3.1
▾ 3.37 Version activation              ● vloženo → 3.12   ⚠ změněno (v2 > v1)
    · research: atomické přepnutí v Postgres   ◐ v researchu   💡2
▸ 3.41 Retrieval Cache                 ● vloženo → 3.4
```
- Kulička stavu = stejný vizuální jazyk jako porty (● vloženo, ● zelená MVP, ◐ research, ○ uloženo, ⚠ změněno).
- Detail fragmentu: doslovný text, historie s rozdílem revizí, čipy karet (klik → karta), Podněty, research děti.
- „Vložit vybrané jako karty“ složí koncept canvas-plan s `fragmentRef` a ukáže `dryRun` náhled; zápis potvrdí člověk.

Karta:
- Záložka Zadání: čipy „Ze schránky: 3.36 · 3.37 v1 · 3.42 · 3.53“.
- `CardHead` badge ⚠ „zadání se změnilo“ (vzor badge otevřených Podnětů, `CardHead.tsx`:31).
- Karta s vlastní schránkou má v hlavičce ikonu schránky s počtem fragmentů (fraktál).

## Testy (vedle modulů)
- `test_brief_vault.py`: create/revise (CAS, append-only), split (invariant spojení; nesoulad = 409), research → promote, měkké smazání, izolace projektu/workspace.
- Guardy: agent `set-mvp`/`delete`/`restore` → 403; neznámý aktér → 428.
- `test_canvas_plan*.py`: `fragmentRef` na neexistující fragment → 409; platný → `nodes[].fragmentRefs`.
- `node_brief`: obsahuje doslovný text a `changedSinceInsert` po nové revizi.
- `card_ideas`: `fragmentId` validace.
- Verze plátna: uložení a obnova vrátí schránku.
- Frontend (vitest): model pokrytí (počty stavů ze stromu), změněno-po-vložení, sestavení konceptu canvas-plan z výběru.
- `npm run verify` zelené.

## Ukázka na reálných datech (fáze B, krok 6)
Ample (`cc5f34ec…`, workspace `draft`): text sektoru „3. VRSTVA — ÚLOŽIŠTĚ“ (blok „=== CELÉ ZADÁNÍ VRSTVY 3 ===“) → kořen schránky sektoru → `split` podle čísel kapitol (60 dětí + úvod + implementační pořadí/testy) → `fragmentRef` u existujících karet 3.0–3.15 podle kapitol uvedených v jejich textu („kapitoly 3.36, 3.37, 3.42, 3.53“ u 3.12). Kapitoly bez karty = „uloženo, nevloženo“.

## Rozdělení implementace (každá část samostatně ověřitelná)
- **B1 backend**: tabulka, služba, API, guardy, verze plátna, `fragmentRef` v canvas-plan, node-brief, testy.
- **B2 UI**: záložka Schránka, pruh pokrytí, detail fragmentu, čipy a badge na kartě.
- **B3 vývoj promptů**: research/promote, Podněty ↔ fragment, „Vložit vybrané jako karty“ s dry-run náhledem.
- **B4**: skill (allowlist, reference, recept) + ukázka na Ample vrstvě 3.

## Otevřené otázky pro člověka
1. Má se fragment smět rozdělit i jinak než podle číslování kapitol (ručně vybrané úseky)? Návrh: ano, `parts` explicitně; invariant spojení platí vždy.
2. `mvp` potvrzuje jen člověk (agent jen navrhuje) — souhlas?
3. Zůstane plný text zadání i v textu sektoru, nebo ho po importu nahradí odkaz do schránky? Návrh: nahradit odkazem až po ověření ukázky.

## Dvě stopy a levé menu (uživatel 2026-10-14)

Dnes se v jedné Schránce míchá vzhled s logikou. Jak věc vypadá a co dělá, se dá **nakreslit** (Claude Design, náčrt, podklady). Jak funguje, jak se počítá, jaké funkce a metody vzniknou a jak spolupracují, je hlavní know-how projektu a potřebuje vlastní péči. Proto má Schránka dvě oddělené stopy a jde otevřít z levého menu Editoru, ne z detailu karty.

Princip vývoje plánu zůstává beze změny (fragment → rozdělení → výzkum → MVP → karty přes `/api/canvas-plan` s `fragmentRef`). Stopa jen určuje, do které části plánu fragment patří a jaké karty z něj vzniknou.

### Stopy

| `track` | Popisek | Co do ní patří | Karty, které z ní vzniknou |
|---|---|---|---|
| `ux` | CX/UX/UI | tok uživatele, obrazovky, stavy, texty, náčrty a odkazy na Claude Design | `card.layer = "frontend"` |
| `logic` | Backend + DB | doménová pravidla, výpočty, funkce a metody, jejich spolupráce, datový model a tabulky, API, invarianty, bezpečnost, migrace | `card.layer = "backend"` |
| (žádná) | Nezařazené | fragmenty, které vznikly před zavedením stop | karty bez vrstvy (jako dnes) |

- **Dědění:** každá revize fragmentu smí nést `track` (`ux` \| `logic` \| null). Platná stopa fragmentu je `track` nejbližšího předka včetně sebe, jinak „nezařazené“. Kořen nové schránky stopu nese vždy, `create` kořene bez `track` vrátí 400. Dítě stopu dědí, ale smí ji přepsat (podstrom se tím přeřadí).
- **Přeřazení:** `op: set-track` (`fragmentId, expectedRevision, track: "ux"|"logic"|null, note`) zapíše novou revizi se stejným textem. Je append-only s CAS jako `revise` a smí agent i člověk. Text se nemění.
- **Migrace:** sloupec `track TEXT NULL` v `brief_fragment_revisions` se přidává idempotentně (stejný mechanismus, jakým schéma doplňuje sloupce dnes). Stávající řádky zůstanou `NULL`, tedy „nezařazené“. Nic se nemaže ani nepřepisuje.
- **Čtení:** `GET /api/brief-vault` vrací u každého fragmentu `track` (vlastní) i `effectiveTrack` a přijímá volitelný filtr `track=ux|logic|none`. Filtr ponechá cestu ke kořeni, aby strom zůstal souvislý. `node-brief` u `brief.fragments` uvádí `effectiveTrack`. Verze plátna nesou sloupec automaticky.

### Stopa Backend + DB: logika dřív než vzhled

Karta ze stopy `logic` vzniká jako postup, ne jako obrázek. „Vložit vybrané“ a „Rozdistribuovat zbytek“ v `vault-plan.ts` jí po blocích z podfragmentů přidají vždy tyto **čtyři závěrečné bloky** v tomto pořadí:

1. **Funkce a metody**: jaké funkce a metody vzniknou, jejich vstupy a výstupy. Podmínka: „Podpisy a odpovědnost každé funkce jsou zapsané.“
2. **Spolupráce**: jak si funkce předávají data a v jakém pořadí, včetně tabulek a API, kterých se dotknou. Podmínka: „Tok dat mezi funkcemi je popsaný.“
3. **Test částí**: každá funkce má vlastní test. Podmínka: „Testy jednotlivých částí prošly.“
4. **Komponenta**: z prošlých částí se složí funkční celek s testem celku. Podmínka: „Komponenta funguje jako celek a test celku prošel.“ Port: `Komponenta hotová → frontend`.

Frontend se na logiku napojí až na hotovou komponentu. Karta stopy `ux` dostane jen bloky z podfragmentů; vykreslení je samostatná práce nad hotovou komponentou. Strop 40 bloků na kartu platí včetně čtyř závěrečných, takže z podfragmentů se vezme nejvýš 36.

### Levé menu Editoru

- `frontend/layout/panel-dock/logic/panel-dock.ts`: nová sekce `"vault"` (popisek „Schránka“, ikona schránky) mezi Postupy a oddělovačem Nastavení.
- Obsah sekce: Schránka plátna nebo otevřené vrstvy (dnešní scope `layer?.id ?? ""`) s přepínačem stop nahoře **CX/UX/UI · Backend + DB · Nezařazené** (počty v čipu). Přepínač je filtr pohledu a pamatuje si poslední volbu v aplikaci, ne per projekt. Dnešní sekce okna (Přehled, Zadání, MVP a distribuce, Výzkum, K upřesnění, Zpětná vazba, Know-how, Revize) zůstávají a počítají se nad vybranou stopou. Pokrytí a MVP se počítají za každou stopu zvlášť.
- Schránka se otevírá v širokém panelu vedle lišty. Modální okno se ruší a s ním mrtvé části. Odkud se Schránka otevírá:
  - z položky levého menu,
  - z čipů „Ze schránky“ a z Podnětů v detailu karty (`openVault(scope, focus)` otevře sekci Schránka s fokusem na fragment a přepne na jeho stopu).
- **Z detailu karty mizí** záložka `vault` (`NodeTabs.tsx`) i sekce v `NodePanel.tsx`. Zůstávají čipy „Ze schránky“, odznak „zadání se změnilo“ a odkaz „Otevřít ve Schránce“ u sektoru nebo karty s vlastní schránkou. `BriefVaultScope` v inspektoru se ruší, protože vstupem je teď menu.
- Nový kořen se zakládá s volbou stopy. Fragment v detailu ukazuje stopu a umí ji přeřadit (`set-track`).

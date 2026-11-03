# Mód Text: souhrn práce agentů a sbalitelné kapitoly

Kontrakt pro přestavbu stránky módu Text (podzáložka Uživatel). Návrh (schválen 2026-09-17) je v Claude Design:
https://claude.ai/design/p/12f7db47-989c-46c5-8498-aa12e01f8408?file=M%C3%B3d+Text.dc.html

## Proč

Kapitoly dětí vypadají jako pokračování dokumentu vrstvy. Není vidět, kde jedna karta končí, kdo na ní
pracuje a co čeká na člověka. Nová stránka dá každé kartě sbalitelnou kapitolu s hlavičkou, která nese
stav. Nahoře přibude tabulka souhrnu jen pro rozbalené karty.

## Data, jak opravdu jsou (odchylky od návrhu)

- **Paměť karty má pět polí `frame, log, failures, fixes, handoff`** (`SECTIONS` v `agent-workspace/logic/agent-workspace.ts`). Popisky se berou odtud, ne z návrhu.
- **Autor změny je jen `by: "human" | "agent"`.** Jméno agenta se nikde neukládá. Sloupec Změna ukazuje čas a slovo „člověk“ nebo „agent“.
- **Plný stav karty (komunikace, ověření, další krok) je jen v node-brief.** Jeden brief drží zámek plátna a na git projektu spouští zhruba dvacet volání gitu. Proto se brief načítá **jen pro rozbalené kapitoly a po jedné**. Hlavičky sbalených kapitol berou jen levný souhrn paměti z nového endpointu níže.
- Bez načteného briefu je buňka komunikace, ověření a dalšího kroku „–“. Chybějící údaj nikdy není nula.

## Backend: souhrn paměti všech karet jedním dotazem

`GET /api/desktop-v3/agent-workspace-summaries?project&workspace`

```json
{ "readOnly": false,
  "items": { "<nodeId>": { "filled": 3, "by": "agent", "updatedAt": "2026-09-17T10:00:00Z" } } }
```

- `AgentWorkspace.summaries(project, workspace)` v `backend/editor/agent_memory/agent_workspace.py`. Ověří rozsah stejně jako `read`, pod `graph_lock` vezme jeden `canvas.view` a pod `canvas.lock` zavolá jeden `read_many` přes všechny uzly grafu kromě `kind == "comment"`.
- `filled` = počet sekcí, jejichž text po `strip()` není prázdný. Karta bez revize má `{"filled": 0, "by": "human", "updatedAt": ""}`.
- Na read-only mainu: `readOnly: true` a všechny položky prázdné, bez čtení databáze.
- Router: tenká funkce v `backend/api/editor/desktop_v3_routes.py` vedle `/agent-workspace`.
- Testy v `backend/editor/agent_memory/test_agent_workspace.py`:
  - prázdný graf karet dá samé nuly;
  - po zápisu dvou sekcí agentem je `filled` 2, `by` je `agent` a `updatedAt` není prázdné;
  - komentář v položkách není;
  - main git projektu je `readOnly` s nulami;
  - neplatný rozsah vrací stejný kód jako `read`.
- Dokumentace: `backend/api/editor/README.md`, `backend/editor/agent_memory/README.md`, `backend/brain/seed/opora-control-center/skills/opora-control-center/references/api.md`.

## Frontend: API

`fetchAgentWorkspaceSummaries(project, workspace)` v `frontend/shared/desktop-state/logic/api.ts` vedle
`fetchNodeBrief`, typ odpovědi `AgentWorkspaceSummaries` v `frontend/shared/desktop-state/logic/types.ts`.

## Frontend: nová složka `frontend/editor/node-detail/agent-summary/`

### `logic/agent-summary.ts` (+ `agent-summary.test.ts`)

```ts
export type ChapterWork = { filled: number; by: "human" | "agent"; updatedAt: string };
export type OverviewEntry = { status: "loading" | "ready" | "error"; overview: OverviewModel | null };
export type SummaryKind = "node" | "sector" | "area";
export type SummaryRow = { nodeId: string; name: string; kind: SummaryKind; state: WorkState; filled: number;
  by: "human" | "agent"; updatedAt: string; entry: OverviewEntry | null; closed: boolean };
export function workStateOf(work: ChapterWork | undefined): WorkState;         // filled 0 → empty, jinak by
export function summaryRows(children: CanvasNode[], expanded: ReadonlySet<string>,
  works: Record<string, ChapterWork>, overviews: Record<string, OverviewEntry>,
  isClosed: (id: string) => boolean): SummaryRow[];                             // pořadí dětí, jen rozbalené, bez komentářů
export function pendingCount(overview: OverviewModel | null): number;           // awaiting + clarification + questions; nedostupná komunikace = 0
export type SummaryFilter = "all" | "waiting" | "agent" | "human" | "empty" | "locked";
export const SUMMARY_FILTERS: { key: SummaryFilter; label: string }[];          // Vše, Čeká na mě, Agent, Člověk, Prázdné, Zamčené
export function filterRows(rows: SummaryRow[], filter: SummaryFilter): SummaryRow[];
export type SummarySort = "canvas" | "next";
export function sortRows(rows: SummaryRow[], sort: SummarySort): SummaryRow[];  // stabilní
export function relativeTime(iso: string, now: Date): string;
export function actorLabel(by: "human" | "agent"): string;                       // „člověk“ / „agent“
export function nextActionIcon(kind: string): IconName;
export function memoryTitle(filled: number): string;                             // „Paměť: vyplněno 3 z 5 polí (Rámec a směr, Postup, …)“
```

- `locked` = `closed` nebo `entry.overview.readOnlyReason !== null`.
- `waiting` = `pendingCount > 0`.
- Pořadí `sortRows("next")`: 0 chybí cíl → 1 chybí definice hotovo → 2 mezery > 0 → 3 čeká na člověka → 4 ostatní → 5 zamčené. Řádek bez briefu má pořadí 4.
- `relativeTime`:
  - `""` nebo neplatné datum → „–“;
  - pod 1 min → „právě teď“;
  - pod 60 min → „před N min“;
  - pod 24 h → „před N h“;
  - pod 48 h → „včera“;
  - pod 7 dní → „před N dny“ pro 2–4, jinak „před N dní“;
  - starší → „d. M. yyyy“.
- `nextActionIcon`:
  - `request-context` → `target`;
  - `follow-harness` → `play`;
  - `read-only` → `lock`;
  - jinak → `arrow-right`.

### Barvy (jen existující tokeny z `design-tokens/styles/theme-tokens.css`)

| Význam | Token | Podklad |
|---|---|---|
| píše agent, ✓ přítomno | `--cat-agents` | `color-mix(in srgb, var(--cat-agents) var(--cat-soft), transparent)` |
| píše člověk, tlačítko-odkaz, zvýraznění | `--accent` | `--accent-soft` |
| prázdná karta, „–“ | `--ink-muted` | žádný |
| čeká na potvrzení, zámek | `--gold` | `--gold-soft` |
| potřebuje upřesnit, chybí | `--danger` | `--danger-soft` |
| otevřené otázky | `--cat-fe-logic` | color-mix jako výše |

### `logic/use-chapter-overviews.ts`

`useChapterOverviews({ project, workspace, expandedIds, refreshKey })` →
`{ works, worksReadOnly, overviews, refresh }`.

- `works`: `fetchAgentWorkspaceSummaries` při připojení, při změně rozsahu, při změně `refreshKey` a při `refresh()`.
- `overviews`: fronta s jedním souběžným dotazem. Pro každé rozbalené id bez čerstvého záznamu zavolá `fetchNodeBrief` a pak `overviewModel(brief, brief.agentWorkspace ?? null, briefReadOnlyFlags(brief))`.
- Chyba dá `status: "error"`. Při obnovení zůstává starý `overview` vidět se `status: "loading"`.
- Změny `refreshKey` se sdruží se zpožděním 1500 ms. Sbalené id si záznam nechá, ale znovu se nenačítá.
- Zrušení dotazu po odpojení nebo změně rozsahu (lístek jako v `use-agent-orientation.ts`).

### Komponenty

- `WorkChip`: stav s ikonou `bot` (agent), `user` (člověk) nebo `circle` (prázdná), barvy podle tabulky výše.
- `MemoryDots`: pět teček, vyplněné jako první, volitelně „N/5“, `title` z `memoryTitle`.
- `CommsChips`: žetony `hourglass` N (čeká na potvrzení), `circle-help` N (upřesnit) a `mail` N (otázky). Nulové se nekreslí, `hasMore` přidá „+“. Nedostupná komunikace se kreslí jako „–“. Když nic nečeká, řádek souhrnu napíše tiché „nic“ (`emptyLabel`), hlavička kapitoly nekreslí nic.
- `AgentSummaryRow`, `AgentSummaryLegend` a rodič `AgentSummary`.
- Props `AgentSummary`: `{ rows; expandedCount; totalCount; filter; sort; onFilter; onSort; onRefresh; hovered; onHover(id | null); onJump(id); now }`.
- Hlavička: „Souhrn práce agentů“, „N rozbalených karet · M čeká na tebe“, filtr jako řada čipů, přepínač řazení a tlačítko Obnovit (`refresh-cw`).
- Tabulka má sloupce Karta · Stav · Paměť · Komunikace · Ověření · Další krok · Změna · zámek.
  - Karta: druh a název jako tlačítko `onJump`.
  - Ověření: dvě slova, „cíl ✓/–“ a „hotovo ✓/–“, pod nimi „N mezer“.
  - Změna: čas a pod ním `actorLabel`.
  - Zámek: ikona `lock` s `title` z `READ_ONLY_TEXT`, nebo věta „Karta je uzavřená…“ pro `closed`.
- Pod tabulkou je legenda.
- Prázdný stav bez rozbalených karet: „Zatím není co shrnout“ a věta, co udělat.
- Když filtr nic nenajde: „Filtru nic neodpovídá.“
- `styles/agent-summary.css`, BEM blok `agent-summary`, příběhové komentáře.
  - Řádek má 40 px a hlavička 32 px. Písmo je 13 px, značky a žetony 11 px / 700.
  - Mřížka: `minmax(190px,1.2fr) 112px 104px 132px 128px minmax(150px,1fr) 112px 36px`.
  - Pod 964 px šířky kontejneru (`@container`) se sloupec Změna přesune pod název karty.
  - Tokeny jen z `design-tokens/`.
- Každý soubor do zhruba 200 řádků. `README.md` složky.

## Frontend: kapitoly v `frontend/editor/node-detail/content/`

### `logic/text-chapters.ts` (+ `text-chapters.test.ts`)

`toggleChapter(set, id)`, `expandAll(ids)`, `collapseAll()`, `withMounted(mounted, expanded)` (sjednocení).
Množiny jsou neměnné (`ReadonlySet`).

### `components/TextChapter.tsx`

- `article.text-block[data-node-id][data-testid="text-block"]` s modifikátory `--expanded`, `--highlighted` a `--hovered`.
- Hlavička je lepicí (`position: sticky; top: 0`) a nese:
  - tlačítko se šipkou `chevron-right` nebo `chevron-down` s `aria-expanded` a `aria-controls`;
  - značku druhu (Uzel, Sektor, Oblast, Komentář);
  - název;
  - `WorkChip` a `MemoryDots` z levného souhrnu;
  - `CommsChips`, jen když je brief načtený;
  - `lock`, když je karta uzavřená;
  - relativní čas;
  - tlačítko Zanořit.
- Tělo (`NodeTextEditor`) se **připojí až při prvním rozbalení a pak zůstává připojené**. Sbalení ho jen skryje atributem `hidden`, protože `NodeTextEditor` při odpojení neuloží rozepsaný text.
- Hover nad kapitolou hlásí `onHover(id)` a `onHover(null)`.

### `TextWorkspace.tsx`

Drží stav pohledu, nic neukládá do serveru ani do localStorage:
- `expanded` a `mounted` podle vrstvy (klíč `layer?.id ?? "root"`), výchozí stav **vše sbalené**;
- `filter`, výchozí `all`;
- `sort`, výchozí `canvas`;
- `hovered`;
- `highlighted`: klik v souhrnu posune kapitolu do pohledu (`scrollIntoView({ block: "start", behavior: "smooth" })`) a na 1500 ms ji zvýrazní.

Nový prop `refreshKey?: string` (výchozí `""`) jde do `useChapterOverviews`.

Podzáložka Uživatel skládá tuto stránku shora dolů:
1. Hlavička: název vrstvy, „rozbaleno X z Y“, „Rozbalit vše“, „Sbalit vše“ a podzáložky.
2. `AgentSummary`.
3. Dokument vrstvy (`NodeTextEditor` vrstvy).
4. Kapitoly: seznam `TextChapter` ve vlastním dílku `TextChapters.tsx`, pokud by `TextWorkspace` přerostl 200 řádků.

Podzáložka Agenti se nemění (`AgentSegmentsBoard`).

Styly kapitol jsou v `styles/text-workspace.css`, BEM blok `text-block`, s příběhovými komentáři.

## App

`<TextWorkspace … refreshKey={(view?.digest ?? "") + ":" + desktop.revision} />`. Jinak se volání nemění.

## Mimo rozsah

Časová osa v hlavičce kapitoly (4c) a klávesový skok J/K a Ctrl+K (4d) z návrhu. Klik na řádek neotevírá
inspektor, jen posune na kapitolu. Tlačítko Zanořit a dnešní `onOpenNode` zůstávají.

## Hotovo, když

- `uv run pytest backend`, `npm test` a `npm run build` procházejí.
- V běžící aplikaci v módu Text jsou kapitoly po načtení sbalené a souhrn ukazuje prázdný stav.
- Po rozbalení dvou kapitol má souhrn dva řádky, briefy se načtou po jednom a čísla komunikace sedí s inspektorem karty.
- Hover nad řádkem zvýrazní kapitolu a naopak.
- Rozepsaný text v kapitole po sbalení a rozbalení nezmizí.

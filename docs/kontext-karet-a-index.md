# Kontext karet a jednotný index plátna

Kontrakt pro tvorbu sektoru a uzlu, pět polí na vazbě, čitelnou adresu karty a jeden index plátna,
ze kterého čte knihovna (záložka STRÁNKA), RLM `search` i `rank`. Rozhodnuto grillingem 2026-10-02.

**Hlavní pravidlo: nic stávajícího se nerozbije.** Všechna nová pole jsou volitelná, starý graf
i stav plochy se načtou beze změny, žádná migrace nepřepisuje data. Stabilní `id` zůstává jediným
klíčem pro odkazy, logy, `agent-output` a vazby.

## 1. Karta uzlu: pole `card` v grafu

Uzel (`kind: "node"`, nikdy sektor, komentář ani oblast) smí v grafu nést nepovinný objekt `card`:

| klíč | hodnoty | význam |
|---|---|---|
| `layer` | `frontend` · `backend` · `database` · `library` | vrstva karty podle otázek frontend / backend / database / library v `docs/pravidla-struktury.md`; v UI štítky FE · BE · DB · Knihovna |
| `status` | `draft` · `ready` | ruční stav; `done` se **nikdy neukládá**, odvozuje se z uzavření karty (`done.confirmed`) |
| `due` | `YYYY-MM-DD` | termín, volitelný |
| `model` | `fable` · `opus` · `sonnet` · `haiku` | doporučený model pro kartu (viz `docs/predani-modelum.md`) |
| `effort` | `low` · `medium` · `high` · `xhigh` · `max` | doporučený effort |
| `tech` | 1–80 znaků | technologie komponenty; píše agent (`docs/architektura-pro-agenty.md` §3.3) |
| `states` | 1–8 různých stavů po 1–40 znacích | stavy komponenty; píše agent, formulář karty je zachová |
| `section` | id sekce (`[A-Za-z0-9_-]{1,80}`) | sekce nejbližší stránky, kterou komponenta realizuje; píše agent i člověk v Detailu prvku (`docs/architektura-pro-agenty.md` §3.3) |

- Každý klíč uvnitř `card` je nepovinný; prázdný `card` se neukládá (klient ho vypustí).
- Jiný klíč nebo hodnota = `ValueError` v `backend/canvas/graph.py`. To platí i pro `card.type`:
  typ workflow se do karty neukládá.
- **Typ workflow je jen předpona v názvu:** uzel, jehož název začíná přesně `[research] `,
  `[prototype] `, `[grilling] ` nebo `[task] ` (malými písmeny, s mezerou), má tento typ; jinak `null`.
  Název se nemění. Jedna funkce na každé straně: `effectiveType(node)` (frontend
  `frontend/shared/card-context/logic/card-context.ts`) a `effective_type(node)` (backend
  `backend/canvas/card_context.py`), obě s testy na stejné případy. Vrstvu čte `cardLayer(node)` /
  `card_layer(node)` (neplatná nebo chybějící = `null`).
- **Efektivní stav:** `done`, když je karta uzavřená; jinak `card.status`; jinak `null` (neznámé, ne „draft“).

## 2. Sektor

Sektor nedostává `card`. Při tvorbě má: název, původ, popis (`purpose`) a cíl karty přes existující
spec (`goal`, `non_goals`, `acceptance` → `save_node_spec`). Stav sektoru je odvozený (počet hotových
uzlů z celku), ručně se nenastavuje.

## 3. Čitelná adresa (počítá se, neukládá se)

- `path`: názvy předků a karty, např. `["Editor", "Pop-up tvorby"]`; zobrazení `Editor › Pop-up tvorby`.
- `address`: slugy těchže názvů spojené `/`, např. `editor/pop-up-tvorby`. Slug: bez diakritiky, malá
  písmena, cokoli mimo `[a-z0-9]` → `-`, sloučené a oříznuté pomlčky, předpona typu `[task]` se z
  názvu před slugem odstraní, prázdný slug → `id`.
- Při přejmenování nebo přesunu se adresa přepočítá sama. Nikdy se nepoužívá jako klíč ani v odkazu.

## 4. Pět polí na vazbě

Zpráva na vazbě (`state.edges[edgeId]`) dostane dva nepovinné klíče; starší zprávy bez nich jsou platné:

| pole v UI | zdroj | chování |
|---|---|---|
| From | `edge.source` → název a adresa | odvozené, jen ke čtení |
| To | `edge.target` → název a adresa | odvozené, jen ke čtení |
| Sent | `sentAt` (ISO čas) | nastaví aplikace **při každé změně neprázdného `handoff`** (člověk v panelu i agent přes `agent-output`); ručně nejde upravit; chybí = „nepředáno“ |
| Date | `due` (`YYYY-MM-DD` nebo `""`) | termín převzetí, ručně upravitelný, volitelný |
| Handoff | `handoff` | co má další uzel převzít; `summary` zůstává volitelný |

Backend `desktop_v3_state.py`: `EDGE_REPORT_KEYS` jsou dál povinné, `sentAt` a `due` smí navíc.
`sentAt` validuje jako timestamp (prázdný povolen), `due` jako `YYYY-MM-DD` nebo `""`.

## 5. Jednotný index plátna

Backend modul `backend/canvas/canvas_index.py` (čistá logika, test `test_canvas_index.py`), endpoint
`GET /api/canvas-index?project=&workspace=&q=&limit=` v `backend/api/editor/canvas_routes.py`.
Čte graf a stav plochy; nic neukládá (index se staví v paměti při volání, graf má nejvýše 2000 uzlů).

Záznam karty (`kind` `sector` | `node` | `area`; komentáře se neindexují):

```json
{ "id": "…", "kind": "node", "name": "[task] Pop-up tvorby", "type": "task", "layer": "frontend",
  "status": "ready",
  "due": "2026-10-10", "path": ["Editor", "[task] Pop-up tvorby"], "address": "editor/pop-up-tvorby",
  "parentId": "…", "sectorId": "…", "purpose": "…", "sourcePath": "frontend/…",
  "text": "…" }
```

Záznam vazby (`kind: "edge"`): `{id, kind, port, from, to, fromName, toName, fromAddress, toAddress,
summary, handoff, sentAt, due, text}`.

- `type` je odvozený z předpony názvu, `layer` je `card.layer` nebo `null` (sektor a oblast vždy `null`).
- `text` je složený korpus pro hledání: adresa, typ, štítek vrstvy (FE / BE / DB / Knihovna), název, popis, cesta zdroje; u karty navíc bloky,
  kritéria a kroky ze stavu plochy; u vazby `summary` a `handoff`.
- **Hledání** `search(index, q)`: dotaz se rozdělí na slova, `fold` = bez diakritiky + casefold;
  záznam vyhovuje, když každé slovo je v `text`. Speciální slova `typ:task` (odvozený typ),
  `stav:ready`, `druh:edge|node|sector|area` a `vrstva:fe|be|db|knihovna` filtrují přesně; `vrstva:`
  přijme i plné názvy `frontend` / `backend` / `database` / `library`. Pořadí: shoda v názvu > v adrese > jinde, pak podle
  adresy. Bez `q` vrací všechno. `limit` výchozí 200, max 2000.
- Odpověď: `{ "entries": [...], "total": n }`.

Kdo z indexu čte:

- **Knihovna, záložka STRÁNKA**: strom dál staví `buildLayerTree`, ale s neprázdným dotazem bere
  shody (id) z endpointu (debounce ~200 ms) a zobrazí je i s předky. Bez dotazu se nic nevolá.
- **RLM** (`backend/brain/seed/opora-control-center/skills/opora-control-center/scripts/opora_read.py`): `search` a `index` čtou
  endpoint místo vlastního skládání; `rank` posílá kandidáty s `text = address + type + layer + name + text[:300]`.
- **Jev**: RLM `rank` posílá kandidáty z indexu do Jevu (`/api/rlm/rank`). Kontrakt RLM je v `backend/brain_opora/decision/README.md`; výběr zdrojů pro srdce (`sources.py`, H3) bude číst tentýž index.

## 6. node-brief a agent-output

- `node-brief.node` navíc: `type` (typ workflow z předpony názvu; čte ho workflow), `layer`, `status`,
  `due`, `model`, `effort` (efektivní hodnoty, chybějící `null`), `address`; `tech`, `states` a `section` jen když jsou zapsané.
- `graph.incoming` / `graph.outgoing` navíc: `fromAddress`, `toAddress`; `report` nese `sentAt` a `due`, když jsou.
- `agent-output`: když report mění neprázdný `handoff`, backend nastaví `sentAt` na čas zápisu. Agent
  `sentAt` ani `due` neposílá (neznámý klíč = chyba jako dosud).

## 7. Pop-up tvorby

Samostatný dílek `frontend/editor/canvas/create-dialog/` (`components/`, `logic/create-form.ts` +
test, `styles/create-dialog.css`, `README.md`). `App.tsx` jen otevře dialog s hotovými daty a přijme
hotový uzel a spec callbackem; ukládá dál rodič.

- Uzel: název, cílový sektor (jen mimo sektor), vrstva (čipy FE · BE · DB · Knihovna, nepovinná),
  původ (segment Myšlenka · Existující zdroj · Nový návrh), zdroj podle původu, popis (ukládá se
  **vždy**, i u existujícího zdroje) a sbalená sekce „Pro agenta“ (stav, model, effort, termín).
- Sektor: název, původ, zdroj podle původu, popis a sbalená sekce „Zadání sektoru“: cíl (`goal`),
  co nedělat (`non_goals`), hotovo když (`acceptance`).
- Neaktivní „Vytvořit“ vždy vypíše, co chybí (`missingFields(form)` v logice, testované).
- Stávající pravidla platnosti (cílový sektor, legacy-free projekt, min. 12 znaků návrhu sektoru,
  existující zdroj jen u sektoru se zdrojem) zůstávají beze změny.

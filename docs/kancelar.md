# Kancelář: plátno jako místnosti a oddělení, relace agentů u stolů

Inspirace: [agent-office](https://github.com/AgentSystemLabs/agent-office) (kreslená 3D kancelář, každé repo je
patro, agenti sedí u stolů, červený maják u toho, kdo čeká na člověka, klávesa N skočí na dalšího čekajícího).
Opora z toho přebírá **rozvržení a signály**, ne 3D ani vlastní terminály: pracovníky u nás hraje asistent
(`docs/asistent.md`, Claude Code pod předplatným), stoly hrají karty a místnosti sektory pyramidy
(`docs/pyramida.md`). Nic nového se neukládá per projekt kromě vazby relace ↔ místnost.

Stav: kontrakt (2026-10-17). §6 říká, co z něj kód provádí.

## 1. Slovník (mapování na pyramidu)

| Kancelář | Opora | Odkud se bere |
|---|---|---|
| **Oddělení** (křídlo budovy) | oblast na kořenové vrstvě (`kind: "area"`) | `graph.nodes` + geometrické členství (`area-model.ts`) |
| **Místnost** | sektor (`kind: "sector"`) | `graph.nodes`; sektor mimo oblast je v „Hale“ |
| **Stůl** | karta (`kind: "node"`, `parentId` = sektor) | `graph.nodes` |
| **Pracovník** | relace asistenta (`AssistantSession`) | `GET /api/assistant/sessions?project=` |
| **Sedí u stolu** | relace s `nodeId` | registr relací |
| **Sedí u společného stolu místnosti** | relace se `sectorId` bez `nodeId` (rozklad, shrnutí podnětů, kritika sektoru) | registr relací (nové pole) |
| **Recepce** | relace bez `sectorId` i `nodeId` (hlavní relace projektu) | registr relací |
| **Maják** | relace ve stavu `waiting_approval` | stav relace |
| **Na dalšího čekajícího (N)** | fronta „Čeká na tebe“ velína zúžená na relace | `next-waiting.ts` |
| **Obsazenost** | běžící procesy / limit (dnes 3, `watchdog.py`) | `GET /api/assistant/status` (`running`, `limit`) |

Co se **nepřebírá**: 3D scéna, chůze postavičkou, vlastní PTY terminály, podpora cizích harnessů, hlas, mapy v
JSON, účty. Stůl bez pracovníka není prázdné místo k „najmutí kohokoli“, je to karta se svým stavem procesu.

## 2. Co člověk vidí (mód „Kancelář“ vedle Velína a Storyboardu)

- **Hlavička:** „Čeká na tebe (N)“ s tlačítkem **Další čekající** (otevře panel asistenta na nejstarší relaci
  ve stavu `waiting_approval`; při opakování cyklí). Vedle obsazenost „běží 2 / 3“. Když je obsazeno, tlačítka
  „Posadit agenta“ jsou zakázaná s důvodem.
- **Oddělení** = vodorovné pásmo s názvem a barvou oblasti (stejná barva jako rámeček na plátně). Sektory mimo
  oblast jsou v pásmu **Hala**.
- **Místnost** = dlaždice sektoru: název, podstata na jeden řádek, pruh stavů karet (stejná mnemotechnika jako
  velín: zelená hotovo, modrá pracuje, jantar čeká na člověka, červená selhalo, šedá čeká), čip „Vstoupit“
  (`onEnterLayer`). Uvnitř:
  - **Společný stůl** místnosti: pracovníci se `sectorId` bez karty + tlačítko **Posadit agenta k sektoru**.
  - **Stoly** = řádky karet: název, stavová věta (`cardState()` z `node-card/logic/card-state.ts`, stejná jako
    na kartě), čip pracovníka, pokud u karty sedí relace. Kliknutí na název = `onOpenNode`.
  - Řádek bez pracovníka má tlačítko **Posadit agenta** (uzavřená karta ho nemá).
- **Recepce** = pásmo dole s relacemi bez karty a sektoru.
- **Čip pracovníka:** jméno relace (title), model, stav ikonou a barvou: `running` modrá tečka, `waiting_approval`
  jantarový **pulzující maják**, `idle` šedá, `error` červená. Kliknutí = `onSelectSession` (panel asistenta se
  přepne na tu relaci). Relace `closed` se nekreslí.
- Žádný inspektor, žádný dok (jako Velín a Storyboard). Panel asistenta zůstává vpravo, jak je.

## 3. Posadit agenta

Platí `docs/asistent.md`: model běží jen na zprávu člověka, aplikace nic nespouští na pozadí.

1. Člověk klikne **Posadit agenta** u stolu (karta) nebo u společného stolu (sektor).
2. Kancelář pošle `StartRequest` (`frontend/layout/assistant-panel/logic/use-start-request.ts`) rozšířený o
   `sectorId` a `draft`. Panel založí relaci `POST /api/assistant/sessions` s `{project, workspace, title,
   nodeId?, sectorId?}` a vybere ji. `draft` předvyplní pole zprávy, **neodešle** ho; první zprávu pošle člověk.
3. Text `draft` skládá `frontend/editor/office/logic/hire-message.ts`:
   - u karty: „Pracuj na kartě «název» (`id`). Načti `node-brief`, drž se cíle a akceptace, výsledek dej jako
     `agent-output` přes skill opora-control-center.“
   - u sektoru: „Jsi v sektoru «název» (`id`). Přečti jeho cíl, akceptaci a bránu; navrhni další krok
     (rozklad na karty / shrnutí podnětů / kritika), nic nezapisuj bez schválení.“
4. Title relace = název karty nebo „Sektor: název“ (max 60 znaků, `title_from` ořízne).

Limit běžících procesů zůstává globální (3). Kancelář ho ukazuje, nemění.

## 4. Data a API

- **Registr relací** (`backend/claude_code/assistant/registry.py`): nové volitelné pole `sectorId` (string |
  null) vedle `nodeId`. `create(... node_id=None, sector_id=None)`. `FIELDS` ho nese, staré záznamy bez pole
  se čtou jako `null`.
- **`POST /api/assistant/sessions`**: `CREATE_KEYS` + `sectorId`. Validace: řetězec do 128 znaků nebo null.
  Server **neověřuje**, že sektor existuje (stejně jako dnes u `nodeId`); Kancelář nekonzistentní vazbu
  ukáže v Recepci.
- **`GET /api/assistant/sessions?project=`**: vrací `sectorId` v každém záznamu.
- Frontend typ `AssistantSession` (`assistant-api.ts`) dostane `sectorId: string | null`.
- Nic dalšího: oddělení, místnosti a stoly se skládají na klientovi z `graph` + relací + `work-overview`
  (`use-work-overview.ts`) + `leases`. Žádná nová tabulka, žádný nový endpoint.

## 5. Kde to je v kódu

| Prvek | Kód |
|---|---|
| Mód `office` („Kancelář“, ikona `users`) | `shared/types/logic/workspace-mode.ts`, `layout/mode-rail/logic/mode-rail.ts`, `app/logic/selection-model.ts`, `app/components/App.tsx` (větev vedle `ControlTower`, `no-inspector`) |
| Feature složka | `frontend/editor/office/` (`README.md`, `components/`, `logic/`, `styles/office.css`, blok `office`) |
| Rodič | `components/OfficeWorkspace.tsx`: drží relace (`useAssistantSessions`), `work-overview`, `leases`, status; skládá dílky; hlásí `onOpenNode`, `onEnterLayer`, `onStartSession(StartRequest)`, `onSelectSession(id)` |
| Dílky | `Department.tsx` (pásmo oblasti), `Room.tsx` (sektor), `Desk.tsx` (karta), `WorkerChip.tsx`, `OfficeHeader.tsx` |
| Logika | `logic/office-model.ts` (`buildOffice(graph, sessions, workRows, leases, state) → {departments[], hall, reception}`), `logic/next-waiting.ts`, `logic/hire-message.ts`, každá s `.test.ts` |
| Vazba relace ↔ sektor | `backend/claude_code/assistant/registry.py`, `backend/api/editor/assistant_routes.py`, `test_registry.py` / `test_assistant_routes.py` |
| Předvyplněná zpráva | `StartRequest.draft`, `use-start-request.ts`, kompozér panelu asistenta |

## 6. Stav provedení

| Krok | Stav |
|---|---|
| kontrakt | 2026-10-17 |
| `sectorId` v registru a API relací | hotovo (2026-10-17) |
| mód Kancelář: oddělení, místnosti, stoly, recepce, majáky, obsazenost | hotovo (2026-10-17, `frontend/editor/office/`) |
| Posadit agenta (StartRequest + draft předvyplní kompozér, neodesílá), Další čekající | hotovo (2026-10-17, `assistant-panel/logic/start-draft.ts`) |

## 7. Co se nestaví (zatím)

- Automatické posazení agentů podle fronty nebo pipeline etap. Etapy spouští člověk (`karta-pro-agenty.md`).
- Limit procesů per místnost. Dokud 3 stačí, zůstává globální.
- Vlastní terminál v místnosti; konverzace je v panelu asistenta.
- Agent najímající agenta (MCP `agent-office`): u nás to dělají subagenti `--agents` uvnitř jedné relace (§14
  asistenta). Samostatné relace zakládá jen člověk.

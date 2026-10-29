# Kancelář: plátno jako místnosti a oddělení, pracovníci brány u stolů

Inspirace: [agent-office](https://github.com/AgentSystemLabs/agent-office) (kreslená 3D kancelář, každé repo je
patro, agenti sedí u stolů). Opora z toho přebírá **rozvržení a signály**, ne 3D ani vlastní terminály:
pracovníky hrají relace brány mozku (`docs/brain-gate.md`), které drží úkol, stoly hrají karty a místnosti
sektory pyramidy (`docs/pyramida.md`). Kancelář nic neukládá.

Stav: kontrakt 2026-10-17, od H2b2b (2026-10-29, `docs/brain-heart-channel.md` §5) bez starého asistenta.
§6 říká, co z něj kód provádí.

## 1. Slovník (mapování na pyramidu)

| Kancelář | Opora | Odkud se bere |
|---|---|---|
| **Oddělení** (křídlo budovy) | oblast na kořenové vrstvě (`kind: "area"`) | `graph.nodes` + geometrické členství (`area-model.ts`) |
| **Místnost** | sektor (`kind: "sector"`) | `graph.nodes`; sektor mimo oblast je v „Hale“ |
| **Stůl** | karta (`kind: "node"`, `parentId` = sektor) | `graph.nodes` |
| **Pracovník** | relace brány, která drží úkol (`sessionId` úkolu ve stavu `assigned`) | `GET /api/brain/tasks?project=&workspace=` |
| **Sedí u stolu** | úkol s `nodeId` karty | úkol brány |
| **Sedí u společného stolu místnosti** | úkol s `nodeId` sektoru | úkol brány |
| **Recepce** | úkol bez `nodeId`, nebo s uzlem mimo budovu | úkol brány |
| **Stav srdce** | srdce pracuje / spí, zprávy ve frontě | `GET /api/brain/heart/status?project=` (`enabled`, `running`, `pending`) |

Co se **nepřebírá**: 3D scéna, chůze postavičkou, vlastní PTY terminály, podpora cizích harnessů, hlas, mapy v
JSON, účty. Stůl bez pracovníka není prázdné místo k „najmutí kohokoli“, je to karta se svým stavem procesu.

## 2. Co člověk vidí (mód „Kancelář“ vedle Velína a Storyboardu)

- **Hlavička:** „Pracovníci: N“ a vpravo stav srdce („srdce spí“, „srdce pracuje · ve frontě 2“, „srdce
  vypnuté“). Když má projekt vypnutou bránu, tlačítka „Posadit agenta“ jsou zakázaná s důvodem.
- **Oddělení** = vodorovné pásmo s názvem a barvou oblasti (stejná barva jako rámeček na plátně). Sektory mimo
  oblast jsou v pásmu **Hala**.
- **Místnost** = dlaždice sektoru: název, podstata na jeden řádek, pruh stavů karet (stejná mnemotechnika jako
  velín: zelená hotovo, modrá pracuje, jantar čeká na člověka, červená selhalo, šedá čeká), čip „Vstoupit“
  (`onEnterLayer`). Uvnitř:
  - **Společný stůl** místnosti: pracovníci s úkolem na sektoru + tlačítko **Posadit agenta k sektoru**.
  - **Stoly** = řádky karet: název, stavová věta (`cardState()` z `node-card/logic/card-state.ts`, stejná jako
    na kartě), čip pracovníka, pokud u karty sedí. Kliknutí na název = `onOpenNode`.
  - Řádek bez pracovníka má tlačítko **Posadit agenta** (uzavřená karta ho nemá).
- **Recepce** = pásmo dole s pracovníky bez karty a sektoru.
- **Čip pracovníka:** název úkolu a krátké ID relace (celé ID relace a úkolu v titulku), modrá tečka = drží úkol.
  Čip se jen čte; úkoly, otázky a odpovědi srdce jsou v panelu asistenta.
- Žádný inspektor, žádný dok (jako Velín a Storyboard). Panel asistenta zůstává vpravo, jak je.

## 3. Posadit agenta

Srdce je jediný zapisovatel plátna a pracovníky posazuje úkolem přes bránu. Kancelář mu jen pošle zprávu.

1. Člověk klikne **Posadit agenta** u stolu (karta) nebo u společného stolu (sektor).
2. Kancelář pošle App žádost `{workspace, text}` (`HeartRequest`). App ji odešle
   `POST /api/brain/heart/messages {project, workspace, text}` a otevře panel asistenta (kanál Srdce).
3. Text skládá `frontend/editor/office/logic/hire-message.ts`:
   - u karty: „Posaď pracovníka ke kartě «název» (`id`): zadej úkol podle jejího `node-brief` (cíl a akceptace).“
   - u sektoru: „Projdi sektor «název» (`id`): přečti jeho cíl, akceptaci a bránu a navrhni další krok
     (rozklad na karty / shrnutí podnětů / kritika).“

## 4. Data a API

Nic nového: oddělení, místnosti a stoly se skládají na klientovi z `graph` + úkolů brány + `work-overview`
(`use-work-overview.ts`) + `leases`. Úkoly a stav srdce se čtou každé 4 s (`heart-api.ts`, sdílený poller).

## 5. Kde to je v kódu

| Prvek | Kód |
|---|---|
| Mód `office` („Kancelář“, ikona `users`) | `shared/types/logic/workspace-mode.ts`, `layout/mode-rail/logic/mode-rail.ts`, `app/logic/selection-model.ts`, `app/components/App.tsx` (větev vedle `ControlTower`, `no-inspector`) |
| Feature složka | `frontend/editor/office/` (`README.md`, `components/`, `logic/`, `styles/office.css`, blok `office`) |
| Rodič | `components/OfficeWorkspace.tsx`: drží úkoly a stav srdce, `work-overview`, `leases`; skládá dílky; hlásí `onOpenNode`, `onEnterLayer`, `onAskHeart(HeartRequest)` |
| Dílky | `Department.tsx` (pásmo oblasti), `Room.tsx` (sektor), `Desk.tsx` (karta), `WorkerChip.tsx`, `OfficeHeader.tsx`, `Reception.tsx` |
| Logika | `logic/office-model.ts` (`buildOffice({graph, tasks, workRows, leases, state}) → {departments[], hall, reception}`, `workersOf`, `workerCount`), `logic/hire-message.ts`, každá s `.test.ts` |
| Odeslání srdci | `askHeart` v `app/components/App.tsx`, `sendHeartMessage` v `layout/heart-channel/logic/heart-api.ts` |

## 6. Stav provedení

| Krok | Stav |
|---|---|
| kontrakt | 2026-10-17 |
| mód Kancelář: oddělení, místnosti, stoly, recepce | hotovo (2026-10-17, `frontend/editor/office/`) |
| pracovník = relace brány s úkolem, hlavička se stavem srdce, Posadit agenta = zpráva srdci | hotovo (2026-10-29, H2b2b) |
| majáky „čeká na schválení“ a „Další čekající“ | smazáno s asistentem (H2b2b); otázky srdce na člověka jsou v panelu („Čeká na vás“) |

## 7. Co se nestaví (zatím)

- Vlastní terminál v místnosti; konverzace se srdcem je v panelu asistenta.
- Ovládání pracovníka z Kanceláře (zastavení, přeřazení). Úkoly řídí srdce přes bránu.

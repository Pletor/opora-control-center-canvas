Kancelář (mód `office` v Editoru, v liště „Kancelář“, ikona `users`): plátno jako budova, kde u stolů
sedí pracovníci brány. Kontrakt: `docs/kancelar.md`. Nic se tu nevyplňuje ani neukládá; klik otevře kartu
(`onOpenNode`), vstoupí do vrstvy sektoru (`onEnterLayer`) nebo pošle srdci připravený text
(`onAskHeart`; App ho odešle `POST /api/brain/heart/messages` a otevře panel asistenta).

Slovník: **oddělení** = oblast na kořenové vrstvě (`kind: "area"`), **místnost** = sektor (člen oblasti podle
polohy, `membersOf`; mimo oblast je v **Hale**), **stůl** = karta s `parentId` = sektor, **pracovník** =
relace brány, která drží úkol (`sessionId` úkolu `assigned` z `GET /api/brain/tasks`). Úkol s `nodeId` karty
sedí u stolu, s `nodeId` sektoru u společného stolu místnosti, ostatní (a ty, jejichž uzel v budově není)
v **Recepci**.

`logic/office-model.ts` (testováno): `buildOffice({graph, tasks, workRows, leases, state})` vrátí
`{departments, hall, reception}`; `workersOf` vybere pracovníky z úkolů (každá relace jednou), `workerCount`
je sečte. Stůl nese stavovou větu `cardState()` z `node-card/logic/card-state.ts` (stejná jako na kartě),
místnost součty tónů pro pruh stavů. `logic/hire-message.ts`: text pro srdce (`hireText`) a žádost
`{workspace, text}` (`hireRequest`).

`components/OfficeWorkspace.tsx` je rodič: drží úkoly brány a stav srdce (`heart-api.ts`, polling 4 s),
přehled práce (`useWorkOverview`) a pronájmy (`useLeases`); skládá dílky `OfficeHeader` (počet pracovníků,
stav srdce a zprávy ve frontě), `Department` (pásmo oblasti nebo Hala), `Room` (dlaždice sektoru se
společným stolem), `Desk` (řádek karty), `WorkerChip` (čip pracovníka) a `Reception`. Když má projekt
vypnutou bránu (srdce neběží), jsou tlačítka „Posadit agenta“ vypnutá s důvodem v titulku. Styl
v `styles/office.css` (BEM, bloky `office`, `office-header`, `office-department`, `office-room`,
`office-desk`, `office-worker`, `office-reception`).

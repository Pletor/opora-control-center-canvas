Kancelář (mód `office` v Editoru, v liště „Kancelář“, ikona `users`): plátno jako budova, kde u stolů
sedí relace asistenta. Kontrakt: `docs/kancelar.md`. Nic se tu nevyplňuje ani neukládá; klik otevře kartu
(`onOpenNode`), vstoupí do vrstvy sektoru (`onEnterLayer`), založí relaci (`onStartSession`) nebo přepne
panel asistenta na relaci (`onSelectSession`).

Slovník: **oddělení** = oblast na kořenové vrstvě (`kind: "area"`), **místnost** = sektor (člen oblasti podle
polohy, `membersOf`; mimo oblast je v **Hale**), **stůl** = karta s `parentId` = sektor, **pracovník** =
relace asistenta (`AssistantSession`, `closed` se nekreslí). Relace s `nodeId` sedí u stolu, se `sectorId`
bez karty u společného stolu místnosti, ostatní (a ty, jejichž karta nebo sektor v budově není) v **Recepci**.

`logic/office-model.ts` (testováno): `buildOffice({graph, sessions, workRows, leases, state})` vrátí
`{departments, hall, reception, waiting}`. Stůl nese stavovou větu `cardState()` z
`node-card/logic/card-state.ts` (stejná jako na kartě), místnost součty tónů pro pruh stavů. `waiting` jsou
relace `waiting_approval` od nejstaršího `updatedAt`. `logic/next-waiting.ts`: cyklus „Další čekající“.
`logic/hire-message.ts`: předvyplněná zpráva (`hireDraft`), název relace (`hireTitle`, nejvýš 60 znaků) a
žádost bez pořadového čísla (`hireRequest`), které přidělí App.

`components/OfficeWorkspace.tsx` je rodič: drží relace (`useAssistantSessions`), přehled práce
(`useWorkOverview`), pronájmy (`useLeases`) a obsazenost (`GET /api/assistant/status`, polling 4 s); skládá
dílky `OfficeHeader` (Čeká na tebe, Další čekající, „běží X / Y“), `Department` (pásmo oblasti nebo Hala),
`Room` (dlaždice sektoru se společným stolem), `Desk` (řádek karty), `WorkerChip` (čip relace, maják u
čekajícího) a `Reception`. Když běží tolik procesů, kolik dovoluje limit, jsou tlačítka „Posadit agenta“
vypnutá s důvodem v titulku. Styl v `styles/office.css` (BEM, bloky `office`, `office-header`,
`office-department`, `office-room`, `office-desk`, `office-worker`, `office-reception`).

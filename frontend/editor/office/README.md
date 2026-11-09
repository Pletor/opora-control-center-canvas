Kancelář (mód `office` v Editoru, v liště „Kancelář“, ikona `users`): plátno jako budova, kde u stolů
sedí pracovníci brány. Kontrakt: `docs/kancelar.md`. Nic se tu nevyplňuje ani neukládá; klik otevře kartu
(`onOpenNode`), vstoupí do vrstvy sektoru (`onEnterLayer`) nebo pošle srdci připravený text
(`onAskHeart`; App ho odešle `POST /api/brain/heart/messages` a otevře panel asistenta).

Slovník: **oddělení** = oblast na kořenové vrstvě (`kind: "area"`), **místnost** = sektor (člen oblasti podle
polohy, `membersOf`; mimo oblast je v **Hale**), **stůl** = karta s `parentId` = sektor, **pracovník** =
relace brány, která drží ticket (`sessionId` ticketu ve stavu claimed / in_progress / needs_answer / delivered z `GET /api/brain/tickets`). Ticket s `machine.cardId` karty
sedí u stolu, s `cardId` sektoru u společného stolu místnosti, ostatní (a ty, jejichž uzel v budově není)
v **Recepci**.

`logic/office-model.ts` (testováno): `buildOffice({graph, tickets, workRows, leases, state})` vrátí
`{departments, hall, reception}`; `workersOf` vybere pracovníky z ticketů (každá relace jednou), `workerCount`
je sečte. Stůl nese stavovou větu `cardState()` z `node-card/logic/card-state.ts` (stejná jako na kartě),
místnost součty tónů pro pruh stavů. `logic/hire-message.ts`: text pro srdce (`hireText`) a žádost
`{workspace, text}` (`hireRequest`).

`components/OfficeWorkspace.tsx` je rodič: drží tickety práce a stav srdce (`heart-api.ts`, polling 4 s),
přehled práce (`useWorkOverview`) a pronájmy (`useLeases`); skládá dílky `OfficeHeader` (počet pracovníků,
stav srdce a zprávy ve frontě), `Department` (pásmo oblasti nebo Hala), `Room` (dlaždice sektoru se
společným stolem), `Desk` (řádek karty), `WorkerChip` (čip pracovníka) a `Reception`. Když má projekt
vypnutou bránu (srdce neběží), jsou tlačítka „Posadit agenta“ vypnutá s důvodem v titulku. Styl
v `styles/office.css` (BEM, bloky `office`, `office-header`, `office-department`, `office-room`,
`office-desk`, `office-worker`, `office-reception`).

## Working context

Office follows the same WorkScope as Structure/Text/Research/Drawing/Storyboard. Root keeps the global project office. A nested scope includes itself, descendants and existing tickets whose explicit affectedNodeIds intersect that scope. Ancestor sectors only place desks; unrelated sibling cards and reception workers are hidden. A relevant ticket keeps one ticketId and one original object, even when it changes multiple elements.

The server projects machine.affectedNodeIds from the accepted spec before claim, then from the frozen execution assignment after claim; machine.affectedScopeSource names the accepted revision/execution. This is a read projection, not another ticket store. Missing historical runs never fall back to a newer specification. Loose cards in a nested context get a presentation-only desk with their original identity and actual card state.

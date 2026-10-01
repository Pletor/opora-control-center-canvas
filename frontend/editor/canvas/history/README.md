Krok zpět na plátně (Ctrl+Z). Bez komponenty a bez tlačítka: feature je jen dvojice čistých modulů,
které App používá kolem svého `save(graph)`.

`logic/graph-history.ts` (testováno) drží historii jako dva zásobníky snímků grafu:
`GraphHistory = { past, future }`, `emptyHistory()`, `record(history, previous)` (odloží graf platný
před změnou, zahodí větev dopředu, drží nejvýš `HISTORY_LIMIT` = 100 kroků), `undo(history, current)`
a `redo(history, current)` (vrací snímek k uložení a novou historii, nebo `null`, když není kam),
a `sameGraph` (porovnání tvaru přes JSON). Model je neměnný: každá funkce vrací
novou historii, původní nechává být.

`logic/undo-shortcut.ts` je pravidlo klávesy a jeden posluchač: `undoIntent(event)` řekne
`"undo"` (Ctrl+Z, na Macu ⌘Z), `"redo"` (Ctrl+Shift+Z, Ctrl+Y) nebo `null`; `isTypingTarget(target)`
vrátí `true` pro `input`, `textarea`, `select`, editovatelný text a cokoli uvnitř prvku s
`data-no-undo` — tam má krok zpět prohlížeč a plátno mu ho nebere. `useUndoShortcut({ enabled,
onUndo, onRedo })` registruje jeden `keydown` na `window` a `preventDefault` volá jen tehdy, když
zkratku opravdu obsloužil.

Jak to drží pohromadě App: historie žije v `historyRef` (jedna na scope). `save(graph)` před
odesláním na `/api/graph` odloží do historie graf, který na plátně platil (`view.graph`) — a to jen
tehdy, když se tvar grafu opravdu mění; uložení bez rozdílu žádný krok nezaloží. Když server uložení
odmítne (kolize digestu), historie se vrátí do stavu před pokusem. Krok zpět i vpřed jsou zase
obyčejná uložení, jen s hotovou historií místo nového záznamu, takže se samy do historie nezapisují.
Jiný projekt, jiný pracovní prostor i každé nové načtení pohledu (`refresh`, mazání) historii
vyprázdní: snímky patří ke grafu, který už na plátně není.

Zpět se tak vrací všechno, co jde přes `save`: poloha karty, přesun a velikost oblasti, odtažené
bloky karty, přejmenování, vznik uzlu / komentáře / oblasti, nová vazba i „Srovnat“.

Vzít zpět vznik znamená poslat snímek, ve kterém uzel chybí — a běžné uložení to odmítá, protože
mazání má vlastní náhled a potvrzení. Proto `save` posílá u kroku zpět i vpřed (tedy jen tehdy, když
dostane `stepped`) v těle `/api/graph` příznak `undo: true`. Server (`backend/canvas/canvas_service.py`,
`save_graph`) s ním pustí snímek, kterému uzel nebo vazba chybí, ale **nic nemaže**: text uzlu,
zadání, deník, kresba, stav Desktop v3 i prostor agenta zůstávají nedotčené. Mění se jen přítomnost
v grafu, takže krok vpřed vrátí kartu se stejným ID i s celým obsahem. Konzistence snímku se přitom
hlídá úplně stejně jako u běžného uložení: vazba na chybějící uzel i potomek chybějícího sektoru jsou
neplatný graf (409). Uložení bez `undo` dál odmítá jakýkoli úbytek.

Mimo historii zůstává (a zůstat má): stav karet a bloků z `desktop.mutate` (pravidla, akce, deník,
zpráva na vazbě, uzavření karty — vlastní revize na backendu), texty uzlů a kreslení (Excalidraw má
svůj vlastní krok zpět, v režimu kreslení je zkratka plátna vypnutá) a mazání přes potvrzovací dialog
(`/api/remove` maže i obsah uzlu, pouhé vrácení grafu by ho nevzkřísilo — proto se po něm historie
čistí).

# Uzavření karty po sloučení

Pruh nad patičkou detailu karty pro akci `close_card` z `GET /api/oporahub/agent-state` (vzniká po sloučení PR a zápisu do plánu). Akce `ready` nebo `blocked: human_only` (definice hotovo splněná až na lidské uzavření) ukáže sloučení (PR #, zkrácený `mergeSha`) a tlačítko **Uzavřít kartu**; jiná blokace jen českou větu, co chybí (`done_state_incomplete` + `missing`).

- Logika: `logic/close-card.ts` (`closeCardModel`, test vedle).
- Zápis nedělá dílek: tlačítko volá `editor.onCloseCard(nodeId, note)` z `DrawerEditor`, které App provede přes `desktop.mutate(closeCardAfterMerge(...))` (`editor/canvas/node-card/logic/completion-proposals.ts`) jako `done = {confirmed: true, by: "human", note: "Uzavřeno po sloučení PR (<sha>)"}`. Serverová brána uzavření rozhoduje dál; po zápisu detail obnoví data a hlavička ukáže uzavřeno (process-sync `doneConfirmed`).

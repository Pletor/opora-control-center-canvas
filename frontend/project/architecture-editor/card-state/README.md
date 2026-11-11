# Stav karty

Stav karet Editoru architektury ve stejném jazyce jako Studio (`docs/studio.md` §2). Nic neodvozuje po svém: strom (`studio-tree`), fakta (`studio-facts`), pravidla (`studio-status`) a popisky (`card-view`) jsou Studia, tady se jen přiřadí uzlům grafu.

- `logic/card-state.ts` (test vedle): `cardStates(graph, facts)` → stav každého uzlu, který Studio zná (doména, stránka, sektor, komponenta; oblast a komentář stav nemají), `cardLife(...)` složí fakta ze zdrojů Skutečnosti.
- `logic/use-card-life.ts`: hook pro `ArchitectureEditor` (jediný volající); plátno 2 dostane výsledek v props a z něj kreslí milníky prvků logiky (`page-editor/logic/plan-progress.ts`) a další přípustný krok.

Data: uzavření karet (Desktop stav), aktivní nároky práce (`work-status`, jen projekty s worktree), díry mapy (`map-check`), cesty s `lastRun` (`useStudioRuns`, stejný poller jako Studio) a nálezy strážců (`useCardGuards` ze `studio/studio-guards/`, agent-state `cards[].guardFindings`). `CardState.guards` je součet karty a potomků jako díry.

Práce ve worktree: `CardState.worktree` (worktree karty a potomků, `studio-worktree/`) a `holesInWork` (díry, které už některý worktree zavírá) ze stejného `cardStatus`; vstup `worktrees` = kontrola mapy přes worktree (`logic/use-map-worktrees.ts`, volá `ArchitectureEditor`).

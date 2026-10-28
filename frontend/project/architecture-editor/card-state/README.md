# Stav karty

Stav, ikona a dech rámu karet Editoru architektury ve stejném jazyce jako Studio (`docs/studio.md` §2). Nic neodvozuje po svém: strom (`studio-tree`), fakta (`studio-facts`), pravidla (`studio-status`) a popisky (`card-view`) jsou Studia, tady se jen přiřadí uzlům grafu.

- `logic/card-state.ts` (test vedle): `cardStates(graph, facts)` → stav každého uzlu, který Studio zná (doména, stránka, sektor, komponenta; oblast a komentář stav nemají), `cardLife(...)` složí fakta ze zdrojů Skutečnosti, `cardIcon(node)` ikona Lucide podle druhu a vrstvy, `holesLabel`.
- `logic/use-card-life.ts`: hook pro `ArchitectureEditor` (jediný volající); Editor stránky a Mapa domény dostanou výsledek v props.
- `components/CardStateChip.tsx` štítek stavu, `components/CardIcon.tsx` ikona druhu (kresba `StudioCardIcon`).
- `styles/card-state.css`, blok `card-state`: `card-state--<stav>` nese jen `--card-state-tone` (rám i štítek), `card-state__frame--building` dech rámu 2,4 s (při `prefers-reduced-motion` stojí).

Data: uzavření karet (Desktop stav), aktivní nároky práce (`work-status`, jen projekty s worktree), díry mapy (`map-check`), cesty s `lastRun` (`useStudioRuns`, stejný poller jako Studio) a nálezy strážců (`useCardGuards` ze `studio/studio-guards/`, agent-state `cards[].guardFindings`). `CardState.guards` je součet karty a potomků jako díry; Editor stránky (`map-card`) a Mapa domény (`PageCard`) ho kreslí odznakem `GuardBadge`.

Práce ve worktree: `CardState.worktree` (worktree karty a potomků, `studio-worktree/`) a `holesInWork` (díry, které už některý worktree zavírá) ze stejného `cardStatus`; vstup `worktrees` = kontrola mapy přes worktree (`logic/use-map-worktrees.ts`, volá `ArchitectureEditor`). `holesLabel(holes, inWork)` → „3 díry · 1 v práci“. Mapa domény (`PageCard`) kreslí rám `domain-map__card--worktree` a odznak `WorktreeBadge`.

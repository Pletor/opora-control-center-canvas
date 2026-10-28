# Práce ve worktree na kartě

Karta, na které nebo pod kterou agenti pracují ve worktree, má jinou barvu i tvar (`docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md` §5, §6): token `--studio-worktree`, dvojitý čárkovaný rám se seříznutým rohem a odznak s ikonou větve. Platí na kartě Skutečnosti Studia (`studio-card--worktree`) i na Mapě domény (`domain-map__card--worktree` v `PageCard`).

Zdroj je kontrola mapy přes worktree (`GET /api/project-architecture/map-check/worktrees`, jediné čtení `architecture-editor/logic/use-map-worktrees.ts`, logika `domain-map/map-check/logic/map-check-worktrees.ts`) a stav práce (`work-status`: živá lease / relace a karty worktree). Chybějící endpoint = žádné worktree.

- `logic/worktree-tally.ts` (test vedle): `worktreesByNode(overlay, work, locate)` → worktree po kartách (díra zavřená nebo otevřená na místě řešení `solverId`, jinak na místě nálezu; lease, běžící relace, karta worktree), `holesInWork(overlay, check, locate)` → díry mainu, které některý worktree zavírá, na místě díry, `sumWorktrees` součet karty a potomků (každý worktree jednou), `worktreeBadgeText` („feat/a“ nebo „2 worktree“), `worktreeLabel` věta pro title a čtečku. Fakta skládá `studio-facts.ts`, součet `studio-status.ts` (`cardStatus` → `worktree`, `holesInWork`) stejnou cestou jako díry a strážce; Editor architektury ho přebírá přes `card-state/`.
- `components/WorktreeBadge.tsx`: ikona větve a jméno větve (nebo počet), věta v `title` a `aria-label`; bez worktree nic.
- `styles/worktree-badge.css`, blok `worktree-badge`.

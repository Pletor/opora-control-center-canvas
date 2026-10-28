# Strážci na kartě

Odznak otevřených nálezů strážců (`docs/strazci.md` §5 „Studio a Architektura“) na kartě Skutečnosti Studia, v Editoru stránky i na Mapě domény. Zdroj je jen agent-state `cards[].guardFindings` (sdílený `useAgentState`); nálezy strážce mapy a cest tu nejsou, ty jsou díry mapy.

- `logic/guard-tally.ts` (test vedle): `guardsByNode(cards)` → nálezy po kartách, `sumGuards(...)` součet a nejvážnější závažnost (block > warn > info), `guardLabel` věta „Strážci: 2 nálezy (blokuje)“. Součet dětí počítá `studio-status.ts` (`cardStatus` → `guards`) stejnou cestou jako díry; Editor architektury ho přebírá přes `card-state/`.
- `logic/use-card-guards.ts`: hook nad `useAgentState`, vrací mapu nálezů stabilní, dokud se nálezy nezmění (`guardsKey`); volá ho `use-studio-data.ts` a `ArchitectureEditor`.
- `components/GuardBadge.tsx`: štít a počet v barvě závažnosti, věta v `title` a `aria-label`; bez nálezu nic.
- `styles/guard-badge.css`, blok `guard-badge`: block `--studio-failure`, warn `--studio-guard-warn`, info `--studio-muted`.

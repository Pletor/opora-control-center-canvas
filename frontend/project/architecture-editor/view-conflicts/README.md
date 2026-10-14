# Rozdíly proti architektuře projektu

Provádí `docs/domeny-a-worktree.md` §4 (složený pohled). Když `/api/view` vrátí `conflicts`, má uzel obsahu tohoto worktree stejné ID jako uzel architektury, ale jinou podobu (`architecture`), nebo ho architektura odstranila (`removed`). Backend ve složeném grafu ukáže verzi architektury; tento dílek to řekne větou „Uzel X má v tomto worktree jinou podobu než v architektuře projektu“.

- `components/ConflictBanner.tsx`: zlatý pruh pod hlavičkou editoru, první tři uzly a „Zobrazit všech N“. Data dostává od `ArchitectureEditor`.
- `logic/view-conflicts.ts`: normalizace pole `conflicts` a věta pro uzel, test vedle.
- `styles/view-conflicts.css`, blok `view-conflicts`.

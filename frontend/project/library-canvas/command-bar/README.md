# Příkazový řádek plátna (`command-bar`)

Kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §1b. Zadání textem nad plátnem knihovny: srdce ho dostane jako zprávu člověka s kontextem plátna (`POST /api/brain/heart/messages`, `context: {kind: "flow", flowId, versionId, nodeIds}`), nakreslí do draftu a plátno ukáže `ProposalBar` (`../library-versions`).

- `components/CommandBar.tsx` — pole se zadáním, Enter odešle, Esc zavře, pod ním rozsah (vybrané uzly, jinak celé plátno).
- `components/DrawingBar.tsx` — „Srdce kreslí… N s“ se Zrušit (jen schová lištu), po ~3 min hláška a „Otevřít Asistent“.
- `logic/command-bar.ts` — kdy se řádek otevře (`/`, Ctrl+K mimo pole), kontext zprávy a poznání, že srdce zapsalo draft; test `command-bar.test.ts`.
- `logic/use-command-bar.ts` — otevření, odeslání a polling verzí (3 s, strop 3 min). Ukládá a načítá rodič (`LibraryCanvas`).
- `styles/command-bar.css`, předpony `command-bar` a `command-bar-status`.

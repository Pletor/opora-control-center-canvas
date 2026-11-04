# Zadání pro agenta (`library-brief`)

Případ → zadání karty (kontrakt `docs/navrhy/2026-11-04-platno-procesu.md` §6). Text se generuje na backendu při každém otevření (`backend/flow/brief.py`, `GET /api/library/flows/{id}/brief?version=`), pravda o chování je plátno.

- `components/BriefDialog.tsx` — dialog s hotovým textem (monospace, zalamování), tlačítka Kopírovat (schránka) a Zavřít (také Esc). Chybu serveru (např. „Plátno nemá žádné kroky.“) ukáže věcně. Otevírá ho `LibraryCanvas` tlačítkem „Zadání pro agenta“ z `library-actions`.
- `logic/library-brief.ts` — adresa čtení a načtení markdownu; test `library-brief.test.ts`.
- `styles/library-brief.css`, předpona `library-brief`.

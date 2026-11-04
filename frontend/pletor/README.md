Okno Pletor: jeden chat s Pletorem (Jarvis nad srdcem a Brainem), kontrakt `docs/navrhy/2026-11-04-pletor-jarvis.md`, milník P1.
Pletor nezapisuje na plátno; záměr předá srdci a rozhodnutí zapíše do Schránky. Okno to ukazuje chipy provedených akcí.

Otevřenost okna se ukládá jednou pro aplikaci (`localStorage` `opora:pletor:v1`), nikdy per projekt. Projekt a prostor jsou jen kontext.

Dílky (`components/`):

- `PletorButton`: tlačítko v horní liště vedle Asistenta, otevře a zavře okno.
- `PletorWindow`: rodič. Drží stav konverzace a odesílá (`usePletor`); skládá dílky.
- `PletorHeartLine`: jeden řádek se stavem srdce a počtem čekajících eskalací.
- `PletorMessages`: zprávy, člověk vpravo, Pletor vlevo.
- `PletorActions`: po odpovědi chipy akcí (Poslal jsem srdci / Zapsal do Schránky / Selhalo).
- `PletorComposer`: pole a tlačítko Odeslat, Enter odešle.

Logika (`logic/`):

- `pletor-client.ts` (test vedle): `POST /api/pletor/messages`, `GET /api/pletor/state`, mapování odpovědi na texty okna, uložení otevřenosti.
- `pletor-poll.ts`: polling stavu každé 4 s, jen když je okno otevřené (sdílený `usePolling`), a odeslání zprávy.

Styl: `styles/pletor.css` (blok `pletor`, tlačítko `pletor__toggle`).

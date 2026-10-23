Brána vzdáleného přístupu: přihlašovací obrazovka, která stojí před `App`, když aplikace neběží na loopbacku, ale za tunelem.

- `logic/access-gate.ts` (+ test): čistá rozhodnutí — `needsGate(status)`, tolerantní `statusFrom`, `lockedOut` po HTTP 401, kontrola délky tokenu a jediný název události `opora:access-required`.
- `components/AccessGate.tsx`: při startu volá `GET /api/access/status`. Doma (`remote: false`) vykreslí rovnou `children`. Venku bez tokenu ukáže formulář a pošle `POST /api/access/login`; backend nastaví cookie `opora_access` (HttpOnly, Secure, SameSite=Strict) a stav se načte znovu.
- Odhlášení: venku s platným přihlášením (`canLogout(status)`) vykreslí `AccessGate` vedle `children` pilulku „Vzdálený přístup · host“ s tlačítkem **Odhlásit** → `POST /api/access/logout`, stav `lockedOut` a na formuláři věta `LOGGED_OUT_NOTICE`. Doma se neukáže.
- `api()` v `frontend/shared/types/logic/types.ts` při 401 pošle `opora:access-required`, takže se brána vrátí i uprostřed práce.

Token se nikdy neukládá do `localStorage` ani do URL; drží ho jen cookie prohlížeče. Kontext a důvody: `docs/vzdaleny-pristup.md`.

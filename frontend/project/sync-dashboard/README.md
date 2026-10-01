# sync-dashboard

Celkový pohled na proces jednoho projektu na stránce projektu: co je zelené, co čeká na 1:1, co
blokuje a proč. Kontrakt je `docs/synchronizace-pravdy.md`, části 5 (stavy a barvy), 8 (verdikt
Oracle) a 9 (dashboard projektu). Data přijdou hotová v props z `GET /api/sync-report`; napojení
(fetch, obnova) dělá rodičovská stránka, tento dílek jen zobrazuje.

- `logic/sync-dashboard.ts` — čisté funkce a typy nad `SyncReport` z `@/shared/desktop-state/logic/types`.
  `dashboardView(report, names)` složí `DashboardView` (`null`, když report ještě nedorazil):
  - `rows` — jeden `ScopeRow` na verdikt (oblast, sektor, nebo uzel), seřazený tak, aby nahoře bylo,
    co blokuje: nejdřív `waiting`, pak `draft`, `green`, `closed`; uvnitř skupiny podle jména z mapy
    `names` (chybějící jméno nahradí `id` rozsahu). `failed` jsou názvy neprošlých kontrol, `nextStep`
    je první další krok verdiktu nebo `null`.
  - `totals` — počet řádků v každém ze čtyř stavů.
  - `bySeverity` — počet echa (`SyncSignal`) podle závažnosti (vysoká, střední, nízká).
  - `topSignals` — nejvýš pět typů echa, sestupně podle počtu, při shodě abecedně.
  - `observedAt`, `gitHead` — beze změny z reportu.
- `components/SyncDashboard.tsx` — dostane `{ view, onRefresh }`. Když je `view` `null`, ukáže jednu
  větu, že echo ještě není načtené. Jinak ukáže souhrn stavů, souhrn echa podle závažnosti, pět
  nejčastějších typů echa, přepínač „jen blokující“ (jediný vlastní stav dílku) a tabulku rozsahů se
  stavem, jménem, neprošlými kontrolami a dalším krokem. Tlačítko „Přepočítat“ jen volá `onRefresh`.
- `styles/sync-dashboard.css` — BEM blok `sync-dashboard`, tokeny z `frontend/app/styles/style.css`.

Co dílek nedělá: nic nenačítá ani neukládá, nevolá `fetch`, nezná projekt ani workspace a nečte
`sourceKind` — report a jména rozsahů sestaví a předá rodič.

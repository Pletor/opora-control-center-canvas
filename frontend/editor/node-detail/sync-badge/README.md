# sync-badge

Štítek verdiktu Oracle nad jedním uzlem: barva a věta odpovídají na jedinou otázku — smí se to
commitnout a smí to do mainu? Kontrakt je `docs/synchronizace-pravdy.md`, části 4 (brána 1:1), 5
(stavy a barvy) a 8 (verdikt Oracle).

- `logic/sync-badge.ts` — čisté funkce a typy dat z `GET /api/sync-report`: `pickVerdict(report,
  nodeId)` najde verdikt daného uzlu v reportu (`null`, když report, uzel nebo jeho verdikt chybí);
  `badgeView(verdict)` z něj složí `{ tone, label, detail, steps, checks }` — `green` = smí, sedí
  zadání i kód; `waiting` = čeká na 1:1 a detail řekne, kolik kontrol neprošlo (správný český tvar
  pro 1 / 2 až 4 / 5 a víc); `draft` a `closed` jsou tiché stavy bez poplachu; když `canMerge` i
  `canCommit` jsou nepravda a verdikt nese blokující echo vysoké závažnosti, tón je `red` a popisek
  „Nesmí se commitnout“ (uzavřený rozsah tuto podmínku nesplní, protože blokující echo nemá).
- `components/SyncBadge.tsx` — dostane hotové `{ view }` v props a nic jiného; když je `view` `null`,
  nevykreslí nic. Jinak ukáže puntík a popisek podle tónu, větu s detailem, seznam dalších kroků a
  tlačítko, které rozbalí/schová seznam všech kontrol brány s jejich stavem (prošla/neprošla) a
  signálem echa u té, co padla. Rozbalení je jediný stav, který dílek sám drží.
- `styles/sync-badge.css` — BEM blok `sync-badge`, čtyři varianty tónu (`--green`, `--amber`, `--red`,
  `--muted`) na puntíku a popisku.

Co dílek nedělá: nic nenačítá ani neukládá, nevolá `fetch`, nezná projekt ani workspace a nečte
`sourceKind` — report, uzel a jeho verdikt sestaví a předá rodič.

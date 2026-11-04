# Search design systému

Pole „Search“ nad menu Správy webu (kontrakt `docs/navrhy/2026-11-04-sprava-webu-design-system.md` §3, `image9.png`): hledá v rozepsaném dokumentu přes barvy, spacing, radius, stíny, typografické styly, komponenty a assety (jméno, usage, hodnota, ukázka, skupina, souhrn).

- `components/DsSearch.tsx`: pole a výsledky (druh, jméno, hodnota); klik hlásí `onPick(hit)`.
- `logic/search.ts` (+ test): `searchDesign(design, query)` → nejvýš 30 výsledků `{section, kind, label, detail, target}`; `target` je `data-testid` řádku, který sekce už vykresluje.
- `logic/use-highlight.ts`: rodič po přepnutí sekce najde `target`, posune ho doprostřed a na 2,4 s mu dá třídu `ds-search__hit` (bez animace při `prefers-reduced-motion`).

Dílek nic nemění: sekci přepíná a zvýraznění spouští rodič `SiteAdmin`.

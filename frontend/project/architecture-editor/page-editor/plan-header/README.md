# Hlavička plátna 2

Hlavička otevřené stránky (`docs/navrhy/2026-11-10-platno-2.md`).

- `components/PlanHeader.tsx`: název stránky, slot `tools` (žeton webu, Kopírovat zadání rozkladu), **Skenovat web** (`onScan`; okno a běh skenu skládá `PageEditor` z `../plan-scan/`, `scanBusy` tlačítko vypne, dokud sken běží nebo čeká na rozhodnutí), **Zkontrolovat plán** a stav stránky **Rozpracováno / Kompletní**. Zkontrolovat plán rozbalí pod hlavičkou `MapCheckPanel` (`../../domain-site/map-check/`) s dírami jen této stránky (`pageCheckGroups`, hotová data od `PageEditor`); klik na nález hlásí `onOpenFinding` (rodič otevře stránku a vybere prvek). Kompletní stránka zavřená pro úpravy (`sealed`) ukáže větu „Stránka je kompletní“ a **Otevřít k úpravám** (`onReopen`, zámek uvolní rodič pro toto sezení).
- `styles/plan-header.css`, předpona `plan-header`.

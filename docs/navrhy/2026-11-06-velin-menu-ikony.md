# Velín – levé menu s ikonami a zasunutím

Datum: 2026-11-06. Větev `feat/velin-menu` (dítě `feat/velin`), jen `frontend/agi-pletor/dashboard/`
(`PletorDashboard.tsx`, `logic/dashboard-route.ts`, `styles/pletor-dashboard.css`, README).

## Proč

Člověk: „Hlavní levé menu dej ikonky a možnost zajet, popisy zmizí, zůstane jenom úzký pruh ikonek.“ Obsah (Linie,
Dílna) potřebuje šířku.

## Co

1. `PARTS` dostane `icon` (jeden znak Unicode, bez knihovny): Přehled ◎, Mozek a LLM ⌬, Hlas ♪, Srdce ♥, Linie ⎇,
   Podklady ▤, Dílna ⚒, Monitoring ◔, Rozhovor ✉, Nastavení ⚙.
2. Každá záložka = ikona + popis. Tlačítko nahoře v navigaci `‹ Zasunout` / `›` přepíná `.pletor-dashboard--narrow`:
   sloupec 200 px → 52 px, popisy `display: none`, ikona vycentrovaná, popis zůstává v `title` a `aria-label`.
   Záložka má vždy `aria-label` = popis, aby čtečka četla totéž v obou stavech.
3. Stav v `localStorage` klíč `pletor.nav` (`"narrow"` / chybí) – jedno nastavení pro aplikaci, ne per projekt.
   Logika čtení/zápisu v `logic/dashboard-nav.ts` (čistá: `readNarrow(storage)`, `writeNarrow(storage, narrow)`), test vedle.
4. Klávesa `[` přepíná zasunutí, když fokus není v poli (stejná ochrana jako Esc v `PletorDashboard`).

## Ověření

`npx vitest run frontend/agi-pletor/dashboard`, `npm run build`, živě: zasunout → 52 px pruh ikon, obnovit stránku →
stav drží, `title` na ikoně ukáže popis.

## Mimo rozsah

Přeskupení částí, nové části, ikony v kokpitu.

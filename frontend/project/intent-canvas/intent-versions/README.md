# Lišta verzí záměru

`IntentVersionBar` ukazuje tři místa: aktivní verzi, kandidáta a rozpracovaný draft novější než oba (prázdné místo jako pomlčka). Vedle je rozdíl zobrazené verze proti aktivní („+2 přidáno · −1 odebráno · ~1 změněno“) a akce: Uložit draft / Zahodit u neuložené úpravy, Navrhnout ke schválení u draftu, Schválit a Zamítnout (s povinným důvodem) jen u kandidáta. Data a zápis drží rodič `IntentCanvas`; lišta si drží jen rozepsaný důvod zamítnutí.

- `logic/intent-versions.ts` (+ test): `intentLane`, `pickIntentVersion`, `diffToActive`, `diffCounts`, `diffText`.
- `styles/intent-versions.css`, předpona `intent-versions`.

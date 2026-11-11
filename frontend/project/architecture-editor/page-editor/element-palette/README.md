# Prvky logiky

Dílek levého panelu plátna 2 ve vrstvě **2 Logika** (`docs/navrhy/2026-11-10-platno-2.md`). Druhy `element` seskupené podle otázky člověka: **Kdo** (Uživatel `actor`), **Kdo smí** (Přístup), **Co musí splnit** (Podmínka, Omezení), **Co se děje** (Akce, Proces, Formulář), **S čím** (Data, Úložiště), **Napojení** (Služba, Vstup, Výstup, Událost, API kontrakt).

- `logic/logic-groups.ts` (test vedle): `LOGIC_GROUPS` (popisky plátna 2; Editor má dál své `ELEMENT_GROUPS`) a `logicLook(kind)`, popisek a symbol štítku prvku na plátně.
- `components/ElementPalette.tsx`: klik hlásí `onInsert(kind, label)` (prvek celé stránky), stisk `onCarry(kind, label, event)` začne tah do boxu nebo na pruh Celá stránka. Nic neukládá; vloží `ArchitectureEditor` přes `/api/canvas-plan`.
- `styles/element-palette.css`, předpona `element-palette`.

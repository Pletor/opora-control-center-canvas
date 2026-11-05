# Úvod Opory — milník 1

Samostatný animovaný vstup na `/` a `/?screen=intro`. Orb používá přímo PletorHudCanvas ve stavu idle, neznázorňuje dostupnost modelu. Barvy sdílí z pletor.css a typografii ze základních tokenů Opory. Animaci lze pozastavit a respektuje `prefers-reduced-motion`. Na mobilu jsou vstupy pod sebou.

`Entry` načítá pracovní aplikaci líně až po vstupu; úvod nevolá model, mikrofon ani projektová API. AccessGate zůstává před vstupem. Existující přímé odkazy na projekty a plátna pokračují do App.

Tři funkční vstupy pro tento milník:
- Pletor: existující konverzační HUD (`screen=home&entry=pletor`).
- Nastavení: celostránková globální administrace Pletoru a srdce (`screen=settings`).
- Projekty: současný seznam repozitářů (`screen=home`).

Návrat ze seznamu projektů přes menu Opora → Úvod Opory. Přechody jsou běžné odkazy. Návrat se nenabízí uvnitř editoru s rozpracovanými změnami.

Další milníky: samostatná globální administrace Pletoru a srdce. Jedno srdce napříč projekty, Pletor přijímá vizi člověka a předává zadání srdci. Srdce provádí research, ověřování a rozpad na úkoly. Design systém (brand, CX/UI/UX) vlastní každý projekt. Tento milník nemění backend ani projektové vlastnictví současného plátna 1.

Ověření: `npx vitest run frontend/app/intro/logic/entry-route.test.ts`, `npm run build`; v prohlížeči tři vstupy, návrat, mobil, klávesnice a omezený pohyb.

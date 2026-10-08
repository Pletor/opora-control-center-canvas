# Uložit vše a historie

Kontrakt a rozsah obnovy: `docs/verze-platna.md`.

`SaveVersionsTools` skládá Historii uložení a Uložit vše v horní liště za Asistentem. App poskytuje aktuální projekt/pracovní prostor, omezení zápisu a koordinuje dokončení konceptů před vytvořením verze. Nástroje jsou dostupné napříč pohledy projektu; main pouze pro čtení nelze měnit.

`use-canvas-versions` čte serverový stav a token pracovního prostoru. Pro obnovu používá token stavu, který uživatel potvrdil; konflikt nesmí zakrýt načtením nového tokenu těsně před zápisem. Historie uvádí omezení starých verzí a společného cíle projektu.

Sdílený `shared/hooks/logic/save-coordinator.ts` registruje skutečné editory, koncepty a probíhající zápisy. Nevlastní druhou kopii obsahu. Chyba nebo formulář vyžadující výslovné dokončení blokuje oznámení úspěšného uložení. Ctrl+S / ⌘S používá stejný řetězec jako tlačítko.

Po obnově App zahodí již vyřešené místní cache, znovu načte editory a upraví neplatný výběr. `save-versions.ts` obsahuje čisté formátování data, autorů a stavů tlačítek; styl feature je v `styles/save-versions.css`.
# Rešerše

Samostatný tematický canvas mezi Velínem a Textem. Srdce ukládá zjištění přes `/api/research`; UI čte hlavičky a významové hrany, úplný obsah teprve při výběru. Zdrojový kontrakt: `docs/navrhy/2026-11-08-reserse.md`.

- `logic/research-api.ts`: autentizovaný klient, oddělení projektu/prostoru, čtení revizí a archivace s očekávanou revizí.
- `logic/use-research.ts`: pollování přehledu, ochrana před starými odpověďmi, samostatné načítání detailů kartiček a hran.
- `logic/research-model.ts`: tematické filtry, deterministické rozmístění, bezpečné odkazy a rasterové podklady.
- `components/ResearchWorkspace.tsx`: propojené kartičky, hlavičky, filtry a výběr; `ResearchInspector.tsx`: plný text, ověření, citace, historie a význam přechodu.

`refs.attachmentIds` mohou označovat soubory existujícího Kreslení (`DrawingFile.id`). Náhled načítá `/api/drawing-files` ve stejném projektu a efektivním pracovním prostoru. Neznámé ID se zachová jako nedostupný podklad. Odkaz Kreslení u připojeného uzlu otevírá jeho vrstvu; nepředstírá výběr konkrétního elementu. Samotný screenshot nedokládá implementaci backendu.

API může přeložit `main` na aktivní pracovní prostor. UI uvádí efektivní prostor a používá ho pro detail, přílohy i archivaci. Změna projektu/prostoru remontuje pracovní plochu. Historie kartiček zobrazuje tehdejší obsah a současné vazby (výslovně označeno); historie hran zobrazuje původní význam a důvody. Rozhodnutí samo o sobě není dokladem schválení člověkem.

Ruční změna obsahu není součástí této obrazovky; primárním autorem je srdce. Člověk může archivovat či obnovit kartičku nebo vazbu. Nedochází k mazání zjištění. Poloha je odvozena z významového grafu, nevytváří kopii struktury projektu.

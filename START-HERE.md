# Opora Control Center — začni zde

## Jedna primární aplikace

Tento adresář `Opora-control-center-canvas` je jediný aktivní kořen aplikace. Rozhodnutí uživatele: 2026-09-09. Nevytváříme další paralelní varianty produktu.

- Aplikace: **http://127.0.0.1:8740/**
- Instalace a spuštění: [README.md](README.md).
- Schválený směr vývoje: [EDITOR-SPEC.md](docs/source-synthesis/2026-09-09/EDITOR-SPEC.md).
- Zpracované podklady a mapa: [přehled syntézy](docs/source-synthesis/2026-09-09/README.md).
- První rozpracovaný řez: **R01 — editor zadání uzlu**, podklady a výsledek v [.opora/workunits/WU-R01/RESULT.md](.opora/workunits/WU-R01/RESULT.md). Editor je implementovaný a testovaný; další moduly přibývají po ověřených řezech.

## Nově: pracovní módy

**Struktura / Kreslení / Mapa** vlevo, **Nastavení plochy** nahoře. Kresby jsou samostatné pro každou vrstvu a mají ruční ukládání; Mapa používá skutečný graph a exportuje pro Archify. [Ovládání a důkazy](.opora/workunits/WU-MODES-01/RESULT.md).

## Nově: odstranění vložených položek

Uzel/sektor/vazbu smažeš z detailu s potvrzením dopadu; repozitář odebereš horním tlačítkem. GitHub a lokální soubory se nemažou. [Ovládání a důkazy](.opora/workunits/WU-DELETE-01/RESULT.md).

## Co patří kam

| Obsah | Umístění uvnitř tohoto kořene |
|---|---|
| Python backend | `backend/` |
| React frontend | `src/` |
| Automatické testy | `tests/`, `e2e/` |
| Návrh a zdrojové rozbory | `docs/` |
| Přesná zadání implementačních řezů a provenance | `.opora/workunits/` |
| Skutečná lokální data | `.data/production/` |
| Důkazy provedených testů | `evidence/` |
| Sestavený klient, generovaný z frontend zdrojů | `dist/` |

Technické podsložky nejsou další aplikace. Případné pracovní kopie agentů mají být pouze uvnitř tohoto kořene, nikoli dalšími primárními projekty vedle něj.

Starší sourozenecké projekty `OporaCC` a `OporaCC-v3` nejsou aktivní vývoj této aplikace. Zůstávají zachované; tento řez je nemaže ani nepřesouvá. Archify, Excalidraw, Logseq, Open Note, Tuval a OpenViking jsou referenční zdroje, nikoli další části, které by bylo nutné samostatně spouštět pro základní editor.

## Pravidla společného vývoje

- Rozšiřujeme fungující aplikaci, neděláme další blanket rewrite.
- Jeden přesný pracovní řez, jeden writer, testy před kódem a skutečné ověření výsledku.
- Goaly a podklady postupně přejdou do editoru; dnešní soubory nejsou tvrzením, že už je celý kontextový systém implementovaný.
- Automatické připojení skutečného projektu, placený běh agenta, push ani merge nevzniká pouhým otevřením aplikace.
- Originální podklady a předchozí historii zachováváme.

# Opora Control Center — začni zde

## Jedna primární aplikace

Tento adresář `Opora-control-center-canvas` je jediný aktivní kořen aplikace. Rozhodnutí uživatele: 2026-09-09. Nevytváříme další paralelní varianty produktu.

- Aplikace: **http://127.0.0.1:8740/**
- Instalace a spuštění: [README.md](../README.md).
- Směr vývoje: konkrétní kroky vznikají při praktickém vývoji. Dřívější plány, koncepty a LLM/Hermes běhy byly odstraněny 2026-09-13; základ je funkční editor plátna s Podklady pro agenta (náhled, neměnný snímek, export pro externího agenta).

## Nově: pracovní módy

**Struktura / Kreslení / Mapa** vlevo, **Nastavení plochy** nahoře. Kresby jsou samostatné pro každou vrstvu a mají ruční ukládání; Mapa používá skutečný graph a exportuje pro Archify. Ovládání a důkazy: WU-MODES-01 (historické zadání, odstraněno při restrukturalizaci 2026-09-13).

## Nově: odstranění vložených položek

Uzel/sektor/vazbu smažeš z detailu s potvrzením dopadu; repozitář odebereš horním tlačítkem. GitHub a lokální soubory se nemažou. Ovládání a důkazy: WU-DELETE-01 (historické zadání, odstraněno při restrukturalizaci 2026-09-13).

## Co patří kam

| Obsah | Umístění uvnitř tohoto kořene |
|---|---|
| Python backend | `backend/` |
| React frontend | `frontend/` |
| Automatické testy | vedle testovaného kódu: `backend/**/tests/`, `tools/tests/` |
| Návrh a zdrojové rozbory | `docs/` |
| Pravidla umístění souborů | `docs/pravidla-struktury.md` |
| Skutečná lokální data | `.data/` (gitignored) |
| Sestavený klient, generovaný z frontend zdrojů | `dist/` |

Technické podsložky nejsou další aplikace. Případné pracovní kopie agentů mají být pouze uvnitř tohoto kořene, nikoli dalšími primárními projekty vedle něj.

Starší sourozenecké projekty `OporaCC` a `OporaCC-v3` nejsou aktivní vývoj této aplikace. Zůstávají zachované; tento řez je nemaže ani nepřesouvá. Archify, Excalidraw, Logseq, Open Note, Tuval a OpenViking jsou referenční zdroje, nikoli další části, které by bylo nutné samostatně spouštět pro základní editor.

## Pravidla společného vývoje

- Rozšiřujeme fungující aplikaci, neděláme další blanket rewrite.
- Jeden přesný pracovní řez, jeden writer, testy před kódem a skutečné ověření výsledku.
- Goaly a podklady postupně přejdou do editoru; dnešní soubory nejsou tvrzením, že už je celý kontextový systém implementovaný.
- Automatické připojení skutečného projektu, placený běh agenta, push ani merge nevzniká pouhým otevřením aplikace.
- Originální podklady a předchozí historii zachováváme.

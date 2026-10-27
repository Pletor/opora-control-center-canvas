# Opora Control Center — začni zde

## Jedna primární aplikace

Tento adresář `Opora-control-center-canvas` je jediný aktivní kořen aplikace. Rozhodnutí uživatele: 2026-09-09. Nevytváříme další paralelní varianty produktu.

- Aplikace: **http://127.0.0.1:8740/**
- Spuštění: `uv run opora` (nastavení v [opora.toml](../opora.toml)); instalace viz [README.md](../README.md).
- **Jak vyvíjet projekt (zadání v OPORA → agenti ve VS Code → GitHub):** [postup-vyvoje-projektu.md](postup-vyvoje-projektu.md).
- Směr vývoje: konkrétní kroky vznikají při praktickém vývoji. Dřívější plány, koncepty a LLM/Hermes běhy byly odstraněny 2026-09-13; základ je funkční editor plátna s Podklady pro agenta (náhled, neměnný snímek, export pro externího agenta).

## Nově (2026-10-27): mapa architektury jako harness agentů

Stránka nese cíl, působení a sekce, aplikace cesty zákazníka jako trychtýř stránek (role, zážitek, počet lidí), vazby druh toku (`carries`); agent dostane
výřez mapy v `node-brief.architecture`, kontrola mapy najde díry bez modelu a cesta je brána hotovo.
Kontrakt a etapy: `docs/architektura-pro-agenty.md`.

## Nově (2026-10-15): pyramida a velín

Člověk píše **záměr oblasti** a potvrzuje dávky; agenti rozkládají oblast → sektory → karty (`docs/pyramida.md`).
Mód **Velín** (dřív Mapa) ukazuje celou pyramidu se stavem procesu a jednu frontu „Čeká na tebe“ s přímým
potvrzením. Karta nese kuličky procesu; dvojklik na ni otevře jednotný detail karty (Zadání · Kroky · Běh · Review & PR · Historie),
v inspektoru je „Rozložit na karty“ a
„Shrnout podněty“ (sektor), „Rozložit na sektory“ (oblast). Kde co žije a odkud se řídí: `docs/rizeni-vyvoje-z-karty.md`.
Nepoužívané formuláře karty (fáze, kritéria, kroky, scénář, fakta, design) jsou smazané podle měření na živých datech.

## Nově: pracovní módy

Kresby jsou samostatné pro každou vrstvu a mají ruční ukládání; obrázky (screenshot Ctrl+V, přetažení, nástroj Obrázek) se ukládají s kresbou. Mapa projektu (Graphify-out v prostředí Projekt) se po mergi do main sama přepíše na místě v `graphify-out/` hlavního projektu, viz [mapy-projektu.md](mapy-projektu.md). Nastavení je vlevo dole.

## Nově: odstranění vložených položek

Uzel/sektor/vazbu smažeš z detailu s potvrzením dopadu; repozitář odebereš horním tlačítkem. GitHub a lokální soubory se nemažou. Ovládání a důkazy: WU-DELETE-01 (historické zadání, odstraněno při restrukturalizaci 2026-09-13).

## Co patří kam

| Obsah | Umístění uvnitř tohoto kořene |
|---|---|
| Python backend | `backend/` |
| React frontend | `frontend/` |
| Automatické testy | hned vedle testovaného modulu jako `test_<modul>.py` (backend, tools) |
| Návrh a zdrojové rozbory | `docs/` |
| Pravidla umístění souborů | `docs/pravidla-struktury.md` |
| Skutečná lokální data | `.data/` (gitignored) |
| Sestavený klient, generovaný z frontend zdrojů | `dist/` |

Technické podsložky nejsou další aplikace. Případné pracovní kopie agentů mají být pouze uvnitř tohoto kořene, nikoli dalšími primárními projekty vedle něj.

Starší sourozenecké projekty `OporaCC` a `OporaCC-v3` nejsou aktivní vývoj této aplikace. Zůstávají zachované; tento řez je nemaže ani nepřesouvá. Excalidraw, Logseq, Open Note, Tuval a OpenViking jsou referenční zdroje, nikoli další části, které by bylo nutné samostatně spouštět pro základní editor.

## Pravidla společného vývoje

- Rozšiřujeme fungující aplikaci, neděláme další blanket rewrite.
- Jeden přesný pracovní řez, jeden writer, testy před kódem a skutečné ověření výsledku.
- Goaly a podklady postupně přejdou do editoru; dnešní soubory nejsou tvrzením, že už je celý kontextový systém implementovaný.
- Automatické připojení skutečného projektu, placený běh agenta, push ani merge nevzniká pouhým otevřením aplikace.
- Originální podklady a předchozí historii zachováváme.

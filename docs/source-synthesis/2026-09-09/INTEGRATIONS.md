# Výběr ze šesti lokálních produktů

Datum: 2026-09-09. Rozhodnutí jsou doporučení; žádná knihovna ani externí služba tím nebyla zapojena do běžícího Canvasu.

## Rozhodovací matice

| Zdroj | Co převzít | Preferovaná forma | Co nyní nepřevzít | Licenční brána |
|---|---|---|---|---|
| Archify | čitelný systémový diagram ze strukturované specifikace, validace, explorable view | odvozený export/projekce vlastního modelu | samostatná konkurenční graph authority | MIT; zachovat podmínky a attribution |
| Excalidraw | kvalitní ruční diagram a image/shape editing | lazy-loaded React component uvnitř uzlu | celou excalidraw.com aplikaci a její cloud/collaboration stack | MIT; prověřit vybrané dependency a verzi |
| Logseq | outliner, identity bloků, backlinks, graph query, single writer | vlastní strukturální model a UX principy; později explicitní import | Clojure/Electron/cloud runtime jako povinný základ OporaCC | AGPLv3; žádný přímý copy kódu bez rozhodnutí |
| Open Note | integraci poznámky, dokumentu, kresby a znalostních vazeb | principy jednotného editoru a propojení podkladů | education-first workflow, cloud auth/billing, kopii frontendu | PolyForm Noncommercial 1.0.0; nepřebírat kód pro produkční/commercial produkt bez potřebných práv |
| Tuval | prostorový systém sémantiky, export graph traversal, mapování diagramu na kontext | vlastní sémantický kontrakt; optional import/read-only adapter po probe | celou aplikaci, její provozní stack a předpoklad live viditelnosti neuloženého UI | AGPLv3; přímé reuse a způsob distribuce musí být rozhodnuty |
| OpenViking | L0/L1/L2, adresovatelný kontext, retrieval trace, freshness, zkušenosti | local-first memory interface; optional separátní retrieval adapter | automatické ingest všech souborů/chatů, povinné embedding API, automatické přepisování autoritativní paměti | tato lokální verze AGPLv3; integrace oddělené služby není automatické vyřešení licence |

Zdroje funkcí a hranic: Archify PRODUCT.md ř. 7–25; Excalidraw README ř. 52–106 a package manifest; Logseq codebase a runtime guide ř. 24–65; Open Note architecture ř. 23–185; Tuval agents/MCP docs; OpenViking concepts.[2][4][5]

Logseq výslovně popisuje graph worker jako autoritu a renderer jako klienta, ne druhého writera.[7][8]

Open Note popisuje integrovaný workspace pro poznámky, kresby a další vzdělávací materiály; jeho konkrétní produktový stack není požadavkem OporaCC.[10][11]

Tuval rozlišuje AI kontext/export i snapshot-based MCP přístup; to je inspirace, nikoli doložené bezproblémové napojení.[13][14][15]

OpenViking popisuje vrstvené souhrny a session memory extrakci, včetně změn existujících memories.[17][18][19]

Licenční identifikace pochází přímo z lokálních LICENSE souborů: MIT pro Archify/Excalidraw; AGPLv3 pro Logseq/Tuval/OpenViking; PolyForm Noncommercial pro Open Note.[3][6][9]

Další licenční doklady pro Tuval, OpenViking a Open Note jsou samostatně registrované; rozhodnutí o konkrétní distribuci, síťovém zpřístupnění a komerčním použití vyžaduje posoudit skutečný způsob integrace, nikoli pouze tuto tabulku.[12][16][20]

## Doporučení: kompozice schopností, ne slepení produktů

Jádro editoru a sémantický model zůstanou OporaCC. Excalidraw bude vložený nástroj kresby, Archify odvozený čtecí/exportní pohled. Logseq a Tuval poskytují principy orientace a sémantiky; nepřebírat současně jejich persistence autority. OpenViking je vyměnitelný backend retrieval, nikoli vlastník goalů, approval nebo WorkUnit lifecycle. Open Note je nyní jen inspirační zdroj.

Ani volná čára v Excalidraw, ani box Archify nesmí potichu změnit závislost ve významovém grafu. Import je nejprve návrh mapování s diffem a konflikty; UI ukazuje, co se stane s ID, vztahy a podklady.

## Co přesně je ověřeno

- Existence všech šesti uvedených lokálních repozitářů, čtené dokumenty, jejich hashe a licence v kontrolované kopii.
- Archify a Tuval měly při čtení lokální změny. Jejich uvedený Git HEAD tedy není vydáván za přesný obsah všech pracovních souborů; rozhodují také hashe v `reference-sources.json`.
- Neověřena běžící API těchto produktů, jejich výkon, aktuální cloud tarify, compliance celé dependency closure, importní kompatibilita ani integrace do OporaCC.
- Žádný ze šesti zdrojových projektů se v této syntéze nemění, nespouští ani nemaže.

## Capability probe před konkrétním reuse

Každý budoucí adapter má malý spike: přesná verze a licence → minimální resource fixture → import/export či tool call → korelace revize → změna/restart/error → skutečné měření času a dat → rozhodnutí použít/odložit. Dokud probe neprojde, status je UNVERIFIED; editor na něm při startu nesmí záviset.

## Sources

[2] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/archify/PRODUCT.md — archify/PRODUCT.md
[3] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/archify/LICENSE — archify/LICENSE
[4] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/excalidraw/README.md — excalidraw/README.md
[5] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/excalidraw/packages/excalidraw/package.json — excalidraw/packages/excalidraw/package.json
[6] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/excalidraw/LICENSE — excalidraw/LICENSE
[7] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/logseq/CODEBASE_OVERVIEW.md — logseq/CODEBASE_OVERVIEW.md
[8] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/logseq/docs/agent-guide/implemented/architecture/2026-08-24-logseq-runtime-and-engineering-guide.md — logseq/docs/agent-guide/implemented/architecture/2026-08-24-logseq-runtime-and-engineering-guide.md
[9] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/logseq/LICENSE.md — logseq/LICENSE.md
[10] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/open-note/README.md — open-note/README.md
[11] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/open-note/docs/architecture.md — open-note/docs/architecture.md
[12] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/open-note/LICENSE.md — open-note/LICENSE.md
[13] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/README.md — tuval/README.md
[14] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/docs/agents.md — tuval/docs/agents.md
[15] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/docs/mcp.md — tuval/docs/mcp.md
[16] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/02.Opora-control-center/tuval/LICENSE — tuval/LICENSE
[17] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/README.md — OpenViking/README.md
[18] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/docs/en/concepts/03-context-layers.md — OpenViking/docs/en/concepts/03-context-layers.md
[19] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/docs/en/concepts/08-session.md — OpenViking/docs/en/concepts/08-session.md
[20] file:///P:/0.%20OSVC/8.%20Code/07.%20Aplikace/03.Agents-tools/OpenViking/LICENSE — OpenViking/LICENSE

Podklady pro agenta: složení uzlu (text, zadání, kresby, dokumentace, paměť) do packetu opora.packet/1, neměnný snímek, redakce tajemství (desktop_v3_packets.py, redact.py).
Balíček celé karty pro model: cíl, definice hotovo, hranice, kontext, harness, bloky s porty, graf a smyčka v jednom JSON opora.node-brief/1 (node_brief.py).
Karta vložená z knihovny nese v `node` navíc `fetch` (co si stáhnout do kontextu) a `fill` (která pole karty vyplnit), jen když jsou; mimo `specification`, takže `contextVersion` nemění (test_node_brief_agent_context.py, docs/zive-zobrazeni-a-knihovna.md §5).
Fraktální předávka v balíčku: pracovní prostor karty i okolí (vazby celý, potomci/rodič/oblast jen rámec a předávka) a odkaz na mapu Graphify v context.knowledgeGraph (node_brief.py).

`loop.openBlocks` počítá všechny nesplněné bloky (`open`, `unmet`, `blocked`). `loop.waitingOnHuman`
vypisuje bloky `blocked` jako `{blockId, ask}`: poznámku posledního výstupu agenta, jinak podmínku
nebo název bloku. Poznámka je v `block.state.note`, nemění verzi zadání. Stav `blocked` používej
pro čekání na zásah člověka; nesplněná kontrola, kterou může agent dál řešit, je `unmet`.

`boundaries.effectiveRules` obsahuje účinná projektová, cestová, adresná i lokální pravidla
karty a všech jejích předků. Každé nese `origin {scope, nodeId, name, path, storage}` a `inherited`.
`scope` rozlišuje projekt, cestu, sektor a kartu; `storage` rozlišuje projektovou a lokální
kolekci (ID lokálních pravidel se mohou opakovat). Zákazy předků se zahrnují i do stop podmínek.
Původní `nodeRules` a `projectRules` zůstávají kompatibilní. Plátno zobrazuje stejný původ ikonami.

Odvozené pohledy (`sector_status`, `sector_blockers`, `frontier`, `work_overview`, `checklists`) počítají předky a vazby jednou za dotaz přes indexy (`sector_ancestry`, `SectorEdges`, `FrontierIndex`, `EdgeIndex`) a zadání s texty čtou dvěma hromadnými dotazy. Výstup je stejný jako dřívější procházení všech dvojic; hlídá to `test_derived_views_equivalence.py` (oprava 7 v docs/navrhy/2026-10-14-vykon-platna.md).
Balíček nese `run` (štítek, úsilí, model, poradce, `handout`, `humanReview`) z kroků zadání karty a grafu, stejný výpočet jako `run` v zadání běhu (`backend/canvas/card_gauge.py`, docs/navrhy/2026-10-30-metriky-a-spoustece.md §3); mimo `specification`, takže `contextVersion` nemění.

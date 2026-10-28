# Plánovač: projekt → vrstvy a sektory → karty → kroky, vše jako návrhy změn

Kdy mě číst: rozkládáš projekt nebo sektor na karty, píšeš `spec.steps`, měníš zadání přijaté
karty nebo vazby `next`. Plán mění **jen návrh změny** (changeset); přijímá ho vždy člověk.
Kontrakty: `docs/oporahub.md` (změny zadání), `docs/oporahub-graph-proposals.md`,
`docs/oporahub-graph-changes.md`, `docs/oporahub-content-changes.md`. Recept rozkladu oblasti
(mapa kódu, 2–7 sektorů, `[gate]`) zůstává v [rozklad.md](rozklad.md).

## Postup

1. **Stav a hlava.** `opora_hub.py state` (`heads.acceptedHead`, `graphDigest`); kontext návrhů
   `GET /api/oporahub/graph-proposals/context` a `GET /api/oporahub/changesets/context`.
   Bez přijatého grafu plánu nic nepřevezmeš (běh v2 vrátí `409 graph_acceptance_required`): první ready akce je
   `propose_graph` (prázdný návrh převezme pracovní graf i zadání karet), pak její `accept`; přijímá člověk, při
   `autonomy.full` agent (`opora_hub.py act --action-id ID`). `accept_baseline` (jen zadání) je starší cesta.
2. **Vrstvy a sektory.** Rozděl projekt na vrstvy (např. `db`, `be`, `fe`, `infra`, `docs`)
   a uvnitř na sektory (uzel `kind: "sector"`); sektor = jedna odpovědnost s vlastním cílem.
3. **Karty.** Karta = uzel `kind: "node"` s rodičem `parent` (sektor). Druh i vrstvu uváděj výslovně:
   `kind` uzlu vždy; vrstvu karty (`cards[].layer`) server odvodí z rodičovského sektoru.
4. **Zadání karty.** `spec: {goal, non_goals, acceptance}`: jeden cíl, co výslovně ne, testovatelné
   podmínky hotovo. Plus `spec.steps`, viz níže.
5. **Závislosti.** Vazby `{from, to, port: "next"}` (volitelně `carries`: `navigation | data | command | event`,
   jen když víš, co po vazbě teče) tvoří **DAG**: cyklus server odmítne (409
   `card_cycle` s `cycle` = uzavřená cesta karet). Karta se odblokuje až po merge a zápisu do plánu všech předchůdců.
6. **Návrh.** Nové uzly a vazby: `POST /api/oporahub/graph-proposals` (`parentRevision`,
   `expectedGraphDigest`, `subject`, `plan: {nodes, edges}`; ≤ 200 uzlů, 600 vazeb). Změna
   zadání existujících karet: `POST /api/oporahub/changesets` (`parentRevision`,
   `expectedGraphDigest`, `subject`, `changes: [{nodeId, expectedRevision, fields}]`, plná pole).
   Úprava nebo odstranění existujících uzlů: [změny grafu](../../../../docs/oporahub-graph-changes.md).
7. **Předej člověku.** Návrh nic nemění; agent-state ukáže akci `accept` (`human_only`) a rozhodnutí.
   Nečekej v cyklu: skonči s ID návrhu. Zastaralý návrh převede server sám ([conflicts.md](conflicts.md)).

```bash
python "<SKILL_DIR>/scripts/opora_write.py" /api/oporahub/graph-proposals --project P --workspace W --json-file plan.json
```

## `spec.steps`

```json
{"steps": [
  {"id": "s1", "order": 1, "title": "Parser DOCX vrací prostý text", "kind": "code",
   "files": ["backend/ingest/docx.py"], "dependsOn": [],
   "acceptance": ["uv run pytest backend/ingest -k docx_text projde"]},
  {"id": "s2", "order": 2, "title": "Test na vzorovém dokumentu", "kind": "test",
   "files": ["backend/ingest/test_docx.py", "backend/ingest/fixtures/*.docx"], "dependsOn": ["s1"],
   "acceptance": ["nový test selže bez s1 a projde s ním"]}]}
```

- Pole: `id` (`s1`…, jedinečné), `order` (celé číslo), `title`, `acceptance` (≥ 1), `dependsOn`
  (existující ID), volitelně `kind` (`code|test|docs|design|research`) a `files` (globy).
- Server ověří: jedinečná ID, existující `dependsOn`, acyklický DAG kroků, `order` souhlasí
  s topologickým pořadím. Kroky jdou v `fields.steps` návrhu změny zadání; při slučování se
  porovnávají po `id` kroku (dva návrhy měnící různé kroky se nesrazí).
- Kroky jsou součástí přijaté revize a neměnného snímku běhu; průběh (`stepResults`) ne.
- Stará karta s `steps`/`criteria` nebo podmínkami bloků dostane **návrh** kroků k přijetí, nic se nepřijme samo.

## Kontrolní seznam kvality plánu kroků

Projdi každou kartu před odesláním návrhu. Jedno „ne“ = přepiš.

| Otázka | Proč |
|---|---|
| Má krok **jeden** výsledek, popsatelný jednou větou bez „a“? | dva výsledky = dva kroky |
| Je každá `acceptance` **ověřitelná příkazem nebo pozorováním** (test, build, výstup, snímek)? | „funguje dobře“ nejde ověřit |
| Vejde se krok do **~1 h** práce agenta? | větší krok rozděl; menší než ~10 min slouč |
| Má krok **výslovné `files`**, a jsou úzké? | agent ví, kam smí; review vidí rozsah |
| Je každá závislost v `dependsOn`, žádná **skrytá** („předpokládá, že…“)? | skrytá závislost = pád v cizím kroku |
| Jdou kroky bez sdíleného stavu dělat ve vyznačeném pořadí bez dotazu člověka? | otázka patří do `research` kroku nebo karty |
| Je první krok malý a ověří předpoklad (spike, failing test)? | levné selhání na začátku |
| Má poslední krok `acceptance` karty (integrační test, build)? | karta = součet kroků + vlastní acceptance |
| Nepoužívá krok vágní slova (vylepšit, doladit, refaktor obecně, „podle potřeby“)? | nejednoznačné = neověřitelné |
| Odkazují `files` a příkazy na **existující** cesty a skripty (nebo krok tu cestu zakládá)? | žádné vymyšlené cesty |
| Je karta bez kroků, které patří jiné kartě nebo vrstvě? | míchání vrstev = velký diff a konflikty |
| Je mezi kartami `next` DAG bez cyklu a s nejkratší kritickou cestou? | paralelní práce a jasné odblokování |

## Nález během práce

Agent při běhu plán nemění. Nález (chybějící krok, špatná acceptance, nová karta) vrať jako
návrh změny nad aktuální `acceptedHead` a zmiň jeho ID v `notes` kroku a v `summary` výsledku.

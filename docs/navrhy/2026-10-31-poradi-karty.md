# Pořadí karty podle záměru

**Stav: návrh ke schválení člověkem (2026-10-31).** Podklad: Ample. Záměr člověka (návrh „AmpleLab – platforma
znalostí a chatbota“, 7 fází) určuje pořadí obrazovek, ale mapa ho neumí vyjádřit. `topoIndex` v agent-state
vzniká jen z vazeb `next` (`card_dag.topo_order`, Kahn) a remízu láme **id karty** (UUID), takže karty bez vazby
stojí v náhodném pořadí. Srdce je přeřadit nemůže: vazba `next` je závislost (blokuje následníka, dokud
předchůdce není sloučený a zapsaný zpět) a návrh grafu od srdce smí u existujícího uzlu měnit jen `memberOf`
(`opora_graph_change_plan.heart_scope`).

Bez změny schématu tabulek (pole žije v JSON uzlu grafu), bez zásahu do brány uzavření karty, do vazeb a
blokování a do dat v `P:\opora-data` mimo API.

## 1. Pole `order` uzlu

- Nepovinné celé číslo `1…9999` u uzlu `kind` `node` nebo `sector`. Jiný druh nebo hodnota → uložení mapy
  odmítne (`graph.validate_graph`, stejně jako `memberOf`).
- Význam: pořadí podle záměru, **ne závislost**. Nic neblokuje, nemění `blockedBy`, claim ani bránu.
- Doporučený zápis fáze a pozice: `fáze × 100 + pozice` (`101` = fáze 1, první obrazovka; `205` = fáze 2,
  pátá). Server význam čísel nezná, jen je řadí.
- Ukládá se a čte jako ostatní pole uzlu (`PERSISTED_NODE_KEYS`, `NODE_KEYS` dávky plánu, `FIELDS` úpravy
  `updateNodes`); `null` v `updateNodes` pole odebere.

## 2. Řazení karet

`card_dag.topo_order(card_ids, pairs, order=None)`: Kahn beze změny, jen remízu (karty připravené ve stejném
kroku) láme klíč `(order karty, nebo 10000 bez pole; id)`. Bez `order` je výsledek přesně dnešní. Vazby mají
dál přednost: karta s pořadím 101 za předchůdcem stojí dál za ním. Agent-state (`opora_agent_state_dag.facts`)
předá `order` uzlů; `cards[]` nese navíc `order` (nebo `null`). Snímek srdce řadí karty podle `topoIndex`, jak
už dnes.

## 3. Příkaz srdce `order`

`opora_heart.py order --nodes ID=101,ID=102,… [--dry-run] [--workspace W]`: návrh grafu `{updateNodes}`
měnící u existujících karet a sektorů jen `order` (`ID=none` pole odebere). Tvar a chyby jako `member`
(neznámý uzel, špatný druh, hodnota mimo rozsah, žádná změna → nic se neposílá). Při `autonomy.full` srdce
přijme jen svůj vlastní návrh, jinak čeká na člověka v UI. `heart_scope` povolí `HEART_NODE_FIELDS =
{"memberOf", "order"}`; `updateEdges` dál zakázané. `prompt.md` dostane jednu řádku: pořadí podle záměru
= `order`, nikdy vazba.

## 4. Pořadí stránek sdílené architektury (řez 2, schváleno 2026-10-31)

Živě na Ample (řez 1, #225): obrazovky jsou uzly **architektury projektu** (uzly se `site` a jejich předkové,
`architecture_graph.split`). Návrh grafu je měnit nesmí („Shared architecture … cannot be edited“), proto srdce
nastavilo pořadí jen 4 kartám. Pořadí obrazovek platí pro celý projekt, takže patří do architektury.

- `opora_heart.py order` rozdělí `--nodes` na uzly architektury a obsah prostoru (podle `architectureContext`
  kontextu návrhů / `split`). Obsah jde dál návrhem grafu (§3).
- Uzly architektury: srdce načte `GET /api/project-architecture?project=`, u daných uzlů změní **jen** `order`
  (`none` odebere) a uloží `POST /api/project-architecture` s očekávanou revizí (souběžná změna → chyba, nic
  nepřepíše). Jiná pole, uzly a vazby architektury se nemění; nástroj to ověří porovnáním před uložením.
  Server zápis srdce do architektury pustí jen při `autonomy.full` téhož projektu a jen se změnou pole `order`
  (jinak 403 / 422 s `code`); člověk zapisuje beze změny.
- Hned potom srdce založí návrh grafu s `adoptArchitectureContext: true` (převzetí architektury do plánu) a při
  `autonomy.full` ho přijme samo; bez plné autonomie čeká na člověka. Do přijetí blokuje rozdíl grafů jen nový
  claim, běžící běhy ne (heartbeat hlídá jen výřez karty).
- Výstup příkazu: `architecture: {revision, changes}`, `proposalId`, `accepted` u obou částí.

## Testy (vedle modulů)

- `test_card_dag.py`: bez `order` stejné pořadí jako dřív; s `order` remíza podle něj; vazba má přednost.
- `test_graph*.py`: `order` u `node`/`sector` projde, u oblasti nebo mimo rozsah odmítnuto.
- `test_opora_graph_change_plan.py`: srdce smí `order`, jiné pole dál 422 `heart_edit_scope`.
- `test_opora_heart.py`: `order` sestaví správný `updateNodes`, `--dry-run` nic nepošle, chyby vstupu.
- `test_opora_agent_state*.py`: `cards[]` nese `order` a `topoIndex` ho respektuje.

## Řez

Jedno malé PR z čerstvého `main`: `backend/canvas/{graph,card_dag,opora_graph_build,opora_graph_change_plan,
opora_agent_state_dag}.py`, `backend/brain_opora/heart/{opora_heart.py,prompt.md}`, `docs/brain-heart.md`,
`docs/oporahub-agent-state.md`, testy. Po sloučení restart 8740 a krok 1 přeřazení Ample znovu srdci.

# Hromadné mazání a krok zpět po smazání

Kontrakt pro dvě schopnosti plátna Editoru:

1. **Výběr tažením a mazání klávesou Delete.** Tah levým tlačítkem myši po prázdném plátně táhne
   obdélník výběru; vybrané jsou oblasti, sektory, uzly i komentáře, které obdélník zasáhne
   (React Flow `selectionMode="partial"`). Posun plátna je prostřední / pravé tlačítko nebo
   mezerník + tah, kolečko dál zoomuje. Klávesa `Delete` (i `Backspace`) mimo psaní otevře
   **jeden** potvrzovací dialog pro celý výběr (počet uzlů včetně potomků a vazeb). Potvrzení smaže
   vše najednou, zrušení nic nemění. Boční bloky (Akce / Pravidla / Podklady) do výběru nepatří.
2. **Zpět a Vpřed.** Na plátně jsou tlačítka Zpět / Vpřed; dělají přesně totéž co Ctrl+Z /
   Ctrl+Shift+Z (jedna historie, `editor/canvas/history`). Smazání je v historii krok jako každý
   jiný: Zpět vrátí smazané karty, vazby i jejich obsah (stav Desktop v3, prostor agenta).

## Backend

### Náhled a smazání výběru

- `GET /api/removal-preview?kind=selection&target=<id1,id2,...>` — `target` je čárkami spojený
  seznam 1..500 různých id uzlů (každé `valid_id`). Smazané = sjednocení všech cílů a jejich
  potomků (`parentId`). Chybí-li kterékoli id, chyba „Položka již v plátně neexistuje.“
  `label`: jméno jediné položky, jinak `"<n> položky"` (2–4) / `"<n> položek"` (5+). Digest náhledu obsahuje `target`.
- `POST /api/remove` beze změny tvaru payloadu; nově přijímá `kind: "selection"`.
- Odpověď pro `node` / `edge` / `selection` nese navíc `recoveryId` (řetězec).

### Záloha smazaného obsahu

Před smazáním se uloží záznam obnovy (`recoveryId`) s:
- grafem před smazáním,
- `state.nodes[id]` všech smazaných uzlů a `state.edges[eid]` všech smazaných vazeb,
- větvemi `onMet` / `onUnmet` přeživších karet, které mířily na smazaný uzel (blok id + původní větev),
- řádky `agent_workspace_revisions` smazaných uzlů.

### Obnova

`POST /api/remove/restore` `{project, workspace, recoveryId, digest}`:
- `digest` musí odpovídat aktuálnímu plátnu, jinak „Plátno se změnilo v jiném okně. Obnovte ho.“
- Graf = aktuální graf + smazané uzly, které v něm chybí + smazané vazby, jejichž konce existují
  (pořadí uzlů dle grafu před smazáním tam, kde to jde). Ukládá se jako krok zpět (`undo=True`).
- Do stavu Desktop v3 se vrátí chybějící záznamy uzlů / vazeb; vynulovaná větev se vrátí jen
  tehdy, když blok ještě existuje a jeho větev je stále výchozí (`kind: "none"`).
- Řádky prostoru agenta se vrátí (`INSERT OR IGNORE`).
- Záznam obnovy je jednorázový; druhé použití → „Obnovení už bylo použito.“
- Odpověď `{view}`.

## Frontend

- `GraphHistory.past` jsou kroky `{ graph, restore? }`; `restore` je `recoveryId`. `future` zůstává
  `Graph[]`. `recordRemoval(history, before, recoveryId)` založí krok se `restore` a zahodí `future`.
- Krok zpět na krok s `restore` volá `/api/remove/restore` místo `/api/graph` a pak znovu načte
  stav Desktop v3. Krok vpřed za ním je obyčejné uložení s `undo: true` (obsah zůstává na serveru,
  takže další Zpět je už obyčejné uložení snímku).
- Výběr více karet drží App (`multiSelected: string[]`); Board ho dostává v props a změny hlásí
  callbackem `onMultiSelect(ids)`. Delete na Board hlásí `onDeleteSelection()`; dialog otevírá App
  přes `requestRemoval("selection", ids.join(","))`.
- Smazání odebrání projektu (`kind: "project"`) historii dál vyprazdňuje.

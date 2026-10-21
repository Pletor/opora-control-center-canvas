# Automatický rebase, odvozená historie a sparse kontext ve výchozím stavu

Tato etapa dotahuje zbývající principy [Scionu](https://www.anthropic.com/research/redesigning-source-control)
pro plány: rebase dělá server, člověk vidí jen skutečné významové konflikty, historie
a blame se odvozují z changesetů přes API bez lokální kopie a kontext podle závislostí
(v2) je výchozí. Přijetí plánu zůstává **výhradně lidské**; nic z tohoto dokumentu
neposouvá přijatou hlavu.

## Automatický rebase

Když se posune přijatá hlava (`opora_spec_refs`), smyčka `AutoRebaseManager`
(`backend/canvas/opora_auto_rebase_manager.py`) projde zastaralé nativní návrhy všech
čtyř druhů: změny zadání, grafové přírůstky, změny grafu a změny obsahu. Zastaralý je
nepřijatý, nenahrazený návrh, jehož rodič není aktuální přijatá hlava.

Každý návrh se deterministicky sloučí třícestně proti přijaté linii (`opora_auto_rebase_merge.py`):

| Strana | Význam |
|---|---|
| `base` | přijatá hodnota, kterou návrh viděl u svého rodiče (`acceptedBefore`, `baseContent`) |
| `ours` | navržená hodnota |
| `theirs` | hodnota v aktuální přijaté hlavě |

Po polích (zadání: `goal`, `non_goals`, `acceptance`; graf: vybraná pole uzlu či vazby,
přidání/odstranění prvku; obsah: klíč `(kind, target, field)`):

- `theirs == base` → čisté, platí naše hodnota;
- `theirs == ours`, nebo naše strana pole nezměnila (`ours == base`) → redundantní, platí jejich hodnota;
- jinak → **skutečný konflikt stejného pole**.

Pravidlo je `merge_field` z `opora_field_merge.py`, jehož komutativitu a zachování
disjunktních změn dokazuje Lean (`tools/formal/lean/OporaHub/FieldMerge.lean`, viz
[ověřování](oporahub-verification.md)); diferenciální test hlídá shodu s modelem.

Výsledek celého návrhu:

| Výsledek | Co se stane |
|---|---|
| čistý | Nový neměnný návrh nad aktuální hlavou: nové ID, `supersedes` = původní, autor `{"kind": "orchestrator", "name": "system"}`, důvod `auto-rebase` v tabulce výsledků (`reason: three_way_clean`). Původní záznam zůstává beze změny. Redundantní položky se do nového návrhu nepřenesou. |
| redundantní | Všechny položky už přijatá hlava obsahuje; návrh se jen označí (`outcome: redundant`), nový nevzniká. |
| konflikt | Návrh zůstává zastaralý a vzniká záznam konfliktu s položkami `{key, base, ours, theirs}`. |
| přeskočený | Předpoklad mimo stejné pole (karta zmizela z pracovního plátna, změněná sdílená architektura, jen-ke-čtení…) — návrh zůstává k výslovnému `rebase`, důvod je uložen. |

Autor `orchestrator` je existující druh autora, který nikdy nesmí přijímat; ověřování
záznamů se tím nemění. Čistý graf se znovu odvodí z původního plánu (`derive` bez
`previous`), protože třícestná kontrola už potvrdila, že dotčená pole nikdo jiný nezměnil.

**Idempotence a meze.** Výsledek se ukládá v `opora_auto_rebase_outcomes` s klíčem
`(druh, návrh, přijatá hlava)` ve stejné SQLite transakci jako nový návrh; opakovaný
průchod nic nezmění. Jeden tick zpracuje nejvýše `OPORA_AUTO_REBASE_BATCH` návrhů
(výchozí 16, max. 256) napříč projekty; prostor, jehož hlava se od posledního úplného
průchodu nezměnila, se přeskočí. Neexistuje globální zámek: každý návrh se slučuje
pod zámkem svého projektu a vlastní transakcí.

**Konfigurace (prostředí):**

| Proměnná | Význam |
|---|---|
| `OPORA_AUTO_REBASE=0` | vypne auto-rebase úplně (agent-state se vrátí k výslovnému `rebase` a mezeře `auto_rebase`) |
| `OPORA_AUTO_REBASE_WORKER=0` | vypne jen smyčku na pozadí (testy volají `run_once()`), API zůstává |
| `OPORA_AUTO_REBASE_SECONDS` | interval ticku, výchozí 5 s |
| `OPORA_AUTO_REBASE_BATCH` | počet návrhů na tick, výchozí 16 |
| `OPORA_SPARSE_CONTEXT_DEFAULT=0` | vypne automatické zapsání nových karet do kontextu v2 |

### Konflikty a jejich vyřešení

Konflikt má stav `open`, `resolved` nebo `obsolete`. Zastará, když se hlava posune znovu
(smyčka návrh posoudí proti nové hlavě), když byl návrh přijat nebo ručně převeden.
Vyřešení je **běžný nový návrh** nad aktuální hlavou (člověk nebo agent; jazykový model
je volitelný, nikdy nutný). Jeho ID se ke konfliktu připojí:

| API | Význam |
|---|---|
| `GET /api/oporahub/auto-rebase/conflicts?project&workspace[&status]` | seznam konfliktů s `base/ours/theirs` |
| `GET /api/oporahub/auto-rebase/conflicts/{id}?project&workspace` | jeden konflikt |
| `POST /api/oporahub/auto-rebase/conflicts/{id}/resolve` | `{project, workspace, resolutionProposalId}`; návrh musí být jiný a mít za rodiče aktuální hlavu |
| `POST /api/oporahub/auto-rebase/run` | `{project, workspace}`; jeden omezený průchod hned (člověk nebo agent) |

## Odvozená data: historie a blame karty

`backend/canvas/opora_derived_history.py` promítne každou přijatou revizi na klíče karty:
`spec:<pole>`, `graph:node:<pole>`, `graph:edge:<id>` (incidentní vazby) a
`content:<kind>:<pole>`. Rozdíl proti projekci rodiče se ukládá do cache
`opora_derived_card_changes` s klíčem revize (`opora_derived_revisions` drží rodiče
a verzi výpočtu). Cache je odvozená a přepočitatelná; neměnné changesety zůstávají zdrojem.

| API | Výsledek |
|---|---|
| `GET /api/oporahub/history/card/{cardId}?project&workspace` | přijaté revize dotýkající se karty od nejstarší: `revisionId`, `parentRevision`, `revisionKind`, `proposalId`, `proposalKind`, `subject`, `author`, `originalAuthor`, `rebasedFrom`, `acceptedBy`, `acceptedAt`, `changedKeys` |
| `GET /api/oporahub/blame/card/{cardId}?project&workspace` | pro každý aktuální klíč poslední přijatá revize, changeset a autor |
| `POST /api/oporahub/history/rebuild` | `{project, workspace}`; jen člověk, smaže a přepočítá cache |

U auto-rebase je `author` systémový a `originalAuthor` sleduje řetěz `supersedes`
až k původnímu autorovi. Historie je omezená na 10 000 revizí; nesouvislá řada se odmítne.

## Sparse kontext v2 ve výchozím stavu

Zapsání karty spouští existující výslovnou přípravu v2 (`opora_execution_context.prepare`):
SQL pokrytí, vazbu registru a soukromý klíč. Nevytváří claim ani lease a nic nepřijímá.

- **Nové karty** — při prvním pozorování prostoru se uloží vodoznak přijaté hlavy
  (`opora_sparse_watermarks`); karty přijaté později smyčka zapíše sama (`source: auto`).
- **Existující karty** — backfill, idempotentní, s náhledem:

  ```bash
  uv run python -m backend.canvas.opora_sparse_backfill --data .data/production --dry-run
  uv run python -m backend.canvas.opora_sparse_backfill --data .data/production [--project P] [--workspace W]
  ```

  Totéž přes `POST /api/oporahub/sparse-context/backfill` s `{dryRun: true}` (zápis
  `dryRun: false` jen člověk). Stav: `GET /api/oporahub/sparse-context/enrollment`.

Karta, u které příprava selže (např. Git/file graf bez SQL autority), se uloží jako
`unavailable` s důvodem. **Fallback v1 zůstává:** `defaultContextProtocolVersion` je 2
jen u zapsaných karet; claim bez `contextProtocolVersion` dál znamená v1 a odmítnutí v2
nikdy tiše nepřepne na v1 (viz [kontext podle závislostí](oporahub-sparse-context.md)).
Office přechází na v2 svým `AGENT_OFFICE_OPORA_CONTEXT_VERSION=2`.

## Stav pro agenty

S auto-rebase zapnutým (`opora_agent_state_auto_rebase.py`) etapa `proposal`:

1. otevřený konflikt → `waiting/auto_rebase_conflicts`, akce `proposal.resolve_conflict`
   (`POST …/auto-rebase/conflicts/{id}/resolve`, `ready`, `preconditions` s hlavou a návrhem);
2. zastaralé návrhy po auto-rebase (bez redundantních a bez vyřešených konfliktů) → `waiting/stale_proposals`;
3. jinak `ok`.

Mezera `auto_rebase` zmizí. Dokument zůstává jen ke čtení.

## Ověření

`uv run pytest backend/canvas/test_opora_auto_rebase.py backend/canvas/test_opora_auto_rebase_kinds.py
backend/canvas/test_opora_derived_history.py backend/canvas/test_opora_sparse_enrollment.py
backend/canvas/test_opora_agent_state_auto_rebase.py backend/api/editor/test_opora_auto_rebase_routes.py`
pokrývá disjunktní rebase všech čtyř druhů, redundanci, záznam konfliktu, idempotenci
a mez ticku, zastarání konfliktu, historii a blame přes rebase, náhled i zápis backfillu,
automatické zapsání nové karty, agent-state a HTTP rozhraní.

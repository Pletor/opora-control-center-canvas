# Kroky plánu (`spec.steps`)

Kroky plánu jsou verzované pole přijatého zadání karty. Leží v `fields` zadání vedle `goal`,
`non_goals` a `acceptance`, takže se mění jen návrhem změny zadání (changeset) a přijetím člověkem.
Průběh práce (které kroky jsou hotové) do zadání nepatří; nese ho výsledek běhu (`stepResults`).

## Tvar a validace

```json
"steps": [
  {"id": "s1", "order": 1, "title": "Datový model", "acceptance": ["migrace projde"], "dependsOn": []},
  {"id": "s2", "order": 2, "title": "API", "acceptance": ["test API zelený"], "dependsOn": ["s1"],
   "kind": "code", "files": ["backend/**/*.py"]}
]
```

| Pole | Pravidlo |
|---|---|
| `id` | 1–40 znaků `A-Z a-z 0-9 _ -`, jedinečné v kartě |
| `order` | celé číslo 1–10000, jedinečné; větší než `order` všech závislostí |
| `title` | neprázdný text do 200 znaků |
| `acceptance` | 1–20 neprázdných podmínek do 1000 znaků |
| `dependsOn` | ID existujících kroků karty, bez sebe sama; závislosti tvoří acyklický graf |
| `kind` | volitelně `code`, `test`, `docs`, `design`, `research` |
| `files` | volitelně nejvýše 50 globů do 300 znaků |

Nejvýše 50 kroků. Pole `steps` je nepovinné: starší zadání bez něj zůstávají platná a čtou se jako
plán bez kroků. Validaci dělá `backend/canvas/opora_plan_steps.py` (`validate_steps`) a volá ji
`validate_payload` zadání, takže platí pro uložení pracovního zadání, návrh, přijetí, obnovu verze
i SQL kontext.

## Návrh, přijetí a převod

Kroky se mění stejně jako ostatní pole zadání: `POST /api/oporahub/changesets` s úplnými `fields`
(včetně `steps`), přijetí člověkem, výslovný `rebase`. Automatický převod zastaralého návrhu
([auto-rebase](oporahub-auto-rebase.md)) rozhoduje `steps` po jednotlivých krocích podle ID
pravidlem `merge_field` dokázaným v Leanu: změna jiného kroku, než který změnila přijatá linie, se
sloučí; změna téhož kroku na obou stranách je konflikt `spec:<karta>:steps:<krok>`. Když jsou obě
strany platné, ale sloučený plán ne (například závislost na kroku, který druhá strana odebrala),
vznikne konflikt s důvodem `steps_invalid_after_merge`.

`GET/POST /api/node-spec` vrací navíc `plan: {working, accepted, acceptedHead, workingDiffers}`:
kroky pracovního a přijatého zadání karty (`accepted` je `null`, dokud karta v přijatém zadání není).

## Neměnný snímek běhu

Převzetí běhu ukládá do snímku `assignment.steps`: přijaté kroky převzaté karty seřazené podle
`order` (u kontextu v2 po redakci jako ostatní snímek). Kontext v2 nese kroky i v zadání karet
SQL projekce. Snímek se po převzetí nemění; změna kroků vyžaduje nový běh.

## Výsledky kroků (`stepResults`)

Výsledek běhu může nést:

```json
"stepResults": [{"stepId": "s1", "status": "done", "evidence": {"notes": "…", "checks": ["pytest"], "commits": ["abc1234"]}}]
```

`stepId` musí patřit ke krokům ve snímku běhu a opakovat se nesmí; `status` je `done`, `failed`
nebo `skipped`; `evidence.notes` je povinný text do 4000 znaků, `checks` nejvýše 50 textů,
`commits` nejvýše 50 SHA (7–40 hex). Výsledky se ukládají v potvrzení výsledku běhu, takže jsou
idempotentní podle `requestId` (stejný obsah vrací stejné potvrzení, jiný obsah se odmítne).

Čtený model karty `{total, done, current}` (`backend/canvas/opora_step_results.py`) se skládá
ze **všech běhů** karty, ne jen z posledního. Hlášení kroku platí, jen pokud se definice kroku ve
snímku běhu rovná aktuálně přijaté definici (změněný krok začíná znovu). Krok, který některý běh
nahlásil `done`, zůstává hotový i když pozdější běh tentýž krok nahlásí `failed` nebo `skipped`;
krok bez `done` nese nejnovější platné hlášení. `current` je první nehotový krok v topologickém
pořadí, `null` když je vše hotové nebo karta kroky nemá. Process-sync a agent-state k tomu vydávají
seznam po krocích `[{id, status, executionId}]` (`stepItems`, resp. `cards[].steps.items`;
`status` = `done`/`failed`/`skipped`/`current`/`waiting`, `executionId` = běh, jehož hlášení platí).

Události (tok [událostí](oporahub-events.md)): převzetí emituje `step.started` pro první nehotový
krok, výsledek `step.done` / `step.failed` pro každý hlášený krok (v téže transakci).

## Připravenost k převzetí

Karta je připravená (`process-sync` stav `ready`, akce `claim` v agent-state), když má přijaté
zadání s alespoň jedním krokem, rozpočet ji připouští a nemá `blockedBy` (nedokončené předchůdce
v [grafu karet](oporahub-agent-state.md#graf-karet-dag)). Bez kroků je stav `needs-steps`.
Desktop-v3 `stages` (stará pipeline) se jen zobrazují v `pipeline`, nikdy neblokují.

Totéž vynucuje endpoint `POST /api/oporahub/executions/claim`: odmítne `409` s kódem
`plan_steps_missing` (přijaté zadání karty nemá kroky) nebo `blocked_by_predecessor`.

## Jediná definice hotovo

`card_done_state(card) -> {done, missing}` (`backend/canvas/opora_card_done.py`) je čistá funkce.
Hotovo = všechny kroky `done` (alespoň jeden) + přijetí karty doložené během nad aktuálním přijatým
zadáním (`card_acceptance`) + brána review `ready` (`gate_ready`) + PR `merged` + plán zapsán zpět
(`plan_written_back`) + lidské `close_card` (`human_close`). `missing` vypisuje chybějící části
v tomto pořadí. Agent-state ji vydává u každé karty jako `cards[].dod`: šest booleanů pod jmény
požadavků (`steps`, `card_acceptance`, `gate_ready`, `merged`, `plan_written_back`, `human_close`),
druh brány `gate` (`review` / `external`), `done` a `missing`. Detail karty kreslí dílky z něj.

- Akce `close_card` v agent-state je `blocked/human_only` jen když chybí pouze `human_close`; jinak
  `blocked/done_state_incomplete` s `preconditions.missing` a bez rozhodnutí pro člověka.
- Lidské potvrzení `done.confirmed` karty s přijatými kroky projde jen při splnění všeho kromě
  `human_close`; starší brána uzavření (doložené testy, `checks_passed`, hotová pipeline, scénář)
  pro takovou kartu neplatí. Karty bez kroků se dál uzavírají po staru a stará data zůstávají čitelná.
- `gate_ready` má dva režimy a výstup je nese v poli `gate`: se zapnutými úlohami review
  (`OPORA_REVIEW_JOBS`) je to `"review"` a platí jen brána OporaHubu `ready` (čte se pro všechny
  vazby PR, i sloučené); s vypnutými úlohami review je to `"external"` a branou je ochrana větve
  na GitHubu, takže `gate_ready` = PR je sloučený. Akce `close_card` nese `preconditions.gate`.

## Migrace

```
uv run python -m backend.canvas.opora_plan_steps_migration --data <data> --project <p> --workspace <w> [--apply]
```

Bez `--apply` jen vypíše plán (nic nezapisuje). Pro každou kartu bez kroků (v pracovním i přijatém
zadání) složí z podmínek bloků (podle čísla bloku), ze starých `steps` a `criteria` lineární
kroky (`s1` → `s2` → …; kritéria karty doplní podmínky posledního kroku) a s `--apply` založí jeden
**návrh** změny zadání na kartu (autor `orchestrator`). Návrh se nikdy nepřijímá automaticky;
vyžaduje přijaté výchozí zadání.

## Omezení

- Spuštěné běhy založené před nasazením mají jiný otisk snímku (nové pole `steps`) a při dalším
  heartbeatu se odvolají; stačí nový claim.
- Testy napsané před kroky plánu vypínají v `backend/conftest.py` povinnost kroků při claimu;
  testy kroků ji zapínají značkou `plan_steps_claim`.

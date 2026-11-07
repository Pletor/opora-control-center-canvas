# Linie L4 – vodotisk cesty: plán → úkol → relace → kód → commit → PR

Datum: 2026-11-06. Navazuje na L2 (`2026-11-06-linie-editor-a-vynuceni.md`) a L3 (`2026-11-06-linie-detail-commitu.md`).
Stav: kontrakt, první průchod.

## Proč

Člověk chce z jediného označení dohledat celou cestu práce: zadání na plátně a jeho revizi, úkol, relace LLM, které
na něm dělaly, místa v kódu, commity, PR a začlenění; cestu seřazenou hierarchicky i chronologicky, aby se z ní dal
ladit proces. Dnes je řetěz z větší části **odvozovaný** (ticket se ke commitu hledá přes větev a rozsah SHA) a tři
hrany chybí: relace Claude Code se nikde neeviduje, ID úkolu se do commitu nepíše a kód na požadavek neukazuje vůbec.
LSP (`workspaceSymbol`, `findReferences`) je nástroj na procházení kódu, ne identita cesty: je fuzzy, bez vazby na
zadání a při plošném použití dělá šum.

## Inventura (co existuje)

| Hrana | Dnes | Kde |
|---|---|---|
| plán → commit | trailer `Opora-Node: <karta>@<revize>`; důkazem je cesta/větev, trailer sám je tvrzení | `backend/canvas/commit_pairs.py` |
| běh → PR | `Opora-Execution`, `Opora-Revision` v těle PR | `backend/canvas/opora_execution_pr_discovery.py` |
| úkol → větev/SHA | ticket `work {branch, baseSha, headSha, checks, acceptance, merged}` | `backend/agi_pletor/linie/work.py` |
| commit → vše | `GET /api/pletor/linie/commit/{sha}` | `backend/agi_pletor/linie/commit.py` |
| zadání → revize | `contextVersion` (otisk zadání), `machine.cardVersion` v ticketu | `docs/karta-pro-agenty.md` |
| relace → úkol | **nic** (`.opora/linie.json` nese jen `ticketId`) | `tools/linie.py` |
| kód → požadavek | **nic**; jen symbolová mapa pro Zrcadlo v `docs/zrcadlo-symboly.md` | — |

## Princip

1. **Jedna značka na celou cestu: vodotisk `OP-XXXXXX`.** Razí ho OPORA při založení práce Linie:
   `"OP-" + ticketId[3:9].upper()` (6 hex znaků z UUID ticketu); při kolizi v projektu se vezme dalších 6 znaků.
   Nikde v repozitáři se tvar `OP-[0-9A-F]{6}` nevyskytuje (ověřeno 2026-11-06). Krok plánu = `OP-XXXXXX.3`
   (pořadí `spec.steps`, jinak index `doneCriteria`). Relace se do značky nepíší (jeden úkol = víc relací); jsou v evidenci.
2. **Značka je tvrzení, evidence je důkaz.** Agent značku píše (trailer commitu, komentář v kódu, tělo PR). OPORA každou
   hranu ověří z nezávislého zdroje a dá jí stav:
   - `verified`: commit s `Opora-Mark: OP-…` leží na `work.branch` nad `baseSha`; komentář `OP-…` je v souboru, který
     některý verified commit úkolu změnil; relace má `fromSha`, který je předkem commitů úkolu.
   - `claimed`: značka je, důkaz ne (commit v cizí větvi, komentář v souboru, kterého se úkol nedotkl).
   - `inferred`: bez značky, ale na větvi úkolu nad `baseSha` (dnešní odvození).
   - `missing`: hrana chybí (commit bez relace = „bez evidovaného běhu“; úkol bez karty).
   Nic se nedomýšlí; stav `missing` je pravdivý stav práce mimo proces.
3. **Revize se zamykají při startu běhu.** Záznam relace nese `revision` zadání (`machine.cardVersion`, jinak `null`)
   a `fromSha` = HEAD větve v okamžiku startu. Pozdější změna plánu historii nepřepíše.
4. **Dohledání je jeden dotaz, ne procházení.** `GET /trace/{mark}` a `linie.py trace` sestaví cestu z DB (ticket,
   karta, plán, relace), `git log --all --grep=<mark>` a `git grep -n <mark> <headSha>` (čte strom commitu, nezávisí
   na worktree). Sekundy; žádné čtení dokumentů ani transkriptů.
5. **Komentář v kódu jen u podstaty.** Jeden řádek `# OP-XXXXXX.3: <proč to tu je>` (TS `// …`) nad vstupním bodem
   nebo principem kroku, ne nad každou funkcí. Historie běhů do komentáře nepatří. Značka bez úkolu je sirotek →
   trace ji hlásí, mažeme.

## Datový model (`tickets.work`, zapisuje jen `work.py`)

```json
{"mark": "OP-3F9A1C",
 "runs": [{"runId": "run_…", "sessionId": "<claude session id | uuid>", "agent": "terminal|office-1|…",
           "transcriptPath": "…|null", "startedAt": "…", "fromSha": "<40hex>", "revision": "<cardVersion>|null"}],
 "…": "pole z L2 beze změny; checks[] a headSha nově nesou runId poslední relace téhož agenta (nebo null)"}
```

Terminál: `<cwd>/.opora/session.json` `{sessionId, transcriptPath, at}` zapisuje hook `SessionStart` Claude Code
(`tools/opora_session_hook.py`, registrace v `.claude/settings.json`). `linie task` ho přečte; bez něj
`OPORA_SESSION_ID`, bez obojího `uuid4` a `agent: "terminal"`.

## API (`/api/pletor/linie`)

- `POST /work/{ticketId}/run {sessionId, agent?, transcriptPath?}` (agent i člověk): přidá/aktualizuje záznam relace
  (stejné `sessionId` → aktualizace, ne duplikát). Vrací ticket jako `GET /work/{id}`.
- `GET /trace/{mark}?project&workspace` (čtení, agent i člověk; 404 `mark_not_found`):

```json
{"mark": "OP-3F9A1C",
 "ticket": {"ticketId", "title", "state", "stateLabel", "next", "body": {"essence", "build", "doneCriteria"},
            "work": {"branch", "baseSha", "headSha", "target"}},
 "card": {"id", "name", "link", "known"} | null, "revision": "<cardVersion>|null",
 "plan": [{"id", "order", "title", "acceptance", "kind"}],
 "runs": [{"runId", "sessionId", "agent", "startedAt", "fromSha", "revision", "status": "verified|claimed"}],
 "commits": [{"sha", "sha7", "title", "at", "author", "branches": [], "trailers": {"mark", "node", "execution"},
              "runId": "…|null", "status": "verified|claimed|inferred"}],
 "code": [{"path", "line", "text", "step": 3 | null, "symbol": "<nejbližší def/class/function>|null",
           "status": "verified|claimed"}],
 "pr": {...} | null, "checks": [...], "acceptance": {...} | null, "merged": {...} | null, "preview": {...} | null,
 "gaps": [{"kind": "commit_without_run|code_without_commit|mark_on_foreign_branch|no_card", "ref": "…", "text": "…"}],
 "sentence": "OP-3F9A1C: <essence> (karta X, 2 relace, 5 commitů, 3 místa v kódu, PR #12 OPEN); stav …"}
```

Pravidla: `commits` = `git log --all --grep=<mark>` (status podle větve/rozsahu) ∪ commity `baseSha..branch` bez
značky (`inferred`), seřazené od nejstaršího. `code` = `git grep -n -e <mark> <headSha>` (bez `headSha` prázdné);
`symbol` je nejbližší předchozí řádek `def |class |function |export (const|function) ` (shortcut: bez LSP, upgrade až
bude `code_intelligence` volatelný ze serveru). `commit.runId` = relace téhož úkolu s nejpozdějším `startedAt`, jejíž
`fromSha` je předkem commitu (nebo roven jeho rodiči). Karta, plán, kancelář, PR a náhled se berou stejnými funkcemi
jako detail commitu (žádná kopie). `GET /commit/{sha}` nově vrací `trailers.mark` a `ticket.mark`; regex traileru
`Opora-Node` ořízne `@<revize>` (dnešní chyba: `uuid@2` kartu nenajde).

## Terminál (`tools/linie.py`)

- `task`: po ověření kontextu zavolá `POST /work/{id}/run`; výpis doplní řádky `Vodotisk: OP-…` a
  `Commit: trailer "Opora-Mark: OP-…"; podstata v kódu "# OP-….<krok>: proč"`.
- `report`: HEAD bez traileru `Opora-Mark: <mark>` → exit 2 s textem a bez odeslání; `--allow-unmarked` povolí
  (cizí commity, úklid).
- `trace [--mark OP-…]` (výchozí značka úkolu z `.opora/linie.json`): vypíše vrstvy Proč / Kdo / Co / Kde / Mezery,
  u každé hrany stav.

## Velín

Panel **Cesta OP-…** (`LinieTrace.tsx`, `logic/linie-trace.ts`): Proč (karta s odkazem, revize, kroky), Kdo (relace),
Co (commity se stavem, místa v kódu `cesta:řádek` + symbol), Kde (PR, kontroly, přijetí, začlenění, náhled), Mezery.
Otevírá se z detailu kuličky (`LinieDetail`) a z detailu commitu (`LinieCommit`) tlačítkem „Celá cesta“; značka je
v hlavičce obou a v hoveru kuličky. Pletor dostává `sentence`.

## Postupy

Skilly `git-linie`, `git-linie-srdce`, seed `opora-control-center`, `CLAUDE.md` (odstavec Linie),
`.github/pull_request_template.md`: každý commit úkolu nese `Opora-Mark`; komentář jen u podstaty kroku;
`linie trace` před hlášením „hotovo“. `docs/zrcadlo-symboly.md` zůstává mapou pro Zrcadlo a odkazuje sem.

## Ověření

- `uv run pytest backend/agi_pletor backend/api/agi_pletor tools`, `npm test`, `npm run build`.
- Testy: trace verified/claimed/inferred/missing, komentář v kódu, sirotek, neznámá značka 404; `run` idempotence;
  `mark` kolize; regex `Opora-Node: x@2` → karta `x`; `linie report` bez traileru exit 2; `linie trace` výpis.
- Kouřově na náhledu 8790: kulička → `linie task` → commit s trailerem a komentářem → `report` → `trace` i panel Cesta.

## Mimo rozsah

Vynucení značky v názvu větve, LSP symbol v trace, zpětné označení dnešních commitů z terminálu (zůstanou
`inferred`/`missing`), transkript relace do OPORY (jen cesta k souboru).

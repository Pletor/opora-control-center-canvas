# Formální ověřování: vstupy, tvrzení a výsledky

OporaHub eviduje formální kontrolu jako neměnný požadavek a nejvýše jeden
neměnný výsledek. Požadavek zachytí skutečnou přijatou revizi, digest zadání,
kartu, execution ID a epochu ze serveru. Nahlášený commit, model a výstup jsou
samostatné podklady; nejsou důkazem, že danému commitu odpovídá implementace.

Tato etapa připravuje společnou evidenci pro TLA+/TLC a Lean. Žádný import
neobdrží důvěru nezávislého ověřovače. `trust` má hodnotu `agent-reported`, jen check
z [důvěryhodného CI](#důvěryhodné-ci-formal-trustedyml) s ověřeným původem má `ci-verified`;
`independentlyVerified` je vždy `false`, včetně výsledku `passed`. Politika
review, dokončení karty ani merge se tím nemění. Úspěch TLC znamená kontrolu
uvedeného konečného modelu; úspěšné sestavení Lean samo není kontrolou důkazu.

## Protokol a oprávnění

Základ je `/api/oporahub/verifications`. Zápisy používají existující execution
token; token nikdy není v historii ani v uloženém požadavku. Server při prvním
zápisu i bezprostředně před uložením kontroluje epochu, lease, neměnné zadání
a pevný konec běhu. Vytvoření kontroly neuvolňuje kartu ani nezakládá druhý lease.

- `POST /requests`: `{project, workspace, executionId, token, epoch, requestId,
  verification}`. Totožná identita i obsah vrací původní záznam; jiný obsah
  pod stejnou identitou je konflikt. `verification` obsahuje přesně `tool`,
  `source`, `claims`, `assumptions`, `configuration`, `artifacts`.
- `tool`: `{name: "tlc" | "lean", version, distributionSha256}`. `source`:
  `{repository, commitSha}`; repository je `owner/name`, SHA je 40 malých hex
  znaků. Jde o tvrzení předkladatele, nikoli potvrzenou identitu GitHubu.
- `claims`: 1–32 záznamů `{id, kind, statement}`, kde kind je `invariant`,
  `temporal-property` nebo `theorem`; ID jsou unikátní. U Lean jsou přípustná
  jen theorem, u TLC invariant a temporal-property. Server doplní digest tvrzení.
  `assumptions` je nejvýše 32 neprázdných textů, `configuration` je omezený JSON
  s uvedením konečných mezí, fairness, axiomů a režimu kontroly podle nástroje.
- Každý vstupní artefakt je `{path, role, sha256, dataBase64}`. Server ověří
  přesné původní bajty a velikost, sestaví seřazený manifest a jeho SHA256.
  Role jsou `model`, `configuration`, `dependency`, `proof`, `source`, `lockfile`.
  Jména jsou relativní POSIX cesty bez traversal, zpětných lomítek a prázdných
  segmentů; žádné symlinky se nepřenášejí. Nejvýše 32 souborů na zprávu.
  Vstupy nejsou prázdné: TLC vyžaduje model i konfiguraci, Lean proof nebo source.
  Úplnost importů a závislostí zůstává tvrzením předkladatele.
- `POST /{id}/report`: `{project, workspace, token, epoch, requestId, report}`.
  `report` obsahuje přesně `outcome`, `checkedClaims`, `summary`, `artifacts`.
  Outcome je `passed`, `counterexample`, `failed`, `inconclusive` nebo `cancelled`.
  CheckedClaims jsou unikátní ID z požadavku; passed vyžaduje všechna tvrzení.
  Passed vyžaduje alespoň jeden výstupní soubor, counterexample soubor této role.
  Výstupní role jsou `stdout`, `stderr`, `counterexample`, `proof`, `run-metadata`.
  Místní TLC export přikládá také metadata běhu: skutečný začátek a konec,
  exit code, důvod ukončení, nastavený časový limit a otisky runneru. Jde stále
  o nahlášená metadata, nikoli autentizovaný původ nezávislého ověřovače.
  Totožné opakování vrací původní výsledek i po skončení běhu. Konflikt odmítne.
  Nový výsledek po ztrátě oprávnění nepřijme. Časy přijetí určuje server.
- `GET ?project=…&workspace=…&nodeId=…` vrací nejvýše 100 posledních požadavků
  s výsledky; nodeId je nepovinné. `GET /{id}?project=…&workspace=…` vrací přesný
  požadavek a výsledek i po odstranění karty nebo archivaci prostoru.
- `GET /{id}/artifacts/{sha256}?project=…&workspace=…` zpřístupní pouze bajty
  uvedené v daném manifestu. Odpověď je příloha, `application/octet-stream`,
  `nosniff`, CSP sandbox. HTML ani SVG se nespouští.

`requestId` má stejný formát jako execution request ID. Neznámá pole, duplicitní
cesty, neplatné base64/SHA, nekonečná čísla a neomezené vnoření JSON se odmítají.
Text je nejvýše 4 000 znaků, konfigurace nejvýše 16 KiB a 8 úrovní. Jeden soubor
má nejvýše 2 MiB, vstupy a výstupy jednoho požadavku dohromady nejvýše 8 MiB,
projekt nejvýše 64 MiB unikátních bajtů. HTTP JSON tělo má limit 12 MiB.

## Uložení, historie a zobrazení

Bajty jsou v projektovém SQLite jako SHA256 adresované BLOB, odděleně od JSON
metadat. Vložení souborů a požadavku či výsledku je jedna transakce. Kvóty se
počítají v téže transakci; neúspěšný zápis nezanechá částečný úspěch. Čtení znovu
ověřuje hash a velikost. Chybějící či změněné bajty jsou nedostupný podklad,
nikoli zelené ověření. Zálohování celé projektové DB zahrnuje historii i bajty;
destruktivní obnova starší DB nesmí novou evidenci odstranit.

Detail výsledku ukazuje skutečnou revizi a execution, nahlášený commit, nástroj,
tvrzení, předpoklady, konfiguraci a soubory ke stažení. Důvěra je viditelná
vedle výsledku. Změněná přijatá revize označí historii jako zastaralou; tato
etapa vůbec neuděluje použitelnost pro automatické rozhodnutí o správnosti.

## Oddělený ověřovač a zbývající práce

Agent nejprve převezme běžné execution oprávnění. [Místní TLC export](../tools/formal/oporahub-execution/README.md)
vytvoří `verification.json` a `report.json` bez tokenu. Klient obalí první soubor
scope, execution ID, tokenem, epochou a stabilním requestId a odešle jej na
`/requests`. Druhý odešle s credentials na `/{id}/report`; potom může obvyklým
execution resultem odkázat uložená ID. Export sám API nevolá a heartbeat běhu
zůstává povinností vykonavatele. Po ztrátě oprávnění lze jen přesně opakovat
již uložený zápis, nikoli přidat nový výsledek.

Spouštění patří do Office/CI. Import neprovádí příkaz, neinstaluje nástroj,
nenačítá URL a nesvěřuje agentovi volbu důvěry. Místní TLC profil musí zachovat
přesné vstupy, verzi a hash nástroje, konečné meze, výstup i důvod ukončení.
Timeout, nedokončený průchod, simulace nebo useknutý potřebný výstup nemají
výsledek passed. Kontrola negativních mutantů dokládá citlivost modelu,
nikoli správnost Pythonu nebo TypeScriptu.

## Automatické ověřování v CI (etapa 3b)

Důkazy a kontroly modelů spouští stroj při každé změně, nikdo je nehlásí ručně.

**Workflow.** `.github/workflows/formal.yml` běží na PR, které mění `tools/formal/**`
nebo modelované moduly (`backend/canvas/opora_executions.py`, `opora_execution_*.py`,
`card_leases.py`, repozitář a schéma executions, `opora_review_aggregation.py`,
`opora_review_job*.py`, `opora_field_merge.py`, `database/repositories/opora_changesets.py`).
Modely TLA+: `oporahub-execution/ExecutionAuthority.tla` (lease a epochy),
`review-jobs/ReviewJobs.tla` (strop kol, práh hlasů, žádné opětovné zveřejnění otisku,
schválení vázané na head SHA; mutanty `no_cap`, `repost`, `threshold`, `stale_approval`)
a `pr-loop/PrLoop.tla` (zápis merge přesně jednou, zavření → pozornost, znovuotevření ji
zruší, nová hlava se znovu připojí, liveness pod weak fairness; mutanty `double_merge`,
`no_attention`, `no_relink`). Každý negativ musí selhat deklarovaným invariantem nebo
(`temporal-property`) vlastností. Job s názvem `formal/tlc` vytvoří
stejnojmenný check run. Stáhne jen připnutý `tla2tools.jar` v1.7.4 (SHA256
`936a2620…0e88`); jiný soubor runner odmítne. Pak spustí TLC na **každé** konfiguraci
z `tools/formal/*/cases.json`:

- pozitivní konfigurace (`expect: pass`) musí vyčerpat konečný prostor bez chyby
  (exit 0, nulová fronta),
- negativní konfigurace (`expect: violation`) musí selhat **přesně** deklarovaným
  invariantem. Negativ, který projde, znamená prázdnou (vacuous) specifikaci a check
  selže s druhem `negative_not_detected`.

Výsledkem je strojově čitelný artefakt `formal-tlc-summary` (`formal-summary.json`:
`schemaVersion`, `check`, `commitSha`, `tool`, `ok`, `cases[]` s `expect`, `observed`,
`kind`, statistikami a stopou akcí, `evidenceKinds`). Každé selhání je navíc anotace
`::error title=formal/tlc <druh>::<JSON případu>`. Druhy: `positive_violation`
(protipříklad v pozitivní konfiguraci), `negative_not_detected`, `wrong_violation`,
`runner_error`. Job také spustí testy parsování na uložených výstupech TLC
(`tools/formal/fixtures/`).

**Místní běh.** Stejný skript běží i lokálně (Java 21 na PATH):

```powershell
python tools/formal/run.py --jar C:/cache/tla2tools-1.7.4.jar --summary formal-summary.json
python tools/formal/run.py --download --cache-dir C:/cache/opora-tla --case negative
```

Exit 0 = všechna očekávání splněna, 1 = některé selhalo, 2 = chybí Java nebo připnutý
jar. Testy: `python -m pytest tools/formal/test_formal_run.py -q` (TLC nespouští).

**Příjem v Canvasu.** Server čte check `formal/tlc` sám, dvěma cestami:

1. Import [GitHub důkazů](oporahub-github.md) (`POST /api/oporahub/github-evidence`)
   už check runs načítá. Ve stejné transakci `opora_formal_checks.ingest_snapshot`
   převede dokončený `formal/tlc` na záznam ve `/api/oporahub/verifications`.
2. Smyčka uzavření běhů (`ExecutionPullRequestManager`) každých
   `OPORA_FORMAL_CHECK_SECONDS` (výchozí 300, `0` vypne) přečte pro každé otevřené PR
   připojené k běhu check `formal/tlc` na jeho head SHA. U neúspěchu načte i anotace.
   Čte jen GET s pevným originem; rate limit nebo 403 pozastaví smyčku.

Záznam vzniká jen tehdy, když je PR připojené k běhu (execution → PR). Jen tak má
execution ID, kartu, epochu a přijatou revizi. PR bez vazby se nezapíše. Jeden check
run (`requestId = gh-check-<id>`) dá nejvýše jeden záznam, opakované čtení nic nepřidá.
Záznam nese `source.commitSha` = head SHA checku a pole `origin` (`github-check-run`,
`checkRunId`, `conclusion`, `observedVia`, `failureKinds`). Výsledek:
`success` → `passed` (všechna tvrzení z `ExecutionAuthority.cfg`), anotace
`positive_violation` → `counterexample` (s artefaktem `counterexample.json`),
jiné selhání → `failed`, `timed_out` a další → `inconclusive`, `cancelled` → `cancelled`.
Vstupní bajty modelu se neimportují. Model leží v repozitáři na uvedeném commitu.

U `formal/*` zůstává důvěra `agent-reported` a `independentlyVerified: false`. Workflow je
kód právě posuzovaného PR, takže zelený check je pozorování, ne nezávislý ověřovač.
Tvrzení TLC záznamu zrcadlí pozitivní konfigurace všech modelů (`ExecutionAuthority` bez
předpony, ostatní `ReviewJobs-…`, `PrLoop-…`; hlídá test).

**Protipříklad → pozornost.** `GET /api/oporahub/agent-state` z nejnovějšího
CI záznamu každého běhu odvodí pozornost. Výsledky `counterexample`, `failed` a
`inconclusive` dají připravenou akci `verification.investigate` (`GET` na detail
ověření, `preconditions` s `headSha`, `outcome`, `failureKinds`). Protipříklad a skutečné selhání
dají i akci `verification.fix` (viz níže). Dají také rozhodnutí
`verification_counterexample` nebo `verification_failed`, které jde před ostatní
rozhodnutí. Pozdější úspěšný check na novějším SHA pozornost zruší. Nic se nezapisuje.

**Shoda implementace (konformní most, ne důkaz).** Model ≠ implementace.
`backend/canvas/test_opora_execution_conformance.py` spouští skutečnou službu
`opora_executions` na SQLite s injektovanými hodinami. Náhodné scénáře se seedem
obsahují claim, heartbeat, release, lidské vynucené uvolnění, výsledek, zastaralé
pověření a posun času. Záznam událostí kontrolují Python predikáty
`OneActiveOwner`, `NoStaleEpochReceipt`, `OneReceiptPerExecution` a `MonotonicEpoch`
(`opora_execution_conformance.py`). Predikáty musí odmítnout ručně pokažené logy, aby
nemohly projít naprázdno. Test dokládá jen to, že zkoumané běhy neporušily vlastnosti.
Nejde o refinement ani o úplné pokrytí. V CI běží jako check `formal/conformance`.

**Lean: důkazy čistého jádra (`formal/lean`).** `tools/formal/lean/` je Lake projekt
(`lakefile.toml` jen jako data, toolchain připnutý v `lean-toolchain`, dnes
`leanprover/lean4:v4.22.0`, bez Mathlib). Modely jsou malé a věrné skutečným funkcím;
specifikace (komentář v hlavičce každého souboru) je psaná zvlášť od implementace a člověk
ji má porovnat se záměrem:

| Soubor | Implementace | Dokázáno |
|---|---|---|
| `OporaHub/Votes.lean` | `opora_review_aggregation.tally`, `candidates`; zveřejnění v `opora_review_job_tasks.advance` | nález je zveřejněn ⇔ navržen a má ≥ `requiredVotes` potvrzení (`posted_iff`); méně platných hlasovacích lístků než práh nezveřejní nic (`not_posted_below_quorum`); další lístky nález nestáhnou (`posted_monotone`); dedupe podle otisku vrací každý nový otisk jednou, vzestupně, nikdy známý (`dedupe_excludes_known`, `dedupe_nodup`), je idempotentní (`dedupe_idempotent`) a po zveřejnění nic znovu nenavrhne (`no_repost`) |
| `OporaHub/AcceptedHead.lean` | `ChangesetRepository.advance` + `insert(parentRevision=expected)` | zastaralá očekávaná hlava nikdy neposune (`stale_never_advances`); rodič přijaté revize je předchozí hlava (`advance_parent_is_previous_head`); každá dosažitelná historie je lineární (`reachable_linear`); log roste přesně o úspěšné posuny (`run_log_length`) |
| `OporaHub/FieldMerge.lean` | `opora_field_merge.merge_fields` | 3-way merge polí je komutativní (`merged_comm`, `conflicts_comm`); disjunktní změny nemají konflikt (`disjoint_no_conflict`) a zachovají obě strany (`disjoint_preserves_both`) |

`opora_field_merge` je dokázané rozhodovací pravidlo [automatického rebase](oporahub-auto-rebase.md):
`opora_auto_rebase_merge.py` jím rozhoduje každé pole, a se zapnutým auto-rebase mezera `auto_rebase` mizí.

`python tools/formal/lean/audit.py` (job `formal/lean`, výchozí zapnutý) provede a do
souhrnu `lean-summary.json` zapíše:

1. `forbidden_construct`: textový sken **před** spuštěním Leanu odmítne `sorry`, `admit`,
   nové `axiom`, `native_decide`, `implemented_by`/`extern`, `unsafe`, `opaque`, `#eval`,
   `run_cmd`, `initialize`, vlastní `macro`/`syntax`/`elab`, `set_option debug.*` a importy
   mimo `OporaHub.*`. Důkazní soubory jsou podmnožina bez metaprogramů.
2. `build_failed`: `lake build` (kernel kontroluje každý důkaz).
3. `nonstandard_axiom` / `audit_incomplete`: `#print axioms` na **každý** teorém nalezený ve
   zdrojích. Povolené jsou jen `propext`, `Classical.choice`, `Quot.sound`; `sorryAx` nikdy.
4. `vectors_drift`: `lake exe vectors` (z `Vectors.lean`, mimo knihovnu důkazů) musí dát
   přesně commitnutý `vectors.json`. `backend/canvas/test_opora_lean_differential.py` na
   stejných vstupech pouští **skutečné** Python funkce (tally/candidates, `advance` nad
   projektovým schématem SQLite, `merge_fields`) a porovná výsledky; hlídá i to, že vektory
   nejsou triviální. Rozdíl = rozpor modelu a implementace.

Pod GitHub Actions audit vypíše `::notice title=formal/lean audit::{toolchain, ok,
theorems:[[jméno, axiomy]]}` a pro každé selhání `::error title=formal/lean <druh>::<JSON>`.
Exit 0 = čisté, 1 = selhání, 2 = chybí elan/Lean. Lokálně: nainstalovat elan, pak
`python tools/formal/lean/audit.py` a `python -m pytest tools/formal/lean/test_lean_audit.py`.

**Příjem Lean.** Smyčka uzavření běhů čte u checku `formal/lean` vždy i anotace. Záznam má
`tool.name = lean`, tvrzení po modulech (`OporaHub-Votes`, `OporaHub-AcceptedHead`,
`OporaHub-FieldMerge`, druh `theorem`) a v `configuration.axiomAudit` axiomy každého
teorému. `passed` vznikne jen ze zeleného checku **s úplným čistým auditem**; zelený check
bez auditu nebo s nestandardním axiomem je `inconclusive`. Druhy selhání z anotací jdou do
`origin.failureKinds`. `distributionSha256` u Lean je SHA-256 řádku `lean-toolchain`,
nikoli binárky (uvedeno ve `version`).

## Důvěryhodné CI (`formal-trusted.yml`)

`formal.yml` je kód posuzovaného PR: autor PR může workflow změnit a zelený check si
vyrobit. Proto jeho výsledky zůstávají `agent-reported`. Dvojče
`.github/workflows/formal-trusted.yml` běží na `pull_request_target`; GitHub pak vždy
použije definici workflow ze **základní větve**, změny workflow v PR se nespustí.

- Job `verify` má jen `contents: read`, žádné secrets, `persist-credentials: false`.
  Z PR čte jen data: `*.tla`, `*.cfg`, `cases.json` a Lean zdroje `OporaHub/**`. Runner
  `run.py`, `audit.py`, `lean-toolchain` a `lakefile.toml` bere ze základního commitu.
  Symlinky v `tools/formal` odmítne. Lean sken (krok 1 výše) proběhne před elaborací, takže
  elaborace nemůže spustit kód z PR; spustitelný `vectors` se v trusted režimu nestaví.
  Bez cache (žádná otrava cache základní větve).
- Výstupní souhrny nahraje jako artefakt `formal-trusted-<headSha>`.
- Job `publish` (`checks: write`) PR neklonuje ani nespouští; jen parsuje JSON a vytvoří
  check runs `formal-trusted/tlc` a `formal-trusted/lean` na hlavě PR s
  `external_id = run id` a stejnými anotacemi jako běžné joby.

Canvas (smyčka uzavření běhů) u `formal-trusted/*` přečte `GET /actions/runs/{external_id}`
a jeho artefakty. Důvěru `ci-verified` (`trust` i `sourceBinding`) dá jen když run je
`.github/workflows/formal-trusted.yml`, událost `pull_request_target` nebo `workflow_run`,
a run vlastní artefakt `formal-trusted-<headSha>` pro přesně tuto hlavu. Jinak se záznam
uloží jako `agent-reported` a `origin.provenance.reason` řekne proč (`missing_run_id`,
`untrusted_workflow`, `untrusted_event`, `head_not_bound`). Import GitHub důkazů
(`/github-evidence`) trusted ani Lean checky nezapisuje, nechá je smyčce s ověřením původu.

Model hrozeb a zbytková rizika:

| Hrozba | Opatření |
|---|---|
| PR změní workflow a vyrobí zelený check | `pull_request_target` bere workflow ze základní větve; `formal/*` zůstává `agent-reported` |
| Workflow v PR vytvoří check run se jménem `formal-trusted/*` | Canvas váže check na run trusted workflow s trusted událostí a artefaktem pro tuto hlavu |
| Podvržené `external_id` jiného (zeleného) trusted běhu | artefakt `formal-trusted-<headSha>` musí patřit tomuto běhu a této hlavě |
| Spuštění kódu PR s tokenem nebo secrets (pwn request) | verify bez secrets s read-only tokenem; publish nespouští obsah PR, jen parsuje JSON |
| Lean metaprogram / `#eval` při elaboraci podvrhne audit | sken zakázaných konstrukcí z kódu základní větve proběhne před elaborací |
| Škodlivý toolchain v `lean-toolchain` PR | trusted job používá `lean-toolchain` a `lakefile.toml` základní větve |
| TLC čte cizí soubory přes symlink | symlinky odmítnuty, kopíruje se jen `*.tla`/`*.cfg`/`cases.json` |
| DoS (nekonečný důkaz nebo model) | timeouty jobů; výsledek není `passed` |

Zbytkové riziko: kdo může zapisovat do základní větve, mění i trusted workflow; GitHub
Actions a vydání TLC/Lean jsou důvěryhodný základ. `ci-verified` neznamená nezávislý
ověřovač: `independentlyVerified` i `currentEligibility` zůstávají `false` a politika
review ani merge se nemění.

## Protipříklad → návrh opravy

Když smyčka zapíše výsledek `counterexample` nebo `failed` (ne jen `runner_error`),
založí po transakci běžný návrh grafu (`graph-additions`, autor `orchestrator` /
`system · formal verification`) s jedinou kartou „Opravit formální ověření: …“. Zadání karty
nese check, head SHA, druhy selhání, cestu k detailu ověření a ke stažení
`counterexample.json`; non-goals zakazují oslabit model nebo důkaz jen kvůli zelené.
Nic se nemění, dokud návrh **nepřijme člověk** obvyklou cestou. Předmět nese
`[verification <prvních 12 znaků ID>]`, takže opakované čtení, restart ani akce
`verification.fix` nevytvoří druhý návrh. Agent-state přidá akci `verification.fix`
(`POST /api/oporahub/verifications/{id}/fix-proposal`, tělo `{project, workspace}`),
která návrh idempotentně založí nebo vrátí; pro jiné výsledky vrací 409.

## Kniha důkazů (ledger)

`GET /api/oporahub/verifications/ledger?project=…&workspace=…` vrací
`{schemaVersion, allowedAxioms, counts, entries[]}`. Řádek má `id` (`lean:<teorém>` nebo
`tlc:<tvrzení>`), `tool`, `kind`, `name`, `source`, `declared`, `status` (`proved`,
`checked`, `counterexample`, `failed`, `unverified`, `unchecked`), `commitSha`, `axioms`,
`trust`, `lastChecked`, `verificationId`, `checkName`. Katalog bere z tohoto checkoutu
(teorémy `tools/formal/lean/OporaHub`, tvrzení pozitivních TLC konfigurací), stav
z nejnovějšího CI záznamu, který dané tvrzení pokrývá. Agent si před psaním důkazu nebo
modelu ověří, že totéž už není `proved`/`checked`. Endpoint nic nezapisuje.

## Nezávislý ověřovač (zbývá)

Nezávislé ověřování vyžaduje zvlášť implementovaný izolovaný runner, vynucené
limity procesového stromu a ověřený původ výsledku mimo repozitář. Vypnutý Docker nebo
chybějící Lean se zobrazí jako nedostupná schopnost. Model, důkaz a test shody skutečné
implementace jsou tři odlišné typy důkazů.

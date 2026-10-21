# Formální ověřování: vstupy, tvrzení a výsledky

OporaHub eviduje formální kontrolu jako neměnný požadavek a nejvýše jeden
neměnný výsledek. Požadavek zachytí skutečnou přijatou revizi, digest zadání,
kartu, execution ID a epochu ze serveru. Nahlášený commit, model a výstup jsou
samostatné podklady; nejsou důkazem, že danému commitu odpovídá implementace.

Tato etapa připravuje společnou evidenci pro TLA+/TLC a Lean. Žádný import
neobdrží důvěru nezávislého ověřovače. `trust` má vždy hodnotu `agent-reported`
a `independentlyVerified` je vždy `false`, včetně výsledku `passed`. Politika
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
`card_leases.py`, repozitář a schéma executions). Job s názvem `formal/tlc` vytvoří
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

Důvěra zůstává `agent-reported` a `independentlyVerified: false`. Workflow je kód
právě posuzovaného PR, takže zelený check je pozorování, ne nezávislý ověřovač.

**Protipříklad → pozornost.** `GET /api/oporahub/agent-state` z nejnovějšího
CI záznamu každého běhu odvodí pozornost. Výsledky `counterexample`, `failed` a
`inconclusive` dají připravenou akci `verification.investigate` (`GET` na detail
ověření, `preconditions` s `headSha`, `outcome`, `failureKinds`). Dají také rozhodnutí
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

**Lean: `not_connected`.** Druh důkazu `lean` je jen deklarovaný zástupný druh
(`EVIDENCE_KINDS` v `opora_formal_checks.py`, `evidenceKinds` v souhrnu). Job
`formal/lean` (`lake build`) je ve workflow vypnutý, dokud repozitářová proměnná
`OPORA_LEAN_ENABLED` nemá hodnotu `true`. Ani potom Canvas check `formal/lean`
nepřevádí na důkaz, protože sestavení není kontrolou důkazu (viz níže). Agent-state
dál uvádí mezeru `lean_verification`.

Důvěryhodný Lean adaptér zatím není k dispozici. Vyžaduje izolované sestavení,
nezávisle zadané očekávané tvrzení, kontrolu proof termů a tranzitivních axiomů;
`sorryAx` a neschválené axiomy se nesmějí přijmout. Samotný log autora ani
`lake build` tuto podmínku nesplňují. Viz [validace důkazů Lean](https://lean-lang.org/doc/reference/latest/ValidatingProofs/).

Nezávislé ověřování vyžaduje zvlášť implementovaný izolovaný runner, vynucené
limity procesového stromu a ověřený původ výsledku. Vypnutý Docker nebo chybějící
Lean se zobrazí jako nedostupná schopnost. Model, důkaz a test shody skutečné
implementace jsou tři odlišné typy důkazů.

# Harness: měření výbavy, předběžný náhled a ověřovatel

Kdy mě číst: vybíráš nebo hodnotíš výbavu karty (`harness.kit`: skripty, pravidla, dokumentace), chceš vědět,
jak si vedla dřív, potřebuješ náhled přijaté výbavy před claimem, nebo ti běh řekl o ověření fixture.
Kontrakty: `docs/harness-kit.md`, `docs/harness-invocations.md`, `docs/harness-server-verifier.md`.

Všechny cesty jsou pod `/api/oporahub`, berou výslovné `project` a `workspace` a nejsou v `opora_read.py`
ani `opora_write.py`: mimo okno OPORA je volej HTTP (níže), v okně OPORA je asistent nevolá.
Neplatný rozsah nebo filtr = 422 `invalid_scope`, neznámý projekt = 404.

**Žádná z těchto cest nic nepovyšuje ani nepřijímá.** Odpovědi nesou `promotionAllowed: false` (a podobné
`executionAuthority`, `permissionsGranted`, `independentlyVerified`); jsou to podklady k posouzení, ne
pravomoc. Neznámá úspěšnost je `null`, ne 0. Prázdný výsledek nedokazuje, že nic neselhalo.

```bash
OPORA=http://127.0.0.1:8740
curl -s "$OPORA/api/oporahub/harness-learning?project=P&workspace=W&limit=20"
curl -s -X POST "$OPORA/api/oporahub/harness-preflight" -H "Origin: $OPORA" \
  -H "Content-Type: application/json" -H "X-Opora-Actor: agent; name=$OPORA_AGENT_NAME" \
  -d '{"project":"P","workspace":"W","nodeId":"NODE","expectedAcceptedHead":"HEAD","expectedContextVersion":"CV"}'
```

Zápis (POST) vždy se stejným `Origin`, `Content-Type: application/json` a identitou (`X-Opora-Actor`);
bez identity 428, tělo nad 4096 B 413, nedostupný nebo změněný podklad 409.

## Čtení (GET, bez identity)

| Cesta | Filtry (kromě `project`, `workspace`) | Odpověď |
|---|---|---|
| `/api/oporahub/harness-learning` | `nodeId?`, `resource?`, `limit` 1–100 (100) | statistiky vybrané výbavy podle verze konfigurace, typu problému a úrovně důkazu (`reported` / `verified`): úspěchy, neúspěchy, neznámé, pokrytí, počet karet, 95% Wilsonův interval, `guardrails` (běhy s incidentem nebo revertem), `limited` |
| `/api/oporahub/harness-memory` | `limit` 1–100 (100) | fronta doručení poznatků do OpenVikingu: stav (`waiting-role`, `submitted`, `superseded`…), pokusy, kód chyby, adresa zápisu |
| `/api/oporahub/harness-invocations` | `nodeId?`, `resource?`, `limit` 1–100 (50) | `harness.invocations/1`: kohorty (resource, digest, adapter, Node, problém) s počtem spuštění, pass/fail, trváním, `latestSourceReceipt`; `receiptWindowLimited`, `cohortsLimited`, `invalidReceipts`, `conflictingInvocations`; hlásí worker, ne server |
| `/api/oporahub/harness-paired-evaluations` | `nodeId?`, `resource?`, `problem?`, `limit` 1–100 (20) | `evaluations[]` (`sourceReceipt` + ověřená zpráva párového srovnání baseline/kandidát), `receiptWindowLimited`, `invalidReceipts`, `conflictingEvaluations` |
| `/api/oporahub/harness-documentation` | `nodeId?`, `resource?`, `limit` 1–100 (50) | nejvýš 100 nahlášených čtení dokumentace (Context7) se zdrojovými receipty; bez procenta úspěchu |
| `/api/oporahub/harness-origin-history` | `nodeId?`, `resource?`, `originScope?`, `originNode?`, `limit` 1–100 (100) | výsledky podle připnutého původu výběru `(scope, node)`; kohorty se **překrývají, nesčítej je**; `window.excluded`, `limited`, `omittedCohortContributions`; `no-store` |
| `/api/oporahub/harness-kit-capabilities` | — | `harness.kit-capabilities/1`: `acceptedKitSchemas` (`harness.kit/1`, `/2`), `contextProtocolVersion: 2`, `selectionSchema`, `limits {resources, bytes}`; před zápisem kitu v2 ověř, že ho server přijímá |

Ověřovatel (čtení s identitou): `GET /api/oporahub/harness-verifier/requests?project&workspace&nodeId?` →
nejvýš 100 nejnovějších záznamů fixture (`domain: harness-fixtures`) + `quarantine`
(`harness.fixture-quarantine/1`, selhané verze kandidátů; `complete: false` = nevěř chybějícím řádkům) + `budget`.

## Zápis a náhledy (POST, identita povinná)

| Cesta | Tělo | Kdo | Odpověď |
|---|---|---|---|
| `/api/oporahub/harness-preflight` | `{project, workspace, nodeId, expectedAcceptedHead, expectedContextVersion}` z vyjednaného kontextu v2 | agent i člověk | `harness.preflight/1`: přijatý kit karty, jeho digest, digest zadání (včetně předávky předchůdců) a identity kontextu; nic nebere (žádný běh ani lease); při claimu porovnej identity znovu |
| `/api/oporahub/harness-shared-memory/publish` | jen `{publication}` (ID ze serverové politiky přenosu) | agent i člověk | zařadí sdílený poznatek fixture do fronty paměti; vlastní text se nepřijímá |
| `/api/oporahub/harness-shared-memory/recall` | jen `{publication}` | agent i člověk | ověřené čtení zpět (`verified-readback`); je to podklad, ne pravomoc |
| `/api/oporahub/harness-verifier/eligibility/retained` | `{project, workspace, verificationId}` | agent i člověk | `harness.retained-stability/1`, `executionAuthority: false` |
| `/api/oporahub/harness-verifier/eligibility/shared` | jen `{publication}` | agent i člověk | `harness.shared-eligibility/1` (aspoň 3 projekty a 2 obrazy) |
| `/api/oporahub/harness-recovery` | `{project, workspace, executionId, token, epoch, sourceExecutionId, resource}` | běh (token) | `harness.recovery-proposal/1`: návrh kitu se starší verzí prostředku; podej ho **návrhem změny zadání** ([planner.md](planner.md)), člověk přijme |
| `/api/oporahub/harness-verifier/requests` | `{project, workspace, executionId, token, epoch, plan: {id, digest}}` | běh (token) | spustí serverové ověření fixture v kontejneru; výsledek čti v historii výše |
| `/api/oporahub/harness-verifier/eligibility` | jako `/requests` | běh (token) | `harness.stability-eligibility/1`, jen čte důkazy |

Cesty s tokenem běhu volá orchestrátor (agent-office). Ty token nikdy nepiš do příkazu, souboru v repozitáři
ani zprávy; `opora_hub.py` je nemá, proto je ručně nevolej.

## Jak s tím pracovat

- Výbavu měň jen návrhem změny zadání karty (`fields`), nikdy přímým zápisem; přijímá člověk.
- Před doporučením prostředku čti `harness-learning` (a `quarantine` ověřovatele): `verified` = lidsky uzavřená
  karta, `reported` = jen hlášení běhu. Vzpomínka z paměti role (`context.roleMemory`) je starší než tyto cesty;
  přijaté zadání má vždy přednost.
- Výsledek běhu může nést `harnessInvocations`, `harnessPairedEvaluation` a `harnessDocumentation`
  (`docs/harness-invocations.md`); hlas jen to, co se skutečně stalo, `readId` / `invocationId` při opakování neměň.

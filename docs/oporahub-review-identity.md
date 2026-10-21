# Lidé v review, metriky, eval sada a opakované nálezy

Druhá část principů ze [Solving code review at Anthropic](https://claude.dev/blog/solving-code-review-at-anthropic/)
nad [automatickým review](oporahub-review-jobs.md):

- **Schválení agentem nikdy není schválení člověkem.** Účty agentů a boti se nepočítají nikdy.
- **Člověk, který agenta řídil, je jeden reviewer.** Kdo přijal plán, podle kterého běh vznikl, se
  počítá jednou, i když PR navíc schválí na GitHubu.
- **Dvě schválení = dva různí skuteční lidé**, ne dva účty.
- **Šum review měří reakce autora**: oprava (`fixed`) proti vypořádání bez opravy (`resolved`),
  vedle kandidátů, které zamítli ověřovatelé.
- **Reverty a incidenty se stávají eval sadou** pro regresní test promptů reviewera.
- **Metriky sledují lidský čas na PR**, míra revertů a incidentů je pojistka (guardrail).
- **Konvence žijí v [`REVIEW.md`](../REVIEW.md)**, opakované nálezy se mění v kontroly.

Vše je deterministické účetnictví backendu; GitHub se jen čte (GET), nic se na něj nezapisuje.
Kód: `backend/canvas/opora_review_identity.py`, `opora_review_humans.py`, `opora_review_metrics.py`,
`opora_review_evals.py`, `opora_review_recurring.py`, společné `opora_review_insight_common.py`;
úložiště `database/repositories/opora_review_insights.py`, schéma
`database/schema/opora_review_insight_schema.py`; router `backend/api/editor/opora_review_insight_routes.py`;
čtení komentářů `backend/integrations/github_identity_reader.py`.

## Registr lidských identit

Identita patří projektu (platí ve všech pracovních prostorech karet). Zakládá, ověřuje a ruší ji
**jen lidská session UI**; agent registr jen čte a nikdy nevidí ověřovací řádek.

1. `POST /api/oporahub/review-identities/claim` `{project, name, githubLogin, operator?}` vrátí
   `identityId` a `marker` tvaru `Opora-Identity: <identityId> <nonce>`. Opakování stejného nároku
   vrátí stejný řádek. `operator: true` značí člověka, který u tohoto Canvasu přijímá plány;
   operátor může být jen jeden (jiný až po zrušení).
2. Člověk vloží řádek **jako samostatný řádek komentáře** do libovolného PR nebo issue v GitHub
   repozitáři projektu, a to ze svého účtu.
3. `POST /api/oporahub/review-identities/{identityId}/verify` `{project, number}` – server mimo
   zámky přečte komentáře (`GET /repos/{repo}/issues/{number}/comments`, nejvýše 3 stránky)
   a identitu ověří, jen když komentář s přesným řádkem napsal **nárokovaný login**, účet je typu
   `User` a není v `approvals.agent_account_ids`. Uloží číselné GitHub ID a důkaz (repozitář,
   číslo, ID a URL komentáře, čas). Jeden GitHub účet patří nejvýše jedné ověřené identitě.
4. `POST /api/oporahub/review-identities/{identityId}/revoke` `{project}` identitu zruší; nový
   nárok pak dostane nový nonce.

`GET /api/oporahub/review-identities?project=` vrací `{items: [{identityId, name, githubLogin,
githubUserId, state: claimed|verified|revoked, operator, claimedAt, verifiedAt, revokedAt, evidence}]}`.

**Mez:** registr dokládá, že daný GitHub účet ovládá člověk, který řádek vložil, a že ho operátor
Canvasu výslovně přiřadil k osobě. Neprokazuje fyzickou odlišnost osob, pokud operátor sám
nárokuje víc účtů; to je vědomé rozhodnutí operátora, ne mezera v počítání.

## Počítání různých lidí v bráně merge

Dokud projekt nemá žádnou ověřenou identitu, brána počítá účty jako dosud. Jakmile existuje aspoň
jedna, `humanApprovalsAtHead` znamená **počet různých ověřených lidí**:

- schválení přesné hlavy se počítá jen od účtu propojeného s ověřenou identitou (autor PR,
  boti a účty agentů nejsou způsobilé nikdy);
- ověřený operátor se započítá jednou, když plánovou revizi běhu PR přijal člověk (přijetí je
  vždy lidské, takže to platí pro každý běh s přijatým plánem);
- schválení z neověřených účtů se jen hlásí v `unverifiedApprovals`.

Brána pak přidá `reviewGate.humans = {mode: "verified_humans", count, identityIds, directorId,
unverifiedApprovals}`. Tím se uzavírá mezera „lokální lidská session nedokáže doložit dva
reviewery“: úroveň `high` (2 schválení) splní operátor plus jeden další ověřený člověk.
Důsledek principu: úroveň `medium` (1 schválení) splní sám ověřený operátor, který přijal plán;
kdo chce u `medium` druhý pár očí, zvýší `approvals.medium` v konfiguraci review úloh.

## Metriky

`GET /api/oporahub/review-metrics?project=&workspace?=&window=30d` (`all` nebo `1d`–`999d`).
Do okna patří PR, jehož první úloha review vznikla po začátku okna; vše ostatní se počítá jen pro
tato PR. Čtení bez zápisu, stejný stav a čas dají stejný dokument.

| Pole | Význam |
|---|---|
| `prsReviewed` | PR s aspoň jednou úlohou review |
| `findingsBySeverity` | Zveřejněné nálezy `important` / `nit` / `pre_existing` |
| `findingOutcomes` | `fixed`, `resolvedWithoutFix`, `rejectedByVoters` (kandidát bez potřebných hlasů), `open` |
| `findingAcceptanceRate` | `fixed / (fixed + resolvedWithoutFix)` – reakce autora; zbytek je šum |
| `voterRejectionRate` | `rejected / (rejected + zveřejněné)` – co odfiltrovalo hlasování |
| `roundsPerPr` | `{mean, max}` dokončených kol |
| `humanApprovalsPerPr` | Průměr schválení přesné hlavy v nejnovějším úplném snímku (bez agentů) |
| `timeToHumanDecisionSeconds` | `{samples, median, mean}` od první úlohy po první lidské rozhodnutí (approve / changes requested z GitHub důkazů nebo rozhodnutí za stropem kol) |
| `guardrails` | `revertRate` a `incidentRate` = podíl PR s revertem / incidentem |
| `incidents`, `prs` | Odkazy na incidenty a řádky po PR (nejvýše 200, `truncated`) |

Míry jsou zaokrouhlené na 4 desetinná místa, bez dat `null`.

## Reverty, incidenty a eval sada

**Revert** je sloučené PR, jehož popis má právě jeden řádek

```text
Opora-Revert-Of: #<číslo>
```

(také `owner/repo#<číslo>` téhož repozitáře). `POST /api/oporahub/review-evals/sync {project}`
přečte stejnou jednu stránku nedávných PR jako uzavření smyčky a zaznamená reverty PR, která
prošla automatickým review. **Incident** připojí člověk nebo agent:
`POST /api/oporahub/review-incidents {project, workspace, repository, number, reference, summary}`
(PR bez review → `404`).

Každý revert a incident deterministicky vytvoří **jeden** eval případ (`caseId` z projektu, PR,
druhu a zdroje). Opakování nic nezmění a případ se nikdy nepřepisuje:

```json
{"schemaVersion": 1, "caseId": "rev_…", "kind": "revert|incident", "repository": "owner/repo",
 "number": 7, "workspace": "…", "diffRef": {"base": "…", "head": "…", "range": "base..head", "url": "…"},
 "baseSha": "…", "headSha": "…", "mergeSha": "…|null", "revertSha": "…|null", "revertNumber": 9,
 "incident": {"reference": "INC-42", "summary": "…"} , "rounds": 2,
 "findings": [{"fingerprint": "…", "severity": "important", "status": "fixed", "round": 1,
               "path": "…", "line": 3, "title": "…"}],
 "rejectedFingerprints": ["…"], "createdAt": "…"}
```

`revertSha` je hlava revertujícího PR. `GET /api/oporahub/review-evals?project=&workspace?=`
vrací `{items}`, `GET /api/oporahub/review-evals/export.jsonl` totéž jako JSONL (jeden případ na
řádek, seřazeno podle vzniku).

### Jak eval spustit (agent-office)

1. Stáhnout `export.jsonl` (identita agenta stačí).
2. Pro každý případ vytvořit čistý worktree na `headSha` a spustit **současné** prompty hledačů
   a ověřovatelů na diff `diffRef.range` (`baseSha` `null` → merge-base s cílovou větví), každý
   slot v čerstvém kontextu, bez přístupu k `findings` případu.
3. Za zachycený případ se počítá potvrzený nález, který se dotýká souboru změněného revertem
   (`git diff revertSha^..revertSha`) nebo popsaného incidentem. Nálezy, které už v případu byly
   (`findings`), slouží jako kontrola, že nová verze promptu neztratila, co dřív našla.
4. Výsledek je míra zachycení na sadě; nová verze promptu nesmí klesnout pod předchozí. Výsledky
   eval běhu se do Canvasu nezapisují.

## Opakované nálezy → kontroly

Třída chyby je druhý segment otisku (`cesta:třída:symbol`), u otisku bez `:` celý otisk.
Třída zveřejněná aspoň na **N různých PR** projektu (výchozí 3, `OPORA_REVIEW_RECURRING_MIN_PRS`
2–50) a dosud nepovýšená přidá do [agent-state](oporahub-agent-state.md) akci
`review.promote_to_check` (`attention: true`, `targetId` = třída, `preconditions
{bugClass, prCount, minPrs}`). Agent pak napíše kontrolu (test, lint, pravidlo v `REVIEW.md`)
a zaznamená ji `POST /api/oporahub/review-recurring/promote {project, bugClass, checkRef}`;
akce zmizí. Stejný `checkRef` znovu nic nemění, jiný je `409`. Přehled:
`GET /api/oporahub/review-recurring?project=`.

## Chyby a ověření

Bez identity `428`; jen pro člověka `403 human_required`; neznámá identita / PR bez review
`404 not_found`; chybějící důkaz `409 identity_proof_missing`; GitHub nedostupný `502`;
ostatní konflikty a neplatná data `409 review_conflict`.

`uv run pytest backend/canvas/test_opora_review_identity.py backend/canvas/test_opora_review_metrics.py
backend/canvas/test_opora_review_evals.py backend/integrations/test_github_identity_reader.py
backend/api/editor/test_opora_review_insight_routes.py` pokrývá ověření identity (špatný účet,
bot, agent, nonce), jedinečnost operátora, počítání různých lidí a režiséra, matematiku metrik,
idempotenci eval případů a detektor opakovaných nálezů.

# Linie: editor s kuličkami a skutečné vynucení workflow

Stav: kontrakt L2 (2026-11-06). Navazuje na `2026-11-06-velin-git-linie.md` (role větví, náhledy, přijetí; M1 v PR #350).
Zadání: editor řádků a kuliček ve Velínu podle skici `image.png` a stejná pravidla pro agenta v terminálu i dělníky
v Kanceláři, vynucená backendem, ne promptem.

## 1. Inventura odpovědností (co dnes funguje)

| Odpovědnost | Kde dnes | Závěr |
|---|---|---|
| Zadává práci | srdce vydává **ticket** (`ticket.issue`, jen role heart) do tabulky `tickets`; tělo `essence / build / doneCriteria`, stavy draft → issued → claimed → in_progress → delivered → verified → closed | Ticket = jednotka práce = **kulička**. Sem se připojí workflow. |
| Bere a odevzdává | dělník bránou `/api/gate` (`ticket.claim`, `ticket.deliver {summary, sha?}`), relace tokenem `X-Opora-Gate-Token`; terminál skillem `opora-control-center` (`opora_gate.py`, `opora_hub.py`) | Stejná cesta pro Kancelář i terminál. `sha` z `deliver` se dnes **nekontroluje** proti gitu. |
| Eviduje běh | `opora_executions` (lease, epocha, token), vazba PR `opora_execution_pull_requests` (`head_sha`, `merge_sha`, `state`), `local-merge` ověří, že commit je předkem HEAD | Běh nenese větev ani worktree. |
| Provádí Git | nikdo v backendu; agent sám (`git merge`, `gh pr merge`), backend jen pozoruje (GitHub jen GET) | Chybí oprávněná služba pro začlenění. |
| Merge fronta | `opora_review_merge_queue`: `ready` = kontroly na přesné hlavě + hlava na špičce báze; pozorování báze jen pro tutéž hlavu | Ochrana proti závodu existuje pro **kontrolu**, ne pro **merge** (nikdo nevynucuje `expectedHeadSha` při merge). |
| Přijetí člověkem | jen plán (revize zadání) a vzhled (screenshoty); M1 přidal přijetí hlavy větve ve Velínu (`<data>/pletor/linie/acceptance.json`) | Přijetí se přesune k ticketu (jeden záznam, ne dva). |
| Ochrana větví | GitHub: žádná protection, žádné rulesets; účet `Pletor` má admin; agenti v terminálu i Kancelář používají **tentýž token** | **Nevynuceno.** Ruleset zablokuje přímé pushe, ale merge přes API agent od služby neodliší bez samostatné identity. |

Srdce dál jen plánuje plátno a vydává tickety; Git mu nepřibývá. Pletor čte a vysvětluje; platnost rozhodnutí ověřuje backend.

## 2. Jeden autoritativní záznam: ticket + `work`

Tabulka `tickets` dostane sloupec `work` (JSON, `ensure_ticket_work_column`, aditivně). Zapisuje ho jen backend
(`backend/agi_pletor/linie/work.py`), nikdy přímo klient:

```json
{"rowId": "row_…", "repository": "<sourcePath nebo REPO_ROOT>", "worktree": "<cesta>|null",
 "branch": "feat/datovy-uzel", "baseBranch": "develop", "baseSha": "<40hex>", "headSha": "<40hex>|null",
 "target": "develop|main|topic/…|null",
 "checks": [{"name": "npm test", "status": "green|red|pending", "sha": "<40hex>", "at": "…", "by": "agent:…"}],
 "preview": {"slug": "…", "sha": "…"}|null,
 "acceptance": {"sha": "…", "revision": "<revize zadání>", "by": "human", "at": "…", "note": "…"}|null,
 "mergeAllowed": {"target": "develop", "targetSha": "<40hex>", "sourceSha": "<40hex>", "by": "human", "at": "…"}|null,
 "merged": {"sha": "<merge commit>", "target": "develop", "at": "…", "by": "opora"}|null,
 "blocked": {"reason": "…", "at": "…"}|null, "deferred": false, "next": "<povolený další krok>"}
```

Stav kuličky se **odvozuje** (`work_state.py`, bez modelu): `open` (bez přijetí) · `awaiting_checks` (headSha bez zelených
kontrol) · `blocked` · `deferred` (experiment) · `accepted_unmerged` („Hotovo, ještě nezačleněno“: přijetí platí pro
headSha, merged null) · `merged` · `stale` (přijetí/povolení pro jiné SHA než headSha nebo jiná špička cíle).
Git je zdroj historie kódu; `merged` vzniká jen z ověřené Git operace (§5), nikdy z hlášení agenta.

Řádky editoru: `<data>/projects/<id>/linie/rows.json` `[{"id": "row_…", "name", "type": "topic|work|experiment|fix",
"ticketId"|null, "branch"|null, "base": {"branch", "sha"}, "target"|null, "collapsed": false, "order"}]`.
Main a Develop jsou pevné řádky s explicitním mapováním `{"main": "main", "develop": "develop"}` v témže souboru.
Přidání řádku **nezakládá** větev, přejmenování ji **nepřejmenuje**; větev se k řádku připojí až `work.branch` ticketu.

## 3. API (`/api/pletor/linie`, jen člověk, pokud není řečeno jinak)

- `GET /board?project&workspace` → `{rows, balls: [{ticketId, rowId, title, state, stateLabel, branch, headSha7,
  createdAt, mergedAt|null, counts: {commits, prs, merges}, links: [{to: ticketId|row, kind: "follows|planned|merged"}],
  preview, acceptance, mergeAllowed, next, blocked}], mapping, realMerges: [...]}`. Plán (`planned`) a skutečný merge
  (`merged`) jsou odlišené druhy spojnic; `follows` = návaznost práce.
- `POST /rows {name, type, base?, target?}` · `PATCH /rows/{id} {name?, target?, collapsed?}` · `DELETE /rows/{id}` (jen prázdný).
- `POST /work {rowId, title, essence, build, doneCriteria, branch, baseBranch, target?}` → založí ticket `issued`
  s `work` (člověk zadává z editoru; srdce dál vydává tickety bránou a `work` jim doplní `POST /work/{ticketId}/attach`).
  Větev se **nezakládá**; `branch` je jméno, které agent založí z `baseBranch@baseSha`.
- `GET /work/{ticketId}` → ticket + work + stav (agent i člověk; agent `X-Opora-Actor` nebo gate token).
- `POST /work/{ticketId}/report {sha, checks?: [{name, status}], worktree?}` (agent i člověk): backend ověří, že `sha`
  existuje a je potomkem `baseSha` na `branch` (`git merge-base --is-ancestor`), uloží `headSha`, kontroly k tomuto SHA.
  Jiná větev nebo SHA mimo větev → 409 `work_mismatch`. Commit **neuzavírá** kuličku.
- `POST /work/{ticketId}/preview` → `previews.start` pro `branch`, uloží `preview.sha`.
- `POST /work/{ticketId}/accept {sha, note}` (jen člověk): `sha == headSha` jinak 409 `head_moved`; zapíše
  `acceptance` s revizí zadání (`card_version`/`acceptedRevision`). Přijetí **neprovádí** merge.
- `POST /work/{ticketId}/allow-merge {target}` (jen člověk): vyžaduje platné přijetí pro `headSha`; zapíše
  `mergeAllowed` se špičkou cíle `targetSha` v okamžiku povolení.
- `POST /work/{ticketId}/merge` (člověk nebo agent; provádí **služba**): §5. 
- `POST /work/{ticketId}/block {reason}` · `/defer` · `/resume` (člověk nebo agent).
- `DELETE /work/{ticketId}/accept` (jen člověk).
- `POST /deployed {sha}` zůstává z M1.

Přijetí a nasazení z M1 (`acceptance.json`) se přesune do `work`; `GET /graph` čte přijetí z ticketů. Soubor
`acceptance.json` zaniká (M1 nebyl přijat, nic se nemigruje).

## 4. Agent v terminálu a dělník v Kanceláři

Skript `tools/linie.py` (bez nových závislostí, `OPORA_BASE_URL` jako skill, identita `OPORA_AGENT_NAME` →
`X-Opora-Actor: agent; name=…`, nebo gate token z `.opora/gate.json`):

- `linie task [--ticket tk_…]`: načte aktivní úkol (ticket s `work`, držený touto relací nebo zadaný); ověří, že `cwd`
  je repozitář/worktree úkolu, že je na `work.branch` a vypíše stav necommitnutých změn. Nesoulad → exit 2 a text
  „jiný kontext, nezačínej“, nic nezahazuje.
- `linie report --check "npm test=green" …`: pošle `HEAD` + kontroly (`/report`).
- `linie preview`: spustí náhled. `linie status`: stav kuličky a povolený další krok.
- `linie merge`: zavolá `/merge`; bez platného přijetí a povolení dostane 409 a vypíše důvod.
- Nedostupný server → exit 3 „evidence nedostupná, kód zachován, blokace“; skript nikdy neslučuje sám.

Kancelář: dělník má gate token; `ticket.deliver {sha}` nově projde `work.report` (stejná kontrola SHA na větvi), takže
sha mimo větev je 409 a `delivered` neznamená hotovo. Lifecycle `verified → closed` nastává až po `work.merged`
(nebo sloučeném PR jako dosud).

`CLAUDE.md`: jeden odstavec „Práce na úkolu Linie: `uv run python tools/linie.py task` před editací, `report` po
commitu, `merge` jen přes službu“. Skill `git-linie` dostane totéž. Žádný z těchto souborů nenese stav.

## 5. Začlenění jako služba (`merge.py`)

Předpoklady, všechny ověřené těsně před operací, jinak 409 s důvodem a bez zápisu:
1. `acceptance.sha == headSha == git rev-parse branch` (zdroj se nezměnil).
2. `mergeAllowed.target == target` a `git rev-parse target == mergeAllowed.targetSha` (cíl se nezměnil od povolení).
3. Všechny kontroly pro `headSha` zelené; žádná `pending`/`red`.
4. Žádný jiný ticket téhož řádku ve stavu `accepted_unmerged` se stejným cílem nezůstává nepřijatý v rozdílu
   (`git log target..branch` obsahuje jen commity tohoto úkolu nebo již přijaté: shortcut: kontrola, že `baseSha`
   je předkem špičky cíle; plné oddělení nepřijatých změn je M3).
Operace: dočasný odpojený worktree `<data>/pletor/linie/merge/<ticket>` na `target`, `git merge --no-ff branch`
(topic→develop, develop→main; pro `feat/*`/`fix/*` do rodiče `--squash` jen když `rows[type] == work` a nikdo z větve
nevětví, jinak merge commit), `git push origin HEAD:target` (lokální ref cíle se aktualizuje, pokud není vybraný v jiném
stromu), zápis `merged {sha}` **z výstupu gitu** (`rev-parse HEAD` po merge). Idempotence: opakované volání s již
zapsaným `merged` vrátí 200 beze změny; když push selže po merge, zapíše se `merged` jen pokud `git merge-base
--is-ancestor branch origin/target` po `fetch` potvrdí začlenění, jinak 409 `push_failed` s instrukcí.

Ochrany: GitHub rulesets pro `main` a `develop` („vyžadovat PR“, bez bypassu) jsou možné (admin), ale služba i agenti
sdílejí token → ruleset by zablokoval i službu. Stav zůstává **nevynuceno** a ukazuje se v editoru, dokud nebude
samostatná identita služby (GitHub App / deploy key). Lokální checkout agent měnit může; sdílené větve chrání služba.

## 6. Editor ve Velínu (část Linie)

Podle prototypu Claude Design (projekt „OPORA – Velín · editor linie (kuličky)“) a skici: pevné řádky Main a Develop
s mapováním, pracovní řádky s přidáním / přejmenováním / sbalením, kuličky z `GET /board` (plná = `accepted_unmerged`
nebo `merged`; obrys = `open`; text stavu vždy), spojnice `follows` tečkovaná, `planned` čárkovaná šipka
s popiskem „plán“, `merged` plná s bodem merge. Hover: název, stav, vznik a začlenění zvlášť, počty commitů | PR |
merge, větev + sha7. Klik: detail (zadání, větev, SHA, commity, PR, kontroly, přijetí, cíl, náhledy s revizí; chybějící
historický náhled přiznat). Akce jen pro člověka: Přijmout tuto revizi, Povolit začlenění do <cíl>, Začlenit (služba),
Zapsat nasazení. Pletor dostane `GET /board` do podkladů (sekce LINIE, strop 1500 znaků) a umí odpovědět, kde se
pracuje, co je hotové, co čeká a kam lze výsledek začlenit.

## 7. Ověření vynucení (testy, bez sítě, dočasné git repo)

1. Přidání řádku nezaloží větev. 2. `report` s commitem nezmění stav na hotovo. 3. `accept` neprovede merge.
4. `merge` bez přijetí → 409. 5. Přijetí starého SHA po novém commitu → `stale`, `merge` 409 `head_moved`.
6. Kontroly chybí nebo červené → `merge` 409, stav ne `accepted_unmerged`. 7. `linie task` v jiném adresáři/větvi → exit 2.
8. Cíl se posunul mezi `allow-merge` a `merge` → 409 `target_moved`. 9. Obnovení relace: `linie task` najde týž ticket.
10. Opakované `report`/`merge` → žádný duplicitní merge ani milník. 11. Merge proběhl, hlášení selhalo → `merged`
se zapíše z gitu při dalším volání. 12. Plánovaná spojnice se v `board` nikdy nevrací jako `merged`.

## 8. Postup

L2a backend (`work.py`, `work_state.py`, `rows.py`, `merge.py`, routy, migrace, gate `deliver` → `report`) + `tools/linie.py`
+ testy §7 · L2b editor ve Velínu podle prototypu · L2c Pletor podklady + skill + CLAUDE.md · náhled bez merge do main,
pak připomínky člověka.

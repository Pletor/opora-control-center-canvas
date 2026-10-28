# Lokální sloučení karty (projekt bez GitHubu)

Stav: kontrakt, rozhodnutí uživatele 2026-10-28. Kód ho provádí, nemění. Navazuje na
[jedinou definici hotovo](oporahub-plan-steps.md#jediná-definice-hotovo) a [plnou autonomii](plna-autonomie-agenta.md).

## 1. Proč

Hotovo karty OporaHubu chce `gate_ready`, `merged` a `plan_written_back`. Ty dnes vznikají jen z PR na GitHubu
(`/executions/{id}/pull-request`, GitHub, zápis plánu po sloučení). Projekt bez GitHubu (lokální projekt, Git bez
vzdáleného repa) proto kartu nikdy neuzavře – ani člověk, ani agent. Uživatel chce, aby agent stavěl a uzavíral
práci v OPOŘE autonomně v každém projektu.

## 2. Pravidlo

- Projekt bez vazby na GitHub má režim brány **`local`** (vedle `review` a `external`, pole `gate` v `cards[].dod`).
  Režim se odvodí, nikdy nezadává: GitHub vazba projektu existuje → dnešní chování beze změny.
- Agent (nebo člověk) ohlásí sloučení: `POST /api/oporahub/executions/{executionId}/local-merge`
  `{commit}` → server v repozitáři projektu ověří, že commit existuje a je předkem `HEAD` cílové větve projektu
  (lokální projekt = aktuální větev jeho repa), a zapíše **vazbu stejného tvaru jako PR** (`state: "merged"`,
  `source: "local"`, `commit`, bez URL). Neplatný commit → 422, commit mimo cílovou větev → 409.
- Po zapsání vazby proběhne **stejný zápis plánu zpět** jako po sloučeném PR (`planWrittenBack`), žádná druhá cesta.
- `gate_ready` v režimu `local` = vazba `merged` a poslední kontroly karty na tomto commitu (pokud karta nějaké má:
  `checks` / check-run / ověření harnessu) prošly. Karta bez kontrol: `gate_ready` = `merged`.
- `human_close` se řídí [plnou autonomií](plna-autonomie-agenta.md): bez ní uzavírá člověk, s ní agent.
- Idempotence: opakované ohlášení téhož commitu vrátí stejnou vazbu; jiný commit nahradí starší lokální vazbu.
- Záznam činnosti: `local_merge` s původcem a commitem.

## 3. Co se nemění

Projekty s GitHubem (režimy `review`, `external`), tvar `cards[].dod` kromě nové hodnoty `gate: "local"`, žádná
změna schématu existující tabulky (vazba se ukládá tam, kde dnes PR vazby; když by to bez změny schématu nešlo,
implementace se zastaví a zeptá).

## 4. Skill

`opora-control-center` popisuje `local-merge`, režim `local` a pořadí práce agenta: kroky → přijetí karty →
commit → `local-merge` → kontroly → cesty → `close_card`.

## 5. Upřesnění z implementace (2026-10-28)

Jen upřesnění, pravidla §2–§4 platí beze změny.

- **Odvození režimu.** `local` = projekt nemá konfiguraci GitHubu (`opora_review_scope.configuration` selže:
  lokální složka bez připojeného repozitáře, Git bez GitHub `origin`, vestavěný návrh `draft`). Jinak beze změny
  `review` / `external` (`backend/canvas/opora_card_done.py`: `local_mode`, `facts(..., local_checks=)`).
- **API.** `POST /api/oporahub/executions/{executionId}/local-merge`, tělo `{project, workspace, commit}` (commit 7–64
  malých hex), volitelně `token` + `epoch` běhu. Odpověď = DTO vazby jako `GET …/pull-request` (`state: "merged"`,
  `source: "local"`, `repository: "local"`, `number: null`, `commit`, `mergeSha`, `headRef` = větev,
  `planWrittenBack: true`, `events`). Chyby: 428 bez identity, 422 `invalid_commit` (tvar nebo neexistující commit),
  409 `commit_not_on_branch` (není předkem `HEAD`), 409 `execution_conflict` (projekt s GitHubem, projekt bez
  složky repa, běh mimo projekt/prostor z těla, běh už má PR vazbu z GitHubu, neplatná pole).
- **Projekt požadavku.** `project` a `workspace` jsou v těle povinné: middleware autonomie z nich pozná projekt
  a služba čte běh jen v tomto projektu a prostoru (`{executionId}` z jiného projektu = 409). Totéž platí pro
  `close_card` (`POST /api/desktop-v3/state` nese `project` v těle).
- **Kdo smí.** Člověk vždy. Agent pro běh s platným převzetím nebo s odevzdaným výsledkem (stejné pravidlo jako
  vazba PR); jiný běh jen s plnou autonomií. Ověření gitem (`rev-parse --verify <commit>^{commit}`,
  `merge-base --is-ancestor <commit> HEAD`) běží v repozitáři projektu (zdrojová složka, jinak klon) mimo zámky.
- **Úložiště.** Řádek tabulky `opora_execution_pull_requests` beze změny schématu: `repository = "local"`,
  `number = 0`, `head_sha = merge_sha = commit`, `head_ref` = větev, `source = "local"`, `enrollment = "unavailable"`.
  Smyčka sladění GitHubu ho nikdy nečte (bere jen `open` / `closed` a `pending`).
- **Zápis plánu zpět.** Sdílená funkce `write_back` (`backend/canvas/opora_execution_pr_closure.py`): událost
  `execution.merged` jednou na commit, `awaitingHumanClose`, ukončení běžícího běhu, události `merge.done`,
  `writeback.done`, `decision.created` (u lokálního sloučení bez čísla PR, v datech `source: "local"`, `commit`).
- **Kontroly v `gate_ready`.** Kontroly karty = poslední běh `POST /api/check-run` se `scope` = ID karty. Má-li karta
  běh, musí být `green` a jeho `sha` shodné (prefix) se sloučeným commitem; bez běhu projde jen karta bez
  deklarovaných `checks`. Ověření harnessu se do lokální brány zatím nepočítá.
- **Záznam činnosti.** Řádek cesty `…/local-merge` nese v `summary` `local_merge commit=<sha>` s původcem a jménem
  agenta (`describe` dostává cestu požadavku).
- **agent-state.** `cards[].dod.gate = "local"` a akce `close_card` s `preconditions.gate: "local"`. Při `autonomy.full` je
  každá akce blokovaná jen kvůli člověku (`human_only`) pro agenta `status: "ready"` s `autonomy: "full"`; rozhoduje
  dál server při zápisu.

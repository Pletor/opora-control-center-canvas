# Rozhraní OporaHubu (fáze 2): smyčka, karta, pro agenty

OporaHub (Alt+3) je jedna stránka nad jedním dokumentem
[`GET /api/oporahub/agent-state`](oporahub-agent-state.md). Vychází z návrhu Claude Design
„OporaHub — přehled“ (`01-prehled`, `02-karta`, `03-agenti`, tokeny `oh-tokens.css` převzaté
z `frontend/design-tokens`). Ukázková čísla návrhu se nepřebírají; vše je ze serverového snímku.

## Tři pohledy

| Pohled | Kde | Co ukazuje |
|---|---|---|
| **Přehled** (výchozí) | záložka Přehled | Horní pás: přijatá hlava, drift pracovní verze (a počet návrhů na starém základu), mix rizika čekajících návrhů, nejvýše 3 rozhodnutí člověka. Pod ním smyčka deseti etap `plan → … → plan_writeback` jako „had“ (1–5 zleva doprava, 6–10 zpět) se spojkami a pata se známými mezerami. |
| **Karta** | záložka Karta, klik na cíl `claim`, nebo `?ohCard=<nodeId>` | Drawer s cestou karty: přijatý základ → změny zadání → převzetí (lease, epocha) → důkazy → PR → zápis do plánu. Zastaralé návrhy visí na červené přerušované větvi nad osou. Pod osou rozpočet běhu, přijetí vázaná na revizi a druhy důkazů. Výběr karty v hlavičce. |
| **Pro agenty** | záložka Pro agenty, nebo `?ohView=agents` | Protokol (GET → preconditions → zápis s requestId → 409 znovu GET), hlavy pro CAS, fronta akcí (id, sloveso, metoda, cesta, preconditions, rozpočet, stav), přesný JSON s tlačítkem „kopírovat JSON“ a tabulka kontraktu `data-oh-*`. |

Rozhodnutí `close_card` (PR sloučeno, karta čeká na potvrzení člověkem) otevře detail karty, kde krok
Merge → plán ukazuje „čeká na uzavření člověkem“ a merge SHA; kartu uzavírá jen člověk (`human_only`).
Klik na etapu, rozhodnutí nebo cíl akce otevře **existující** detail (návrh zadání/grafu/obsahu,
běh, důkazy, pravidla…). Pata „Podrobné formuláře“ dál otevírá všechny původní drawery: zadání karty,
návrhy grafu, změny obsahu, přijímání návrhů, pravidla přijetí, běhy, limity, proces Control Center,
důkazy a sledování GitHubu, pravidla review, formální podklady, rozhraní pro agenty a starší historii.
Každý drawer má ✕ vpravo nahoře; ✕ i Escape ho zavřou a vrátí focus.

## Vlna 5: brána review, lidé, metriky, auto-rebase, důkazy a plátno

| Kde | Co ukazuje | Zdroj |
|---|---|---|
| Přehled · etapa **Review** | Stav brány merge (`✕ blokuje` / `◷ čeká` / `✓ žádná brána nedrží` / `◌ automatické review vypnuto`) a kód pravidla, které ji drží; lidské znění je důvod etapy | `stages[review]` + `gaps` |
| Přehled · etapa **Návrh změny** | Počet otevřených konfliktů auto-rebase; klik otevře drawer konfliktů | `actions[verb=proposal.resolve_conflict]` |
| Pro agenty · fronta | Skupina slovesa (`brána review`, `ověření`, `auto-rebase`, `smyčka`) a `◷ pozornost`; česká jména pro `review.claim`, `review.self_checks`, `pr.update_branch`, `review.promote_to_check`, `verification.*`, `proposal.resolve_conflict` | `actions[]` |
| Karta · krok **Review · brána merge** | Na ose etapa karty (`cards[]`); pod osou panel brány: stav, pravidlo, které drží, všechny důvody, otevřené důležité nálezy, bezpečnostní review, požadovaná schválení proti **různým ověřeným lidem na hlavě** (`reviewGate.humans`), neověřená schválení, vlastní kontroly, `stale_against_main` (o kolik commitů), `template_incomplete` (chybějící sekce) a související akce | `GET /api/oporahub/review-jobs/gates` |
| Karta · **Formální důkazy** | Lean, TLC a shoda s implementací (`formal/conformance` zatím jen v CI → `◌ nenapojeno`), výsledek, důvěra `nahlášeno agentem` / `ověřeno CI`, historický podklad; rozhodnutí `verification.fix` jako tlačítko „Založit návrh opravy“ (přijímá člověk) | `GET …/verifications?nodeId=` + `actions[]` |
| Karta · **Historie a blame** | Přijaté revize karty (i „auto-rebase z … · původně …“) a pro každý klíč poslední revize a autor | `GET …/history/card/{id}`, `…/blame/card/{id}` |
| Pata · **Konflikty auto-rebase** | Seznam konfliktů, tabulka `base / ours / theirs` po polích, volba strany, kopírovatelný návrh řešení, připojení nového návrhu (`…/resolve`) a „Spustit auto-rebase teď“ | `GET/POST …/auto-rebase/*` |
| Pata · **Metriky review** | Malá infografika: nálezy podle závažnosti, co se s nálezy stalo, přijetí a šum, odfiltrováno hlasováním, kola na PR, čas do rozhodnutí člověka, pojistky revertů a incidentů, počet eval případů a odkaz na `export.jsonl` | `GET …/review-metrics`, `…/review-evals` |
| Pata · **Kniha důkazů** | Počty podle stavu, filtr nástroje, řádky s důvěrou, commitem a axiomy (axiom mimo povolené je zvýrazněn) | `GET …/verifications/ledger` |
| Pata · **Lidé v review (jen člověk)** | Nárok identity → řádek `Opora-Identity: <id> <nonce>` ke zkopírování a vložení jako samostatný řádek komentáře na GitHub, ověření číslem PR/issue, registr (ověřeno / čeká / zrušeno, operátor), zrušení s potvrzením | `…/review-identities*` |
| **Plátno Editoru** | Nad pravým horním rohem každé karty odznak `značka · etapa · slovo`; klik přepne do OporaHubu s otevřeným drawerem karty. Vypínač: Nastavení → Plátno → „Odznaky etap OporaHubu na kartách“ (výchozí zapnuto) | `cards[]` agent-state |

**Nonce nikdy nejde agentovi.** Řádek `Opora-Identity` vrací server jen lidské session a UI ho ukazuje
jen jako text v draweru: není v žádném `data-oh-*` atributu ani v zrcadle `oh-review-identities`
(funkce `publicIdentities` ho odstraní, hlídá test).

## Zdraví, tvar a role

| `health` | Tón | Značka | Vzhled |
|---|---|---|---|
| `ok` | zelená | ✓ | plný horní pruh |
| `waiting` | zlatá | ◷ | plný horní pruh |
| `blocking` | červená | ✕ | červený rámeček |
| `not_connected` | šedá | ◌ | přerušovaný rámeček, spojka přerušovaná „nenapojeno“ |

Barva nikdy nenese význam sama: vždy značka a slovo. Kroky člověka (přijetí, review, merge) mají
zlatý zaoblený štítek, kroky agenta (převzetí, práce, důkazy, PR) tyrkysový hranatý. Strojový
`reason` se překládá do češtiny; neznámý kód se zobrazí doslova.

## Data a obnova

- Jediné periodické čtení agent-state: `useAgentState` nad sdíleným `agentStateStore`
  (`frontend/hub/oporahub-agent-state/logic/agent-state-store.ts`): přehled OporaHubu i odznaky na plátně odebírají
  **jeden** poller na prostor (10 s po dokončení čtení, jen ve viditelném okně); poslední odběratel ho
  zastaví. Posílá `If-None-Match`; `304` jen potvrdí čerstvost snímku.
- Detaily vlny 5 (brána, důkazy, historie, konflikty, metriky, kniha, identity) čtou jednou při otevření
  a po „Obnovit“ (`frontend/hub/oporahub-mirror/logic/use-hub-read.ts`); nic z nich nepolluje.
- Starší hooky zůstávají pro detaily, které agent-state nenese (řetěz změnových sad karty, běhy,
  rozpočet, obsah). Periodická čtení změn obsahu, formálních podkladů, sledování GitHubu a review
  návrhů běží jen s otevřeným detailem (`onDetailOpenChange` → `App`).
- Parser odmítne dokument jiného projektu/prostoru, neúplnou smyčku a neznámé zdraví.

## Kontrakt `data-oh-*` (DOM pro agenty)

Agent nečte obrazovku. Čte buď JSON zrcadlo, nebo atributy:

```js
JSON.parse(document.getElementById("oh-agent-state").textContent) // celý dokument agent-state
document.querySelectorAll('[data-oh-action-status="ready"]')      // připravené akce
```

| Prvek | Atributy | JSON cesta |
|---|---|---|
| Kořen | `data-oh-view` (`overview`/`agent`), `data-oh-accepted-head`, `data-oh-etag`, `data-oh-generated-at`, `data-oh-schema-version` | `heads.acceptedHead`, `generatedAt` |
| Zrcadlo | `<script type="application/json" id="oh-agent-state">` (`<` escapováno jako `<`) | celý dokument |
| Dlaždice | `data-oh-field` (`acceptedHead`, `drift`, `staleProposals`, `riskMix`, `decisions`) + `data-oh-value` | `heads.*`, `riskMix`, `decisions.length` |
| Etapa | `data-oh-stage`, `data-oh-health`, `data-oh-reason`, `data-oh-count` | `stages[]` |
| Spojka | `data-oh-link="from->to"`, `data-oh-link-state` (`plain`/`warn`/`broken`) | odvozeno |
| Rozhodnutí | `data-oh-decision`, `data-oh-action-id` | `decisions[]` |
| Akce | `data-oh-action-id`, `data-oh-action-status`, `data-oh-verb`, `data-oh-method`, `data-oh-path`, `data-oh-target`, `data-oh-block-reason` | `actions[]` |
| Fakt CAS | `data-oh-field` + `data-oh-value` (`acceptedHead`, `graphDigest`, `contextVersion`, `workingDiffers`, `budgetPolicyHead`) | `heads.*` |
| Mezera | `data-oh-gap`, `data-oh-health="not_connected"` | `gaps[]` |
| Karta | `data-oh-view="card"`, `data-oh-node-id`; kroky `data-oh-step`, `data-oh-revision`, `data-oh-changeset`, `data-oh-parent`, `data-oh-stale`, `data-oh-accepted`, `data-oh-execution`, `data-oh-epoch`, `data-oh-execution-state`, `data-oh-evidence-for`, `data-oh-pr-link`, `data-oh-writeback` (`awaiting_human_close` + `data-oh-merge-sha` u `close_card`) | agent-state + `…/changesets`, `…/executions` |
| Pata | `data-oh-detail` (druh původního detailu) | — |
| Etapa Review / Návrh | `data-oh-gate-status` (`blocked`/`pending`/`clear`/`off`), `data-oh-gate-rule`; `data-oh-conflicts` | `stages[review]`, `actions[verb=proposal.resolve_conflict]` |
| Akce (doplněk) | `data-oh-group`, `data-oh-attention` | `actions[].verb`, `.attention` |
| Odznak na plátně | `data-oh-view="canvas-badges"` + `data-oh-etag`; `data-oh-card-badge`, `data-oh-stage`, `data-oh-health`, `data-oh-reason`, `data-oh-execution`; zrcadlo `script#oh-card-stages` | `cards[]` |
| Krok Review karty | `data-oh-step="review"`, `data-oh-card-stage`; panel `data-oh-review-gate` (executionId), `data-oh-gate-status`, `data-oh-gate-rule`, `data-oh-gate-reason`, `data-oh-open-important`, `data-oh-security`, `data-oh-approvals-required`, `data-oh-approvals-verified`, `data-oh-humans-mode`, `data-oh-self-checks`, `data-oh-stale-against-main`, `data-oh-template-incomplete`; zrcadlo `script#oh-review-gates` | `…/review-jobs/gates` |
| Formální důkazy karty | `data-oh-proof-kind`, `data-oh-proof-status`, `data-oh-trust`, `data-oh-verification`; tlačítko `data-oh-verb="verification.fix"` + `data-oh-action-id`; zrcadlo `script#oh-card-proofs` | `…/verifications?nodeId` |
| Historie karty | `data-oh-view="card-history"`, `data-oh-history-revision`, `data-oh-proposal`, `data-oh-blame-key`, `data-oh-revision`; zrcadlo `script#oh-card-history` | `…/history/card`, `…/blame/card` |
| Konflikty | `data-oh-view="conflicts"`, `data-oh-conflict`, `data-oh-conflict-status`, `data-oh-proposal`, `data-oh-proposal-kind`, `data-oh-field-key`, `data-oh-choice`; zrcadlo `script#oh-auto-rebase-conflicts` | `…/auto-rebase/conflicts` |
| Lidé v review | `data-oh-view="identity"`, `data-oh-identity`, `data-oh-identity-state`, `data-oh-operator`, `data-oh-github-login`; zrcadlo `script#oh-review-identities` **bez `marker`** | `…/review-identities` |
| Metriky review | `data-oh-view="review-metrics"`, `data-oh-window`, `data-oh-metric` + `data-oh-value`; zrcadlo `script#oh-review-metrics` | `…/review-metrics`, `…/review-evals` |
| Kniha důkazů | `data-oh-view="proof-ledger"`, `data-oh-ledger-entry`, `data-oh-ledger-status`, `data-oh-trust`, `data-oh-metric` + `data-oh-value`; zrcadlo `script#oh-proof-ledger` | `…/verifications/ledger` |

Zdroj pravdy pro tabulku v aplikaci je `frontend/hub/oporahub-agents/logic/contract.ts`.
Atributy jsou jen ke čtení; každý zápis dál ověří původní API a akce `human_only` zůstávají člověku.

## Kód

`frontend/hub/oporahub-agent-state` (čtení a mapování, testy), `oporahub-loop` (Přehled),
`oporahub-card` (detail karty, test `card-timeline.test.ts`), `oporahub-agents` (Pro agenty),
`oporahub-health` (značky), `oporahub-overview` (rám, záložky, zrcadlo, pata, drawer),
`oporahub-workspace` (skládání, přímé odkazy `?ohView=agents` / `?ohCard=<nodeId>`).
Vlna 5: `oporahub-review-gate` (krok Review karty), `oporahub-proofs` (důkazy karty, kniha důkazů),
`oporahub-card-history`, `oporahub-conflicts`, `oporahub-review-metrics`, `oporahub-identity`,
`oporahub-mirror` (jednorázové čtení a zrcadla `oh-*`) a na plátně `editor/canvas/loop-badges`.

## Ověření

`npm test` (mapování agent-state → view-model, parser, 304, escapování zrcadla, cesta karty,
kontrakt, vykreslení atributů), `npm run build` a screenshoty světlý/tmavý režim při 1440 a 390 px
nad lokálně naplněným backendem (`tools/serve-preview.py` na vlastním portu, nikdy 8740).

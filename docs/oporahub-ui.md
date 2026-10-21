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

- Jediné periodické čtení přehledu: `useAgentState` (sdílený `createPoller`, 10 s po dokončení
  čtení, jen ve viditelném okně). Posílá `If-None-Match`; `304` jen potvrdí čerstvost snímku.
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

Zdroj pravdy pro tabulku v aplikaci je `frontend/hub/oporahub-agents/logic/contract.ts`.
Atributy jsou jen ke čtení; každý zápis dál ověří původní API a akce `human_only` zůstávají člověku.

## Kód

`frontend/hub/oporahub-agent-state` (čtení a mapování, testy), `oporahub-loop` (Přehled),
`oporahub-card` (detail karty, test `card-timeline.test.ts`), `oporahub-agents` (Pro agenty),
`oporahub-health` (značky), `oporahub-overview` (rám, záložky, zrcadlo, pata, drawer),
`oporahub-workspace` (skládání, přímé odkazy `?ohView=agents` / `?ohCard=<nodeId>`).

## Ověření

`npm test` (mapování agent-state → view-model, parser, 304, escapování zrcadla, cesta karty,
kontrakt, vykreslení atributů), `npm run build` a screenshoty světlý/tmavý režim při 1440 a 390 px
nad lokálně naplněným backendem (`tools/serve-preview.py` na vlastním portu, nikdy 8740).

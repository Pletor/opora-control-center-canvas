# Panel bloku a portu podle reality

**Stav: rozbor hotový, logika čeká na schválení člověkem, pak návrh UX/UI přes Claude Design (2026-10-31).**
Člověk: „Vytvořený blok má nefunkční menu, agenti ho nevyplňují a nepoužívají. Musí tam být věci potřebné
k úkolu nebo práci agenta, třeba log a historie relací workerů, kteří na tom pracovali.“

## Jak to vypadá dnes

![Menu vytvořeného bloku, 2026-10-31](obrazky/2026-10-31-menu-bloku-dnes.png)

Kód: `frontend/editor/node-detail/tree/`, `frontend/editor/block-editor/`, kontrakt `docs/karta-pro-agenty.md`.

## Rozbor (jen čtení, kód + živá data 8740)

Bloky dnes nikdo neplní. Píše je jen zastaralá cesta `agent-output` / `POST /desktop-v3/block`, kterou skill
zakazuje (`references/hub-loop.md:27`, `legacy.md:9-12`); srdce plánuje jen `spec.steps` (`opora_heart.py`),
bloky nezná. Živý Ample (od 2026-10-30): 0 zápisů `agent-output`, 0 bloků na 11 kartách. Starý lokální Ample
453× `agent-output` (naposledy 2026-10-11), Tajemství 6× (naposledy 2026-10-18).

| sekce | kdo píše | kdo čte | v datech (živý Ample / Tajemství) | verdikt |
|---|---|---|---|---|
| Název, Popis | UI, canvas-plan | node_brief, tvář karty | 0 / 11 z 12 | jen ke čtení |
| Porty | UI, canvas-plan | `CardBlockPorts`, node_brief | 0 / 12 | ponechat jako vazbu; spawn z portu smazat |
| Stav otevřeno/splněno/… | agent-output, UI | checklist, autonomie, spawn | 0 / 5× met | nahradit stavem kroků (agent-state) |
| Podmínka splnění | canvas-plan, UI | node_brief `blockConditions` | 0 / 10 | nahradit `spec.acceptance` + `checks` |
| Splněno → / Nesplněno → | UI | nikdo | 0 / 0 | smazat |
| Poznámka stavu | agent-output | tvář karty | 0 / 5 | smazat |
| Štítky, TODO, Inspirace, Podbloky | UI | jen editor | 0 / 0 | smazat |

## Co OPORA o práci na kartě ví (zdroje dat pro nový panel)

- `GET /api/oporahub/agent-state` `cards[]`: `stage`, `reason`, `nextActionId`, `steps.items`, `pr`, `lease`,
  `dod.missing`, `order`.
- `GET /api/oporahub/executions?nodeId=`: relace dělníků (`owner`, `createdAt`, `state`);
  `GET /api/oporahub/executions/{id}/results`: `summary`, `stepResults[{stepId, status, evidence{notes,
  checks, commits}}]`, `risk`.
- `GET /api/oporahub/events` (`nodeId`, `kind`, `actor`, `prNumber`) a `GET /api/activity-log?nodeId=`,
  `/api/activity-log/latest-by-node` (#228).
- Zprávy na vazbách `state.edges[edgeId]`: `summary`, `handoff`, `agent`, `updatedAt`.
- Detail karty už má záložky Běh / Historie / Review & PR (`hub/oporahub-card-drawer`), panel na ně odkazuje,
  nekopíruje je.

## Návrh logiky panelu (ke schválení)

1. **Hlavička:** název a popis bloku (jen čtení), ID.
2. **Práce na kartě:** etapa a další krok, kroky ✓/…, PR #N, kdo kartu drží a do kdy.
3. **Relace dělníků:** kdo, kdy, stav; rozbalení = shrnutí, kroky s důkazem a commity.
4. **Log změn:** posledních ~10 událostí karty („kdo · kdy · co“), odkaz „Celá historie“ do detailu karty.
5. **Port:** popisek, cílová karta a poslední zpráva na vazbě (co předal a kdo).

Krok 1 (UI): mrtvé sekce pryč z panelu, nové sekce 2–5; uložená data beze změny.
Krok 2 (zvlášť, se souhlasem): úklid backendu a skillu, úprava `docs/karta-pro-agenty.md`, případné smazání
starých polí bloků z dat (372 bloků v lokálním Ample, 12 v Tajemství) – mazání dat jen se souhlasem člověka.

## Návrh UX/UI

Po schválení logiky navrhne vzhled panelu Claude Design (wireframe a varianty), teprve pak implementace
po dílcích podle `docs/pravidla-struktury.md`.

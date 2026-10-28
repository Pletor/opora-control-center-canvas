# Strážci: nálezy tichého dohledu a co s nimi

Kdy mě číst: v `agent-state` vidíš `guards` nebo u karty `guardFindings`, v `node-brief` máš `guards`, nebo
chceš vědět, co hlídá backend sám. Kontrakt: `docs/strazci.md`.

Strážci jsou deterministické procesy v backendu (bez modelu a bez člověka). Sledují plátno, běhy a Git a
**jen hlásí**: nemění zadání, kroky ani obsah karet, nic nepřijímají ani nezamítají a nic neuvolňují.
Nález se neodškrtává: zmizí sám (`resolvedAt`), až pravidlo přestane platit. Opakování se nehlásí.

## Kde nálezy uvidíš

| Kde | Tvar | Poznámka |
|---|---|---|
| `agent-state` → `guards` | `{open: {block, warn, info}, findings: [≤ 20, block první]}`; nález `{key, guard, rule, severity, message, nodeId?, journeyId?, executionId?, workspaceId, firstSeen, lastSeen}` | jen nálezy daného prostoru (`workspaceId`, výchozí `draft`) |
| `agent-state` → `cards[].guardFindings` | `{count, severity}` (nejvyšší závažnost) | karta bez nálezu pole nemá |
| `node-brief` → `guards` | `[{rule, message}]`, nejvýš 3 otevřené nálezy karty | mimo `specification`, `contextVersion` nemění |
| `GET /api/strazci?project=` | `{guards: [{id, label, every_s, lastRunAt, lastOkAt, lastError?, open: {block, warn, info}}], open: {…}}` | stav strážců; `lastError` = strážce spadl (data neber jako aktuální) |
| `GET /api/strazci/findings?project=&node=&open=1` | `{findings: [{key, guard, rule, severity, message, nodeId, workspaceId?, journeyId?, data?, firstSeen, lastSeen, resolvedAt}]}` | block první, pak nejnovější; `open=0` přidá vyřešené (drží se 14 dní); max 500; **včetně** strážce `mapa` |

```bash
OPORA=http://127.0.0.1:8740
curl -s "$OPORA/api/strazci?project=P"
curl -s "$OPORA/api/strazci/findings?project=P&node=NODE"
```

Jen čtení, bez identity; neznámý projekt = 404. `opora_read.py` tyto cesty nemá. Události `guard.alert`
(nový nález) a `guard.resolved` jdou tichým feedem ([events.md](events.md)), karta se kvůli nim neobnovuje.

**Díra mapy jen jednou.** Díry mapy počítá jen kontrola mapy a agentům je dává `mapGaps` (agent-state) a
`node-brief.architecture.holes` ([hub-loop.md](hub-loop.md)). Strážce `mapa` je ukládá jen kvůli změnám,
odznakům a trendu, proto `guards` v agent-state i v briefu nálezy s `guard: "mapa"` a pravidla `journey.failed` / `journey.stale`
(v mapě jako `journey.unverified`) **vynechávají**. Díru
mapy řeš podle `mapGaps` / `holes`, ne podle `/api/strazci/findings`.

## Pravidla a co udělat

`severity`: `block` = brání postupu a patří člověku nebo bráně, `warn` = něco se stáčí, `info` = jen zpráva.

| Strážce (interval) | `rule` | Co znamená | Co udělá agent |
|---|---|---|---|
| `mapa` (60 s, při změně hlavy) | pravidla kontroly mapy (`section.unrealized`, `journey.unrealized`, …) | díry mapy nad přijatou architekturou; `page.no-goal` a `journey.broken` jsou `block` | nic navíc: pracuj z `mapGaps` (`owner: "agent"`); `page.no-goal` a `journey.broken` patří člověku |
| `prace` (30 s) | `work.lease-expired` | nárok karty je po termínu, karta se dál tváří, že se staví | tvůj běh: propadl, heartbeat nepomůže; `opora_hub.py state --fresh` a nový claim přes akci. Cizí: nic, nárok uvolní příští claim |
| | `work.no-heartbeat` | živý běh bez zprávy déle než 10 min | tvůj běh: hned `opora_hub.py heartbeat` (po ⅓ TTL); cizí: nic |
| | `work.step-stalled` | krok `running` (`step.started`) déle než 30 min bez další zprávy | tvůj běh: nahlas krok (`opora_hub.py step`, `done` nebo `failed` s evidencí) nebo pokračuj; cizí: nic |
| `cesty` (120 s) | `journey.failed` | poslední čerstvý doklad cesty neprošel; `nodeId` = stránka cíle prvního neúspěšného přechodu | na své kartě oprav přechod a cestu přehraj znovu ([journey-run.md](journey-run.md)); jinak jen čti |
| | `journey.stale` | doklad cesty je starší než plán (mapa se od běhu změnila); `nodeId` = první stránka cesty | přehraj cestu znovu a pošli nový doklad ([journey-run.md](journey-run.md)) |
| | `journey.blocks-card` (`block`) | karta po merge čeká na uzavření člověkem, ale brání jí brána cest; `journeyId` = první blokující cesta, `data.journeys` všechny | doložit čerstvý prošlý běh každé cesty z `data.journeys`; kartu uzavírá jen člověk |
| `pravda` (300 s) | `truth.worktree-behind` | větev worktree domény je za hlavní větví o víc než 20 commitů; `data {behind, branch}` | ve **svém** worktree `git fetch` a `rebase` na `origin/main` (ne merge, `docs/cista-linie.md`); cizí worktree neměň |
| | `truth.proposal-stale` | návrh zadání, grafu nebo obsahu čeká na člověka déle než 24 h; `data {proposalId, kind, waitingHours}` | nic nepřijímáš ani nezamítáš a neposíláš duplicitní návrh; zmiň ho člověku v závěrečné zprávě |

Dnes běží všech šest strážců. Dva poslední nálezy nevydávají:

- `zkusenost` (při události: tick dočte od kurzoru `card.closed`, `merge.done` a nové doklady cest) zapíše
  deterministický záznam `opora.guard-experience/1` `{card, role, passed, failed: [{step|segment, fixedBy}], steps,
  evidence}` do OpenVikingu pod klíčem role karty (`agentRole` na ploše), cesta
  `viking://user/<role>/peers/<projekt>/resources/cards/<karta>/zkusenost-<zdroj>-<otisk>.md`, štítek
  `kind=guard-experience`. Kroky a segmenty jsou `agent-reported`, nic neověřoval model. Když je paměť vypnutá,
  OpenViking neběží nebo karta nemá roli, záznam čeká ve frontě a nic neblokuje. Při vybavování (recall) ber záznam
  jako historii: co dřív spadlo a čím se to opravilo; aktuální stav čti z agent-state.
- `trend` (900 s) vzorkuje osm čísel projektu: `holes`, `holes.agent`, `journeys.verified`, `journeys.total`,
  `cards.done`, `cards.building`, `work.stalled`, `proposals.waiting`; retence 90 dní.

| Rozhraní | Tvar | Poznámka |
|---|---|---|
| `GET /api/strazci/trend?project=&metric=&days=` | `{metrics: [...], days, series: {metric: [{at, value}]}}` | `days` 1–90 (výchozí 14), `metric` jen ze známých osmi (jinak 422); vzestupně podle času; číslo bez vzorku v `series` chybí |

```bash
curl -s "$OPORA/api/strazci/trend?project=P&metric=holes.agent&days=30"
```

Trend je pro člověka (panel Trend ve Velínu) a pro závěrečnou zprávu („díry klesly z 12 na 7“); práci dál vybírej
z `mapGaps` a `actions[]`, ne z trendu.

# Studio: co stojí a jak teče data

Stav: kontrakt, rozhodnutí uživatele 2026-10-27. Kód ho provádí, nemění. Nahrazuje Archify (automatickou mapu
z kódu přes model); Graphify zůstává. Vzhled a ovládání podle TechViz Studia, základ je vlastní prototyp
`P:\0. OSVC\8. Code\07. Aplikace\04.Architektura-projektu\prototype` (kód, změřený design a rozbory v `analysis/`).
Stažené originální soubory TechViz (`vendor/`) se nekopírují.

Tento kontrakt mění `docs/zive-zobrazeni-a-knihovna.md` §1 („žádná simulace zátěže“): simulace je povolená,
ale jen ve vrstvě **MODEL**, která je vždy viditelně odlišená od skutečného stavu a nikdy se za něj nevydává.

## 1. Kde a co

Záložka **Studio** v hlavní liště na místě Archify (`Architektura projektu · Studio · Graphify-out`). Plátno
v designu TechViz (tmavé, mřížka teček, karty s ikonou a porty, Bézierovy vazby, minimapa, zoom 0,1–3,
fit, drobečková navigace). Dvě vrstvy nad stejnou mapou, přepínač nahoře:

| Vrstva | Zdroj | Pohyb | Zápis |
|---|---|---|---|
| **Skutečnost** (výchozí) | architektura OPORY (`/api/view` graf), stav práce karet, poslední ověření cest (`lastRun`) | jen co skutečně běží nebo právě skončilo | nic; jen čte |
| **MODEL** | technický model domény (§4), simulace (§5) | částice podle vypočteného toku | jen vlastní model, nikdy `/api/graph` |

Ve vrstvě MODEL má plátno trvalý štítek „MODEL – výpočet, ne měření“ a jiný tón pozadí.

## 2. Fraktální zanoření (Skutečnost)

Úrovně: **projekt → doména → stránka → sekce → komponenta**. Každá úroveň je jedno plátno s dětmi aktuálního
uzlu jako kartami; dvojklik nebo Enter na kartě sestoupí o úroveň, drobečky a Backspace vystoupí. Karta nese
souhrn toho, co je pod ní (počet dětí, kolik stojí, kolik se staví, díry mapy), takže z každé výšky je vidět, co
stojí. Sekce je úroveň, jen když stránka má `site.sections`; komponenty bez `card.section` jsou na úrovni
stránky ve skupině „bez sekce“. Uzel se do úrovně přiřazuje přes `parentId` a `nearest_page` / `card.section`
(stejně jako `node_architecture`).

Stav karty (barva rámu a štítek), odvozený, nikdy zadaný:
- **plán** – karta existuje, nikdo na ní nepracuje, není hotová;
- **staví se** – aktivní nárok práce (lease / `card_work_activity`), trvalý jemný pohyb rámu;
- **hotovo** – `done.confirmed`;
- **ověřeno** – hotovo a všechny cesty, na kterých karta leží, mají `lastRun` passed a ne stale;
- **díra** – nález kontroly mapy míří na kartu (odznak s počtem).
Rodič agreguje děti (např. „4/7 stojí, 1 se staví“).

Vazby: hrany grafu mezi uzly téže úrovně; hrany vedoucí hlouběji se na vyšší úrovni sečtou do jedné vazby mezi
předky (štítek s počtem a převládajícím `carries`). Barva a čára podle `carries` (`docs/zive-zobrazeni-a-knihovna.md`
§2). Pohyb ve Skutečnosti:
- částice po vazbě jen tam, kde je zdroj nebo cíl „staví se“, nebo po přechodech cesty, jejíž `lastRun` právě
  přibyl (jednorázový průchod po trase segmentu, pak klid);
- zastavená červená tečka s křížkem na vazbě segmentu `firstFailure` neprošlé cesty;
- `prefers-reduced-motion`: bez pohybu, stav nese barva a text.

## 3. Ovládání (z prototypu)

Kolečko = zoom kolem kurzoru, tažení pozadí = posun, fit, ± , minimapa vpravo dole, panel detailu vpravo
(stejný obsah jako Detail prvku, tytéž dílky z `element-detail/`: kontext agenta, zadání, vazby, práce; ve
Skutečnosti jen čtení a odkaz „Otevřít v Editoru stránky“). Klávesy: šipky posun výběru, Enter sestup, Backspace výstup, Escape zrušení výběru.

## 4. Technický model (MODEL)

Vlastní verzovaná definice na doménu, oddělená od grafu práce agentů:
`{schema: "opora.studio-model/1", domainId, revision, nodes[], edges[]}`; uzel `{id, type (katalog), name,
position, config, binding?: {nodeId}}`, hrana `{id, from: {nodeId, portId}, to: {nodeId, portId}, type, enabled}`.
Katalog typů, porty (12 datových typů), pravidla vazeb a geometrie karet z prototypu (`catalog`, `cloud-catalog`,
`technology`, `connection-policy`, `observed-*`, `routing`). `binding.nodeId` volitelně váže technickou kartu ke
kartě OPORY (pak se v MODEL ukazuje i její skutečný stav). Ukládá se v SQLite projektu (tabulka `studio_models`,
optimistická revize, konflikt 409), API `GET/PUT /api/studio/model?project=&domain=`. Nový model domény je
prázdný; scénáře z prototypu se otevírají jen jako nová pojmenovaná modelová doména, nikdy nepřepíšou existující.

### 4a. Cíl z MODELu pro agenta (dodatek 2026-10-28, rozhodnutí uživatele)

MODEL popisuje, **kam se aplikace musí dostat** (co musí zvládnout). Uzel MODELu s `binding.nodeId` dodá kartě
OPORY do `node-brief.architecture.model` zadané cíle, ne výsledky simulace:

```json
"model": {"source": "MODEL – cíl, ne měření", "domain": "web", "revision": 4,
          "type": "service", "name": "Service",
          "targets": {"capacity": 2500, "concurrency": 20, "replicas": 2},
          "mustSurvive": ["crash", "slow"], "links": [{"to": "PostgreSQL", "type": "sql-query"}]}
```

- `targets` jen parametry `config.model`, které člověk **zadal** (ne výchozí hodnoty); `mustSurvive` druhy
  plánovaných incidentů v `modelDefinition.incidents`, které uzel zasahují; `links` vazby uzlu v modelu (název
  protějšku a typ hrany), nejvýš 5. Bez vazby (`binding`) klíč chybí; víc modelových uzlů na jednu kartu → první
  podle id uzlu. Hledá se v modelu domény karty (`studio_models`, doména = aplikace karty) a nikdy v doménách
  scénářů (`scenario:*`).
- Mimo `specification` (nemění `contextVersion`); ořez §4 `docs/architektura-pro-agenty.md` ho bere jako stupeň 0b
  hned po `holes` (nejdřív `links`, pak celý klíč). Čísla ze simulace (rps, využití, latence) se nikdy nepíšou.
- Karta mimo stránku (služba, API, databáze – nejčastější vazba modelu) dostane `architecture` jen s klíčem
  `model`. `tech` se nepíše (katalog typů žije ve frontendu); `links` mají `{to, type}` pro odchozí a `{from, type}`
  pro příchozí zapnuté hrany; `mustSurvive` bez `restore`.
- Ve Skutečnosti Studia nese karta s navázaným uzlem MODELu odznak „cíl z MODELu“.

Převod `carries` → typ portu pro předvyplnění modelu z architektury (jen návrh, člověk potvrdí):
`navigation → http-request`, `data → data`, `command → record-command`, `event → event`.

## 5. Simulace (MODEL)

Engine prototypu `flow-model/1` (`simulation`, kernely `*-model`, `cloud-profiles`, `deployment`): tick = jedna
modelová sekunda, deterministický, bez náhody. Lišta RUN: Start/Pause/Step, rychlost 0,25–5×, incidenty
(surge, slow, crash, restore), telemetrie uzlu a hrany. Časování a částice podle prototypu (`PresentationClock`,
perioda částice `clamp(1400 + latency·12, 800, 6000)` ms, max 5 částic na druh na hranu, Pause zmrazí plátno,
Slow pulz 1,6 s). Simulace běží v prohlížeči, nic neukládá kromě definice incidentů v modelu. Výpočet je
„model“, ne měření projektu; čísla se nikdy nepíší do karet OPORY.

## 6. Etapy

| PR | Obsah |
|---|---|
| S1 | odstranění Archify (backend, frontend, docs, `CLAUDE.md`, skill) |
| S2 | záložka Studio: plátno v designu TechViz, fraktální zanoření, stavy karet, souhrnné vazby, minimapa, detail; pohled Studio z mapy domény (etapa 9) se přesune sem |
| S3 | pohyb Skutečnosti (částice, `PresentationClock`, selhání cesty) |
| S4 | MODEL: typy, katalog, pravidla vazeb, geometrie (TS 1:1 z prototypu) + úložiště a API |
| S5 | MODEL: kernely simulace a engine (TS, testy převedené z prototypu) |
| S6 | MODEL: paleta, editace plátna, inspektor, RUN lišta, telemetrie, scénáře |

Každá etapa je samostatný PR z čerstvého `origin/main`. Bundle MODEL části se načítá líně (`import()`).

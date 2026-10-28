# Brána cesty zákazníka (dodatek kontraktu, etapa 8)

Stav: dodatek k `docs/architektura-pro-agenty.md` §6, 2026-10-27. Navazuje na signál přechodu `via`
(`docs/cesta-zakaznika-a-brief.md` §3.2). Kód ho provádí, nemění.

## 1. Proč

Cesta zákazníka je zadání i test: každý přechod `předchozí krok → krok` říká, co má zákazník na stránce udělat
(`via`) a kam se má dostat (`site.path` stránky kroku). Opora testy sama nespouští a nástroj nepředepisuje.
Odvodí z mapy **plán přehrání**, výbava harnessu projektu (u webu typicky Playwright) ho přehraje a odevzdá
**doklad**. Poslední doklad cesty je její `lastRun`. Karta, jejíž komponenta leží na cestě, se neuzavře, dokud
`lastRun` té cesty neprošel a není zastaralý (§5).

## 2. Plán přehrání

`GET /api/project-architecture/journey-plan?project=<id>&journey=<journeyId>` (jen čtení, bez modelu). Čistá
funkce `journey_plan(graph, journey_id)` v `backend/project/architecture/journey_plan.py` nad stejným grafem
jako `derive_journeys`. Cesta je identifikovaná dvojicí `applicationId` + `journeyId`; když stejné `journeyId`
mají dvě aplikace, endpoint vyžaduje parametr `application` (jinak 409).

```json
{
  "schema": "opora.journey-plan/1",
  "applicationId": "web", "journeyId": "kampan", "name": "Kampaň Pěstování",
  "baseUrl": "http://localhost:3000",
  "digest": "sha256:…",
  "segments": [
    {"from": "s1", "to": "s2", "open": "/", "scope": "[data-opora-section=\"form\"]",
     "do": "submit", "text": "Chci video zdarma", "expectPath": "/novinky"}
  ]
}
```

- `baseUrl`: `environments[0].host` aplikace; bez schématu se doplní `http://` pro `localhost` / `127.0.0.1`,
  jinak `https://`. Aplikace bez prostředí plán dostane bez `baseUrl` (runner ho pak musí dodat). Runner ho smí přepsat (`--base-url`); `digest` na něm nezávisí.
- Segmenty v pořadí `derive_journeys` (každý krok kromě prvního navazuje na `after`, jinak na předchozí).
- `open`: `site.path` stránky kroku `from`; u kroku `"nav"` je `"/"`.
- `scope`: CSS selektor, ve kterém se hledá prvek. `via.section` → `[data-opora-section="<sectionId>"]` (má
  přednost i u menu); jinak krok `from` je `"nav"` → `nav`; jinak `body`. Segment, který mapa vazbami
  nerealizuje, v plánu zůstává (cestu nerozbíjí).
- `do`: `via.do` cílového kroku (`click` / `submit`); bez `via` je `click`.
- `text`: `via.text`, když je. Bez něj runner hledá v `scope` libovolný odkaz nebo tlačítko, po jehož použití
  URL odpovídá `expectPath` (pro `click` stačí odkaz, jehož `href` míří na `expectPath`).
- `expectPath`: `site.path` stránky kroku `to`. Shoda = pathname URL po přechodu, bez koncového `/`
  (kromě kořene), bez query a hash.
- Cesta `broken` (chybí stránka kroku) plán nemá: endpoint vrací 409 s důvodem z `derive_journeys`.
- `digest`: sha256 kompaktního JSON (`separators=(",", ":")`, `sort_keys=True`, UTF-8) objektu
  `{applicationId, journeyId, segments}`. Změna cesty, `via`, sekce nebo cesty stránky změní digest.

**Konvence pro stavitele webu:** element sekce stránky nese `data-opora-section="<id sekce>"`. Agent ji dostane
v briefu přes `page.section.id`; tento dodatek ji činí závaznou pro komponenty se `card.section`.

Formulář (`do: submit`): data dodá výbava harnessu (`fixtures` runneru, klíč `<journeyId>/<to>`), ne mapa.
Bez dat runner segment označí jako neúspěšný s důvodem „chybí data formuláře“.

## 3. Doklad (běh cesty)

`POST /api/project-architecture/journey-runs?project=<id>` odevzdá doklad (agent nebo člověk, bez modelu):

```json
{
  "schema": "opora.journey-run/1",
  "applicationId": "web", "journeyId": "kampan", "planDigest": "sha256:…",
  "command": "uv run python tools/journey_run.py --project … --journey kampan",
  "at": "2026-10-27T21:40:00Z",
  "segments": [{"from": "s1", "to": "s2", "ok": true},
               {"from": "s2", "to": "s3", "ok": false, "reason": "URL /novinky, čekáno /pribeh"}],
  "logUrl": "…"
}
```

- Validace: `schema`, existující cesta, `planDigest` tvaru `sha256:<64 hex>`, `command` 1–500 znaků, `at` ISO
  8601, `segments` 1–30 s `from`/`to` z plánu, `ok` bool, `reason` ≤ 300 znaků; `logUrl` nepovinné ≤ 500.
  Tělo ≤ 64 KiB. Chyba tvaru = 422 (i neznámý klíč, poslané `passed`, přechod dvakrát nebo přechod, který
  aktuální plán nemá); neznámá cesta nebo projekt = 404, rozbitá nebo nejednoznačná cesta = 409. `applicationId`
  je povinné. `at` bez časové zóny se bere jako UTC. Odpověď je uložený záznam (200) s `recordedAt`.
- `passed` se **odvodí**: všechny segmenty plánu jsou v dokladu a všechny `ok`. Nepíše se.
- Doklad je neměnný záznam (append-only) v SQLite projektu (tabulka `journey_runs`), s
  `verification: "agent-reported; not independently verified"`, stejně jako výsledky kroků karty.

## 3a. Cesta právě běží (krátkodobý stav)

Runner během přehrání hlásí, kde právě je, aby Studio (Skutečnost) a Editor stránky ukázaly pohyb na aktuálním
přechodu. Je to jen signál pro obrazovku: stav žije **jen v paměti procesu** serveru, žádná SQLite ani změna
schématu; doklad běhu (§3) zůstává neměnný a odevzdává se jako dosud.

- `POST /api/project-architecture/journey-runs/start`, tělo `{project, journeyId, applicationId?}` →
  `{runId, startedAt}` (200). Cesta se ověří stejně jako u plánu (§2): neznámý projekt nebo cesta 404, rozbitá
  nebo nejednoznačná cesta 409, chyba tvaru (i neznámý klíč) 422. Nový start téže cesty předchozí běh nahradí.
- `POST /api/project-architecture/journey-runs/{runId}/progress`, tělo `{segment: {from, to}, ok?}` → 204.
  Heartbeat: bez `ok` se přechod právě přehrává, s `ok` skončil. Neznámý nebo vypršelý `runId` 404, tvar 422.
- TTL 120 s od posledního heartbeatu (startu nebo `progress`); pak běh zmizí. Restart serveru stav smaže.
- `GET /api/project-architecture/journeys` přidá každé cestě `running: {runId, at, segment} | null`; `at` =
  poslední heartbeat (ISO 8601 UTC), `segment` = `{from, to, ok?}` posledního `progress`, před prvním `null`.
- Po zapsání dokladu (`POST /api/project-architecture/journey-runs`) se `running` té cesty smaže.
- Runner (§6) volá start před přehráním a `progress` před každým segmentem a po něm. Selhání těchto volání běh
  nezastaví (jen varování); `--dry-run` je neposílá. Vlastní nástroj projektu je posílat nemusí.
- Zobrazení: po vazbách aktuálního přechodu obíhají dvě tečky v barvě ověření; při `prefers-reduced-motion`
  místo nich štítek „cesta běží“. Dokud něco běží, UI čte `journeys` každé 3 s (jinak 15 s).

## 4. `lastRun`

Poslední doklad cesty podle `at` (při shodě později uložený):
`{at, passed, stale, command, failed: <počet neúspěšných segmentů>, firstFailure?: {from, to, reason?}}`.
`stale = planDigest dokladu != digest aktuálního plánu` (mapa se od běhu změnila). Cesta bez dokladu `lastRun`
nemá. Pořadí podle `at` převedeného na UTC; `failed` a `firstFailure` počítají jen segmenty s `ok: false`
(neúplný doklad má `passed: false` a může mít `failed: 0`). V briefu se `stale` počítá nad grafem pracovního
prostoru karty, v `journeys` a v kontrole mapy nad přijatým grafem.

Kde se objeví:
- `GET /api/project-architecture/journeys`: u každé cesty.
- `node-brief.architecture.journeys[]` (§4 kontraktu): `lastRun: {passed, stale}` (bez textů; ořez ho nebere,
  je to dvě pole).
- Kontrola mapy: `journey.unverified`, cesta bez `lastRun`, se zastaralým nebo neprošlým (zpráva jmenuje
  první neúspěšný přechod; jeden důvod v pořadí chybí → zastaralé → neprošel → nepokrývá všechny přechody).
  Práce pro agenty, ne chyba mapy. Hodnotí se jen tam, kde kontrola dostane doklady (`map-check`); výřez
  `gaps` v briefu ho nenese, karta ověření vidí v `journeys[].lastRun`.

## 5. Brána uzavření karty

Komponenta leží na cestě, když její nejbližší stránka (nebo ona sama, je-li stránkou) je stránkou některého
kroku cesty, která není `broken`. Taková karta se neuzavře (`done.confirmed`), dokud každá její cesta nemá
`lastRun` s `passed && !stale`. Požadavek `journeys` přibude do `REQUIREMENTS` v `backend/canvas/opora_card_done.py`
i do starší větve v `backend/editor/agent_memory/desktop_v3_state.py`; odmítnutí jmenuje cestu a důvod
(„cesta Kampaň Pěstování: chybí ověření“ / „zastaralé“ / „neprošel přechod s2 → s3“).

## 6. Runner

`tools/journey_run.py` (Python Playwright, volitelná závislost jako `tools/e2e`): stáhne plán, přehraje
segmenty v jednom prohlížeči (každý segment začíná `open`), průběh hlásí podle §3a, odevzdá doklad. Exit 0 jen při `passed`. Projekt
smí místo něj použít vlastní nástroj; Opora vyžaduje jen doklad.

## 7. Etapy dodatku

| PR | Obsah |
|---|---|
| 8a | `journey_plan`, `journey_runs` (úložiště + validace), oba endpointy, `lastRun` v `journeys` a v briefu, `journey.unverified` |
| 8b | brána uzavření (§5) a zobrazení `lastRun` v trychtýři a v úseku cesty Editoru stránky |
| 8c | `tools/journey_run.py` a konvence `data-opora-section` ve skillu |

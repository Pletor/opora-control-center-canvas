# Cesta zákazníka: konvence sekcí a ověření před uzavřením karty

Kdy mě číst: stavíš komponentu se `card.section`, nebo karta leží na cestě zákazníka
(`node-brief.architecture.journeys[]`) a chceš ji uzavřít. Kontrakt: `docs/brana-cesty.md` (plán §2, doklad §3,
`lastRun` §4, brána §5). Tady jen to, co dělá agent.

## Konvence `data-opora-section` (závazná)

Komponenta, jejíž karta má `card.section`, vykreslí svůj kořenový element s
`data-opora-section="<id sekce>"`. Id sekce je v briefu karty jako `page.section.id`; nevymýšlej ho.

```html
<section data-opora-section="form">…</section>
```

Plán přehrání v té sekci hledá prvek přechodu (`scope` = `[data-opora-section="form"]`). Bez atributu
segment selže („na / chybí [data-opora-section="form"]“) a karta na cestě se neuzavře. Text tlačítka nebo
odkazu ber ze signálu přechodu (`via.text` v briefu), odkaz bez textu musí mít `href` na cílovou stránku.

## Ověřit cestu před uzavřením karty

1. Z `node-brief.architecture.journeys[]` zjisti, na kterých cestách karta leží (`lastRun: {passed, stale}`).
2. Spusť aplikaci projektu (baseUrl plánu, nebo vlastní adresa přes `--base-url`).
3. Přehraj a odevzdej doklad:

```bash
uv run python tools/journey_run.py --server http://127.0.0.1:8740 --project <projectId> \
    --journey <journeyId> [--application <appId>] [--base-url http://localhost:3000] \
    [--fixtures fixtures.json] [--log journey.log]
```

- Nejdřív `--dry-run`: doklad jen vypíše, nic neodešle. Exit 0 = všechny přechody prošly, 1 = neprošlo nebo
  chyba serveru, 2 = chybí Playwright (`uv run --with playwright python tools/journey_run.py …`,
  prohlížeč `playwright install chromium`) nebo špatné zadání.
- Formulář (`do: submit`) potřebuje data: `fixtures.json` = `{"<journeyId>/<to>": {"E-mail": "a@b.cz",
  "input[name=souhlas]": "on"}}`; klíč je popisek pole, nebo CSS selektor (obsahuje `#`, `.`, `[` …).
  Bez dat segment selže „chybí data formuláře“. Data jsou výbava harnessu projektu, ne mapy.
- Neprošlý segment oprav v kódu a přehraj znovu; doklad je neměnný, platí poslední podle `at`.
- Změna mapy (cesta, `via`, sekce, cesta stránky) změní digest plánu a dosavadní doklad zastará: přehraj znovu.

Projekt smí místo runneru použít vlastní nástroj; Opora vyžaduje jen doklad `opora.journey-run/1`
(`POST /api/project-architecture/journey-runs`, hlavička `Origin` stejná jako server). Výsledky z dokladu
nevymýšlej: doklad jde jen ze skutečného běhu.

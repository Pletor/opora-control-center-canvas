# Archify — uložená mapa hlavního projektu

## Princip

Mapu vytváří automatika aplikace (`docs/mapy-projektu.md`, `map-refresh.md`):
po mergi do main, u projektu bez mapy a po volbě „Aktualizovat teď“. Jedna
session Claude Code Sonnet použije původní skill nad commitem main a Archify
vytvoří specifikaci a HTML. Prohlížeč mapy **pouze načte a zobrazí toto HTML**.
Nepřevádí ruční graf OPORY, nemá vlastní diagramový renderer a otevřením Mapy
nespouští model ani Node.

Původní balíček je celý v `vendor/archify/`; vstup skillu je
`vendor/archify/archify/SKILL.md`, CLI `vendor/archify/archify/bin/archify.mjs`.
Pro authoring načti původní skill a dodrž jeho validate/deliver/visual-check
kontrakt. Zdrojový kód knihovny se kvůli této integraci nemění.

## Uložení a otevření

Jediná sada leží v `archify-out/` **hlavního projektu** a přepisuje se na místě:

- `deliver-receipt.json` — úspěšné potvrzení příkazu deliver;
- `map.architecture.html` a `map.architecture.json`, se SHA-256 a velikostí
  shodnými s potvrzením;
- `visual-check-receipt.json` jako volitelný důkaz a `SPEC.md` s `Revize repa`.

Složka je pro git ignorovaná (případně přes lokální `.git/info/exclude`).

V Editoru otevři **Mapa**. HTML se načte přímo, bez přepínače na starý graf.
**Načíst uložený výstup** znovu načte a ověří doručenou sadu; není to generování.
**Aktualizovat teď** zařadí nový běh Sonnetu i při „Pouze ručně“.
**Stáhnout HTML/JSON** vrací přesné původní bajty. Ovládání diagramu je původní
Archify. Úplnost zobrazené architektury závisí na analýze autora, ne na počtu
ručně založených uzlů OPORY. Uloženou specifikaci svévolně neopravuj.

API: `GET /api/archify/artifact?project=<id>` čte `archify-out/`. Nový běh
zařazuje `POST /api/map-refresh/retry?project=<id>&tool=archify`; renderer ani
sample/example API v této integraci není.

Projekt se vybírá z registry OPORY, nikoli cestou z URL. U připojeného Git
worktree se hlavní adresář určí z Git metadata a ověří se společná identita
repozitáře. Mapa zůstává projektová, nikoli závislá na vybraném worktree.
U obyčejné připojené složky se čte její vlastní adresář.

## Důvěryhodnost

- Kontrola hashů prokazuje shodu souborů s potvrzením, nikoli pravdivost analýzy.
- Kontrola prohlížeče se přebírá pouze při shodě jejího HTML hash; UI ukazuje
  skutečný počet dodaných záznamů, nikoli autorův slovní odhad pokrytí.
- Pokud SPEC.md uvádí revizi a hlavní projekt má jiný HEAD, zobrazí se změna.
  Shodný HEAD sám neprokazuje nepřítomnost rozpracovaných změn: úplná aktuálnost
  zůstává neověřená.
- Přístup je omezen na danou složku. Symlinky, junctiony, chybné potvrzení a
  příliš velké soubory se odmítají. Absolutní cesty uvnitř receipt nejsou
  oprávnění ke čtení jiných adresářů.
- HTML běží v iframe `sandbox="allow-scripts allow-downloads"`, bez přístupu
  k DOM/storage rodiče a s CSP blokující síť. Stažené HTML není upraveno.
- Při chybě nového načtení se staré HTML nevydává za aktuální.

## Ověření

```bash
.venv/Scripts/python.exe -m pytest backend/api/project/test_archify_routes.py backend/project/workspace/test_workspace_sources.py -q
.venv/Scripts/python.exe -m ruff check backend/api/project/archify_routes.py
npm run build
```

E2E testy byly odstraněny při restrukturalizaci; ověření proveď ručně přes náhled (`tools/serve-preview.py`) nebo přes API.

UI test používá výslovnou fixture. Nasazení se ověřuje zvlášť přes skutečné
project ID, odpověď živého API, shodu bajtů a screenshot vloženého prohlížeče.

# Archify — uložená mapa hlavního projektu

## Princip

Agent ve VS Code nebo CLI použije původní skill nad skutečným kódem,
konfigurací a dokumentací projektu. Archify vytvoří specifikaci a HTML.
Control Center **pouze načte a zobrazí toto HTML**. Nepřevádí ruční graf OPORY,
nemá vlastní diagramový renderer a otevřením Mapy nespouští model ani Node.

Původní balíček je celý v `vendor/archify/`; vstup skillu je
`vendor/archify/archify/SKILL.md`, CLI `vendor/archify/archify/bin/archify.mjs`.
Pro authoring načti původní skill a dodrž jeho validate/deliver/visual-check
kontrakt. Zdrojový kód knihovny se kvůli této integraci nemění.

## Uložení a otevření

Výstupy patří do `docs/architecture/archify/` **hlavního projektu**:

- `deliver-receipt.json` — úspěšné potvrzení příkazu deliver;
- HTML a JSON uvedené v tomto potvrzení, se shodnými SHA-256 a velikostí;
- volitelně `visual-check-receipt.json` a `SPEC.md` s důkazy a omezeními.

V Editoru otevři **Mapa**. HTML se načte přímo, bez přepínače na starý graf.
**Načíst ze souboru** znovu načte a ověří doručenou sadu; není to generování.
**Stáhnout HTML/JSON** vrací přesné původní bajty. Ovládání diagramu je původní
Archify. Úplnost zobrazené architektury závisí na analýze autora, ne na počtu
ručně založených uzlů OPORY. Uloženou specifikaci svévolně neopravuj.

API: `GET /api/archify/artifact?project=<id>`. Žádné POST render API ani
sample/example renderer API není v této integraci dostupné.

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
  zůstává neověřená. Není implementováno automatické přegenerování agentem.
- Přístup je omezen na danou složku. Symlinky, junctiony, chybné potvrzení a
  příliš velké soubory se odmítají. Absolutní cesty uvnitř receipt nejsou
  oprávnění ke čtení jiných adresářů.
- HTML běží v iframe `sandbox="allow-scripts allow-downloads"`, bez přístupu
  k DOM/storage rodiče a s CSP blokující síť. Stažené HTML není upraveno.
- Při chybě nového načtení se staré HTML nevydává za aktuální.

## Ověření

```bash
.venv/Scripts/python.exe -m pytest tests/test_archify_routes.py tests/test_workspace_sources.py -q
.venv/Scripts/python.exe -m ruff check backend/api/project/archify_routes.py tests/test_archify_routes.py
npm run build
```

E2E testy byly odstraněny při restrukturalizaci; ověření proveď ručně přes náhled (`tools/serve-preview.py`) nebo přes API.

UI test používá výslovnou fixture. Nasazení se ověřuje zvlášť přes skutečné
project ID, odpověď živého API, shodu bajtů a screenshot vloženého prohlížeče.

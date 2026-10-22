# Plán vs. realita

Měří, kolik z plánu na plátně Opora Canvas je opravdu hotové. Skript je **jen pro čtení**: posílá výhradně HTTP GET na běžící Opora backend (výchozí `http://127.0.0.1:8740`), čte soubory (`graphify-out/graph.json`, existence cest) a volitelně (`--gh`) volá `gh pr view`. Nic nezapisuje do aplikace ani do databáze a nespouští žádný model.

## Co měří

Tři úrovně důkazu, počítané odděleně a nikdy nesčítané (vždy hotové jednotky / všechny jednotky, po kartě, oblasti i projektu):

- `tvrdí` – plán sám říká hotovo (krok done / blok met / u karty bez kroků a bloků `done.confirmed` nebo návrh agenta).
- `kód` – karta má `sourceRef` s původem `existing` a cesta existuje v checkoutu (bez checkoutu n/a).
- `potvrzeno` – člověk potvrdil kartu (`done.confirmed`).

Jednotka plánu: kroky karty; jinak listové bloky; jinak samotná karta. Nálezy: `ZBYVA` (včetně `dalsi_krok`), `SLEPA_ULICKA`, `NOVA_CESTA`, `SIROTEK`, `DOPLNIT`, `UBRAT`, `VYMENIT`, plus pokrytí graphify souborů.

## Spuštění

```
python tools/plan-vs-realita/mereni.py --project <id> --workspace <wid> [--checkout <cesta>] [--gh] --out vystup.json
```

Na stdout jde stručné Markdown shrnutí, celý výsledek je v JSON. Výstup ukládejte mimo repozitář.

## Testy

```
uv run pytest tools/plan-vs-realita -q
```

# Aktualizace projektových map

Pro asistenta v aplikaci jde jen o vědění: mapy `graphify-out/` a `archify-out/`
v kořeni projektu se obnovují bez tebe a spouštět je nesmíš ani nemůžeš.

- Automaticky: po mergi do main, a u projektu bez mapy při prvním běhu
  (volba „Po mergi do main“; globální přepínač je v Nastavení → Obecné).
- Ručně: v UI Mapa → „Aktualizovat teď“ (Graphify lokálně, Archify
  session Claude Code Sonnet). To dělá člověk.
- Mapa zobrazuje commit main, ne rozpracované změny. Zastará-li, řekni to a
  nabídni člověku „Aktualizovat teď“; sám ji negeneruj.
- Selhaný běh nechá poslední funkční sadu. Existenci sady poznáš podle
  `graphify-out/graph.json` a `archify-out/deliver-receipt.json`.
- Obě složky jsou mimo git (lokální `.git/info/exclude`).

Čtení map: `graphify.md`, `archify.md`. Kontrakt: `docs/mapy-projektu.md`.

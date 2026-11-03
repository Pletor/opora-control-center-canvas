# Aktualizace projektových map

Pro asistenta v aplikaci jde jen o vědění: mapa `graphify-out/`
v kořeni projektu se obnovuje bez tebe a spouštět je nesmíš ani nemůžeš.

- Automaticky: po mergi do main, a u projektu bez mapy při prvním běhu
  (volba „Po mergi do main“; globální přepínač je v Nastavení → Obecné).
- Ručně: v UI Mapa → „Aktualizovat teď“ (Graphify lokálně, bez modelu). To dělá člověk.
- Mapa zobrazuje commit main, ne rozpracované změny. Zastará-li, řekni to a
  nabídni člověku „Aktualizovat teď“; sám ji negeneruj.
- Selhaný běh nechá poslední funkční sadu. Existenci sady poznáš podle
  `graphify-out/graph.json`.
- Složka je mimo git (lokální `.git/info/exclude`).

Čtení map: `graphify.md`. Kontrakt: `docs/mapy-projektu.md`.

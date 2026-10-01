# Mapy projektu: stabilní soubory, automatická aktualizace

Každý připojený projekt má na pevných cestách jednu sadu map. Sada se přepisuje
na místě, když se změní `main`. Nevzniká žádná historie verzí, žádný ukazatel
na verzi ani archiv. Předchozí funkční sadu zachová git historie zdroje, nikoli
kopie souborů: když běh selže, nic se nepřepíše.

## Soubory (v kořeni hlavního pracovního stromu projektu)

| Nástroj | Složka | Soubory (nic jiného) |
|---|---|---|
| Graphify | `graphify-out/` | `graph.json`, `graph.html`, `GRAPH_REPORT.md`, `opora-receipt.json` |
| Archify | `archify-out/` | `map.architecture.html`, `map.architecture.json`, `deliver-receipt.json`, `visual-check-receipt.json`, `SPEC.md` |

- Pomocné soubory běhu (`cache/` Graphify, zámek `opora-build.lock`) smí v `graphify-out/` zůstat. Ostatní mezivýstupy vznikají jen v dočasné složce: validate receipt, evidence, screenshoty a HTML z visual-check.
- Zápis je atomický po souborech. Každý soubor se zapíše jako `<name>.tmp` a pak se provede `os.replace`. Sada se publikuje až po úspěchu celého běhu daného nástroje.
- Obě složky jsou pro git ignorované. Když projekt je git repo a složku neignoruje, aplikace přidá řádek do `.git/info/exclude`. Ten soubor je lokální a nesledovaný, takže `main` zůstane čistý. `.gitignore` projektu se nemění.
- Agenti čtou mapy z týchž cest. Pro Graphify platí `context.knowledgeGraph` v `docs/karta-pro-agenty.md`.

## Automatika

- Je zapnutá bez ručního kroku. Globální přepínač je v aplikaci **Nastavení → Obecné** (app-global, nikdy per projekt). Na serveru ho mění `POST /api/map-refresh/configure {enabled}`.
- Worker každých 5 s kontroluje `refs/heads/main` každého projektu. Nová revize zařadí běh.
- Projekt bez stabilních souborů zařadí počáteční běh. Chybět může jedna ze sad `graphify-out/graph.json` nebo `archify-out/deliver-receipt.json`.
- Po mergi se aktualizuje Graphify (lokálně, bez modelu) i Archify. Archify je jedna relace Claude Code Sonnet, nejvýše 10 tahů a 600 s. Je to jediné místo, kde aplikace spouští model.
- V projektu lze automatiku vypnout pro každý nástroj zvlášť („Pouze ručně“). Tlačítko „Aktualizovat teď“ funguje i tehdy.
- Nejvýše jeden běh v celé instanci. Starý výsledek se nepublikuje, pokud se `main` mezitím změnil.
- Snapshot čte jen commit, nikdy rozepsaný worktree, a vynechává `graphify-out/` i `archify-out/`.

## Čtení

- `GET /api/graphify/artifact` čte `graphify-out/`. `GET /api/archify/artifact` čte `archify-out/`. Obě čtou jedinou sadu, bez výběru verze.
- Archify: HTML a JSON se musí shodovat s `deliver-receipt.json`. `visual-check-receipt.json` je volitelný důkaz. `SPEC.md` nese `Revize repa`.
- Ruční Graphify (`POST /api/graphify/generate`) zapisuje do stejných souborů stejným atomickým způsobem.

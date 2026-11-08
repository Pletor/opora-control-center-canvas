# Pravidla pro agenty (Codex, Claude Code, kancelář, Pletor)

Platí totéž co v `CLAUDE.md`; tento soubor čtou agenti, kteří `CLAUDE.md` nenačítají.

- **Každý vývoj běží přes OPORU.** Žádná změna kódu nevzniká mimo kuličku Linie.
  1. Úkol v OPOŘE: Velín → Linie, nebo `POST /api/pletor/linie/work`.
  2. Větev úkolu z rodiče podle jména (`feat/a-b` z `feat/a`), před první editací `uv run python tools/linie.py task`.
  3. Commity s trailerem `Opora-Mark` z výpisu `linie task`.
  4. Po testech `uv run python tools/linie.py report --check "npm test=green" --try "<místo v aplikaci>" --step "<krok>"`.
  5. Přijetí dělá jen člověk po zkoušce v náhledu (Vyzkoušet); začlení služba OPORY squashem.
- Zakázáno: přímé commity, `git merge` nebo `git push` na sdílené větve (`main`, `develop`, `feat/<kořen>`), práce bez kuličky,
  zápis přijetí za člověka.
- Co přesto vzniklo mimo OPORU, se převede na kuličku a projde přijetím; nestaví se na tom další práce.
- Kontrakty a struktura: `CLAUDE.md`, `docs/pravidla-struktury.md`, `docs/navrhy/2026-11-08-linie-zkouska.md`.

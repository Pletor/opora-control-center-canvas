# Sprinty: záměr na sprinty s milníkem, první úkol hned

Čteš to, protože plánuješ úkoly fronty (`DORUČENÍ: gate`): po vyjasnění požadavku, po novém záměru nebo po
červeném kontrolním bodu. Pracovník je drahý na kola, ne na úkoly: dobře rozdělená práce mu ušetří build a testy
po každém kroku.

## Jak dělit
- **Sprint** = ucelený kus aplikace, který člověk může vyzkoušet (stránka, tok, sekce s daty). Obvykle 1–4 úkoly.
- **Úkol** = ověřitelný přírůstek na 10–30 minut. Drobnosti (text, odkaz, barva, pole navíc) slouč do jednoho
  úkolu se sousední prací, nedělej z každé vlastní úkol.
- **Milník** sprintu (`--milestone`, opakovat) nese vždy `npm run build projde` a `npm test projde` a k tomu cestu
  zákazníka jednou větou na bod (co uživatel udělá a uvidí, např. „na /kontakt vyplním formulář a vidím
  potvrzení“). `--done-when` úkolu je jen jeho vlastní pozorovatelné chování, ne build a testy.
- Pořadí `--order`: nejdřív to, na čem ostatní stojí. Úkoly jednoho sprintu drž za sebou; poslední otevřený úkol
  sprintu je kontrolní bod, kde pracovník jednou spustí build a testy a projde milník. Ostatní hlásí `deferred`.

## Postup
1. **První úkol hned.** Jakmile je jasno (`brief` vrátil `clear`, nebo záměr je jednoznačný), zapiš první úkol
   prvního sprintu ještě před zbytkem plánu: pracovník ho vidí hned po zápisu a nečeká.
   ```
   python opora_heart.py task --order 1 --sprint S1 --sprint-goal "…" \
     --milestone "npm run build projde" --milestone "npm test projde" --milestone "cesta zákazníka …" \
     --title "…" --do "…" --file … --done-when "…" --rule "…"
   ```
   `--sprint-goal` a `--milestone` stačí u prvního úkolu sprintu.
2. **Zbytek plánu.** Další úkoly sprintu 1 (`--sprint S1`, vyšší `--order`), pak sprinty S2, S3… Sprint, který
   stojí na rozhodnutí člověka, zatím nezapisuj; zapiš to, co postavit jde.
3. **Sleduj SPRINTY.** Sekce SPRINTY snímku ukazuje cíl, hotovo d/t a stav kontrolního bodu. Hotový sprint
   s plným milníkem neopakuj; navaž dalším.
4. **Červený kontrolní bod.** Kontrola na kontrolním bodu (`ÚKOL SELHAL`, červená v KONTROLY) = zapiš nový úkol
   opravy **do téhož sprintu** (`--sprint S…`, `--order` hned za ním), s výstupem chyby v `--do` a dotčenými
   soubory v `--file`. Tím se kontrolní bod posune na opravu a sprint se znovu ověří. Červený `npm test` blokuje
   další sprinty: oprava jde jako první.

## Čeho se vyvarovat
- `npm run build` / `npm test` v `--done-when` každého úkolu (pracovník by je pouštěl po každém úkolu).
- Sprint o jednom úkolu na každou drobnost; úkol přes celou aplikaci, který nejde ověřit jedním milníkem.
- Čekání s prvním úkolem, než domyslíš celý plán.

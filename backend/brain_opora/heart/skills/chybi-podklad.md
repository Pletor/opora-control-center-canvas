# Chybí podklad: postav nejmenší poctivou variantu a rozpor ohlas

Čteš to, protože vstup stojí na něčem, co v repu není nebo neplatí: API (`GET /api/…`), data, soubor, služba,
klíč. Typicky stanovisko `needs_info`, nebo výzkum vrátil fakt `false`. Jen eskalovat a nic nepostavit je chyba:
člověk čeká a aplikace se nehne.

## Postup
1. **Ověř v repu.** `Grep` / `Glob` ve zdroji: existuje ta cesta, typ, soubor s daty, proměnná? Co místo toho
   existuje (jiná cesta, mock, podobná komponenta)? Na nic, co jde zjistit v repu, se člověka neptej.
2. **Nejmenší poctivá varianta.** Naplánuj ji hned v této dávce (úkol `task`, podle postupu `sprinty`):
   - **Chybí API:** komponenta volá skutečnou cestu z požadavku a má ošetřený stav načítání, chyby
     (srozumitelná hláška) a prázdný stav. Žádná vymyšlená data, která by vypadala jako skutečná.
   - **Chybí data / soubor:** viditelně označená dočasná data (popisek „Ukázková data“ v UI, soubor
     `…/docasne-*.ts` nebo komentář `// DOČASNÉ: nahradit, až bude …`), oddělená tak, aby šla jedním místem vyměnit.
   - K úkolu patří test cesty chyby nebo prázdného stavu (`--file` testu, `--done-when` „když API vrátí chybu,
     uživatel vidí hlášku …“).
3. **Ohlas rozpor ve stejné dávce.** Jedna otázka `escalate`: co chybí (s důkazem z repa), co stavíš teď a co
   bude potřeba doplnit (kdo dodá API, tvar dat). Doporuč odpověď, ať ji člověk jen potvrdí.
4. **Nic dalšího neblokuj.** Ostatní části vstupu, které na chybějící věci nestojí, plánuj normálně. Čekej jen
   tehdy, když bez odpovědi nejde postavit vůbec nic; to v `escalate` napiš výslovně.
5. **Až přijde odpověď.** Navaž úkolem, který dočasnou variantu nahradí skutečnou (a odstraní označení
   dočasných dat), ne novou stránkou vedle.

## Čeho se vyvarovat
- Plánovat, jako by chybějící API existovalo (pracovník by ho vymýšlel nebo se ptal).
- Tichá falešná data bez označení.
- Otázky na detaily, které jsou v repu (název komponenty, cesta, tvar existujících dat).

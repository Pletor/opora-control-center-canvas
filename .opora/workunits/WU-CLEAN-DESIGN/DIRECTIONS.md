# Tři kompoziční směry (lokální claude-design workflow, ne hosted Claude Design)

Surface: **COMMAND / INSPECT**. Uživatel řídí jeden objekt (vrstva, uzel, blok, běh) a vidí k němu jeden kontext. Explore (Mapa) je sekundární. Žádný Decide/Learn prvek (hero, karty, metriky).

## 1. Konzervativní — „stejný shell, méně šumu“
Zachovat čtyřsloupcový shell (rail · strom · plátno · detail), jen sjednotit typografii, zmenšit hlavičku a zredukovat idle inspektor. Nízké riziko, ale zůstává trvalý levý strom, dvě lišty nad obsahem a formulářová stěna v detailu. Neřeší „velkou klikačku“ ani obsah-first.

## 2. Silný fit — „jedna lišta, rail, obsah, kontext“ (realizováno)
- Jedna horní lišta: projekt, main/worktree, revize, menu Nastavení (plocha, projekt, obnovit, synchronizace, odebrání).
- Úzký rail módů vlevo: Struktura · Text · Kreslení · Mapa · Běhy.
- Obsah dominuje: plátno / dokument / kresba / mapa / běhy. Nad obsahem jen drobeček a „+ Sektor / + Uzel“.
- Jeden inspektor vpravo řízený kontextem: bez výběru = scope (zdroj, worktree, operace, nástroje módu); uzel = karty Obsah · Zadání · Práce; vazba = smazání; Text mód = Souvislosti · Deník vrstvy.
- Levý strom vrstev zrušen: plátno a drobeček jsou navigace; méně trvale viditelných ovladačů, žádná funkce bez náhrady.

## 3. Divergentní — „dokument s plovoucím inspektorem“
Logseq-like: obsah přes celou šířku, inspektor jako plovoucí panel u vybrané karty, příkazová paleta Ctrl+K pro všechno. Nejčistší, ale mění interakční model plátna (React Flow overlay, focus management) a ohrožuje existující e2e i mobil. Vhodné jako další iterace po hosted Claude Design přihlášení, ne pro tento řez.

Volba: **2**. Důvody: obsah-first bez ztráty funkcí, změny selektorů jen v navigaci (menu, karty inspektoru), draft-safety kód zůstává netknutý.

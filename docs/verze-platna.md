# Uložení a historie pracovního prostoru

**Uložit vše** v horní liště za Asistentem nejprve dokončí rozpracované úpravy aktuálního projektu a pracovního prostoru a potom vytvoří uloženou verzi. Stejnou akci provádí Ctrl+S / ⌘S. Zpět a Vpřed v liště Editoru zůstávají samostatnou historií úprav grafu.

Část změn se ukládá průběžně. Indikátor zahrnuje místní koncepty i obsah serveru, který ještě neodpovídá žádné uložené verzi. Neúspěšný zápis nebo konflikt nesmí skončit oznámením, že je vše uložené. Formulář vytvoření karty či domény a změny vyžadující vlastní potvrzení je nutné nejprve výslovně dokončit nebo zavřít; centrální uložení samo nové objekty nevytváří.

## Rozsah verze

Nová verze zachycuje celý pracovní prostor, nikoli pouze otevřenou vrstvu:

- graf a stav Desktop v3;
- zadání, texty a deníky uzlů;
- uložené kresby a jejich místní obrazové soubory;
- editovatelný prostor agenta a dokumentaci pracovního prostoru;
- dostupné místní přílohy spolu s údajem o případných chybějících souborech.

**Cíl a nastavení projektu jsou společné; obnova pracovního prostoru je nemění.** Centrální uložení může dokončit rozepsaný cíl přes stávající rozhraní dokumentace. Verze nese tehdejší cíl jen jako kontext. Neobnovuje zdrojový kód, Git historii, obsah externích odkazů ani neměnné důkazy agentů. Chybějící přílohy se nesmějí vydávat za zálohované soubory.

Starší verze mají označení `legacy-partial`: obsahují pouze graf a Desktop v3. Ostatní obsah při jejich obnově zůstává současný. Historie tento omezený rozsah zobrazuje.

## Obnova a souběžná práce

Historie umožňuje vybrat verzi a potvrdit obnovení. Před obnovou je nutné vyřešit místní koncepty. Odlišný současný stav serveru se uchová jako záchranná verze „před obnovením“. Obnova hlídá graf, revize všech zahrnutých úložišť, přílohy a kontext projektového cíle; cizí změna od načtení potvrzovaného stavu znamená konflikt, nikoli tiché přepsání.

Validace grafu, stavů a uzavřených karet proběhne před zápisem. Historie neobchází pravidla uzavřených karet a přechodů pracovních fází; neplatnou obnovu odmítne bez dílčí změny. Databázové zápisy tvoří jednu transakci a při výjimce se vracejí také změněné soubory. Nejde o záruku společné databázové a souborové transakce při násilném ukončení procesu nebo výpadku disku.

Po úspěšné obnově se načte graf, Desktop i obsah editorů znovu a vyprázdní se místní Zpět/Vpřed. Výběr odstraněného uzlu nebo stránky se vrací do platného kontextu. Main pouze pro čtení nelze ukládat ani obnovovat.

## API a vlastnictví

Po přijetí prvního návrhu grafu OporaHubu je graf prostoru autoritativně v SQLite.
Obnova jej zapisuje ve stejné databázové transakci; původní soubor grafu nepřepisuje.
Obnovuje pracovní stav, nikoli přijatou revizi OporaHubu, zařazení do řízeného
vykonávání nebo historii výsledků. Neshoda obnoveného pracovního grafu s přijatým
manifestem blokuje nové převzetí práce. Omezení společné obnovy ostatních souborů
a databáze při pádu procesu zůstává.

Existující modul `backend/editor/canvas_versions/` vlastní verze v projektové databázi. Nové sloupce `snapshot` a `content_digest` se přidávají kompatibilně, staré řádky zůstávají čitelné.

- `GET /api/canvas-versions?project&workspace` vrací `versions`, `dirty` a `currentToken` (s `ETag`; beze změny `If-None-Match` → 304).
- `GET /api/canvas-versions/head?project&workspace` vrací jen `currentToken` a `dirty`: levná hlava pro polling UI
  (jednou za 30 s); celý výpis si klient stáhne, až se hlava změní. Obojí se drží v cache podle tokenu dat projektu.
- `GET /api/canvas-versions?project&workspace&versionId` vrací neměnný obsah konkrétní verze a ověřenou integritu.
- `POST /api/canvas-versions` přijímá `project`, `workspace`, `digest`, `author`, `expectedToken`. Uložení bez tokenu zůstává pouze kompatibilní neobnovovací operací s označením `legacy-unbound`.
- `POST /api/canvas-versions/restore` navíc přijímá `versionId`; `expectedToken` je povinný. Token se vztahuje k potvrzovanému současnému stavu, nikoli k historické cílové verzi.

Frontend `save-versions/` vlastní historii a její stav. Sdílený `save-coordinator` pouze registruje existující editory a čekající zápisy; nepřebírá koncepty do druhého obsahového úložiště. Každý editor nadále ukládá vlastním rozhraním s vlastní kontrolou revize. Místní indikátor se odvozuje z registru bez načítání celého serverového snapshotu na každé stisknutí klávesy.
### Původce a změněné karty

Nové verze ukládají původce `human`/`agent` podle `X-Opora-Actor` spolu s počtem změněných
karet oproti předchozí uložené verzi. Porovnávají se karty a sektory, jejich pracovní stav,
zadání, texty, deníky, kresby, podklady, vazby, zprávy a účinná pravidla. První verze počítá
všechny karty. Údaje jsou v metadatech snímku chráněných jeho integritou a nemění dirty token.
Starší verze mají neznámého původce; při porovnání s neúplnou verzí je počet nedostupný.
Historie tyto údaje ukazuje ikonou původce a textem „Změněné karty“.

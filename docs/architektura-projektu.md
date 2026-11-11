# Architektura projektu – kontrakt obrazovek

Zdroj: sektor „Projekty a zdroje“ (`a74ccd78-5c02-4004-bdb1-fa3d6478946a`) v projektu OPORA Control Center
a obrázky na jeho kartách (Vygenerování domény → Architektura projektu → Editor stránek → Záložka Editor);
plátno 2 podle `docs/navrhy/2026-11-10-platno-2.md` (verze 2: layout z boxů a logika, `image.png`, `image1-1.png`, `image17.png`; verze 3: Detail boxu, skica, inspirace, stavy boxu, sken webu).
Kód (`frontend/project/architecture-editor/`) tento kontrakt provádí, nemění ho.

## Proces (pořadí je závazné)

1. **Mapy architektury** – výběr prostředí a domény. Řádek *Produkce* (štítek „Produkce“, „Aktivní prostředí“)
   a řádek *Vývoj* (štítek „Vývoj“, „Oddělený prostor pro změny a ověření“). Každá doména je karta:
   ikona druhu (web / aplikace / administrace), host, „druh · účel“, čip `ID` (plné ID v bublině, klik zkopíruje), odkaz **Otevřít mapu domény**.
   Slovo „projekt“ patří jen celému projektu; jedna doména je vždy „doména“.
   Doména = sektor `site.kind = "application"` s jedním prostředím; vše má vlastní ID, domény ani funkce se nemíchají.
   **Otevřít mapu domény** vede rovnou na plátno 2 první stránky domény. Doména s více hosty (starší sdílená struktura)
   se neotevře a nabídne oddělení hostu na přehledu.
2. **Plátno 2 – stránka jako layout a logika** (jedna doména, jedna stránka, kontrakt `docs/navrhy/2026-11-10-platno-2.md`).
   Nejryzejší forma stránky: nezakládají se tu oblasti, uzly ani sektory. Tři sloupce:
   - **Struktura a paleta** (vlevo). Struktura: jen otevřená doména, strom stránek a podstránek; jediné místo, kde se
     mění struktura: **+ Stránka** a **+ Podstránka** otevřou vyskakovací okno jen s Názvem, Adresou (předvyplněnou z názvu)
     a Účelem jednou větou (`site.goal`); ✎ otevře plný formulář stránky (cesta, **Cíl stránky** `goal` 1–200, **Působení**
     `feel` 1–120, **Popisek v menu** `navLabel` 1–40, sekce); dále pořadí ↑ ↓ a odstranění. Prázdné pole se neukládá.
     Pod Strukturou paleta podle vrstvy: ve vrstvě Layout **boxy** (Hlavička, Navigace, Sekce, Článek, Boční panel, Patička,
     Výzva, Formulář, Galerie, Obsah) a **šablony** (Klasický web, Landing, Aplikace); ve vrstvě Logika **prvky logiky** podle
     otázky (Kdo: Uživatel; Kdo smí: Přístup; Co musí splnit: Podmínka, Omezení; Co se děje: Akce, Proces, Formulář;
     S čím: Data, Úložiště; Napojení: Služba, Vstup, Výstup, Událost, API kontrakt).
   - **Stránka** (uprostřed) – hlavička s názvem stránky, **Skenovat web**, **Zkontrolovat plán** (díry kontroly mapy této stránky) a stavem
     **Rozpracováno / Kompletní**; přepínač **1 Layout / 2 Logika**; drátový model stránky na 12sloupcové mřížce (čárkovaná vodítka).
     *Layout*: box = sekce stránky `site.sections[]` s `box {x, y, w, h}` a nepovinným `parent` (box v boxu, hloubka nejvýš 3);
     box se táhne z palety (klik = na konec), posouvá tahem, mění velikost úchytem vpravo dole, přejmenuje dvojklikem, odebere ✕
     a vnoří puštěním do jiného boxu; vše se přichytí k mřížce. Šablona nahradí layout (u neprázdného se zeptá). Sekce bez `box`
     se skládají pod sebe na celou šířku. Layout je struktura stránky (zámek struktury, zapisovatelný i na mainu).
     *Logika*: prvek = uzel `element.kind` pod stránkou, box nese `card.section` (bez něj = Celá stránka); prvek se táhne do boxu
     nebo na pruh Celá stránka, v boxu je štítek se symbolem, druhem, názvem a milníky Návrh → Realizace → Ověření; klik vybere,
     ✕ odebere (náhled a potvrzení odstranění), tah přesune do jiného boxu. Starší sektory a komponenty bez `element` se
     nekreslí („N starších karet jen v Editoru“).
     Pod stránkou **Další přípustný krok**: první neověřený prvek logiky, jehož vstupy `requires` jsou aspoň hotové, s **Otevřít v Editoru →**.
     Stránka s aspoň jedním prvkem logiky, kde jsou všechny ověřené, je kompletní a její logika jen pro čtení, dokud ji člověk neotevře k úpravám.
     *Stavy boxu* (`site.sections[].status`, chybí = Rozpracováno): **Rozpracováno** `draft`, **Návrh** `proposed` (od agenta nebo
     skenu, čárkovaný rám, Přijmout / Zahodit), **Schváleno** `approved`. Značky na boxu se jen odvozují: skica ✎, počet inspirací,
     počet prvků logiky s milníkem nejpomalejšího, **Ověřeno**, když jsou všechny prvky boxu ověřené.
     *Skenovat web*: okno s adresou a poznámkou → `POST /api/page-plan/scan`, dotaz `GET /api/page-plan/scan/{scanId}` každé 3 s
     (nejvýš 10 minut, Zrušit jen přestane čekat). Hotový návrh se ukáže v panelu vedle plátna (náhled layoutu jen ke čtení a seznam
     prvků logiky); **Převzít** nahradí layout boxy Návrh a vloží prvky logiky jedním plánem `/api/canvas-plan` (na mainu jen layout
     s větou proč), **Zahodit** návrh zahodí.
   - **Detail boxu** (vpravo, po kliku na box v kterékoli vrstvě) – název, role, záměr, stav (u Návrhu Přijmout / Zahodit),
     **Skica** (náhled a **Kreslit skicu**: velké okno s kreslením nad vrstvou `box/<pageId>/<sectionId>`, ukládá `/api/drawing`),
     **Inspirace** (0–6 obrázků přes `/api/drawing-file`: Ctrl+V, přetažení, výběr souboru, klik zvětší; odkaz na web a poznámka
     v `site.sections[].inspiration`) a seznam prvků logiky boxu (klik otevře Detail prvku). Na mainu jsou skica a inspirace jen
     ke čtení s větou proč (zámek obsahu); název, role, záměr a stav jsou struktura a jdou měnit i tam.
   - **Detail prvku** (vpravo) – *Pracovní kontext agenta*: prostředí, doména, stránka (s cílem a působením, jsou-li zadané), komponenta / uzel, cesta v repozitáři
     (`sourceRef`, jinak „navržená cesta“ s upozorněním, že není souborem). Záložky **Zadání** (název, účel, vstupní a
     výstupní port, kritéria dokončení, stav), **Vazby** (příchozí a odchozí vazby), **Práce** (brány definice hotovo jako dlaždice, kroky plánu `spec.steps` se stavem, běh: kdo staví, běžící krok,
     otevřené nálezy strážců; **Otevřít v Editoru**). Záložka Práce jen čte: kartu ze snímku `GET /api/oporahub/agent-state`
     (`cards[]`: `dod`, `steps.items`/`current`, `lease`, `guardFindings`, stejný zdroj jako tvář karty na plátně a detail karty)
     a kroky z pracovního zadání (`GET /api/node-spec`). Bez karty ve snímku ukáže „nenapojeno“. Fáze uzlu tu už není.
3. **Editor** (běžný, plátno 3) – detailní rozbor prvku pro agenty nad stejným ID (zjištění, varianty, rozhodnutí, výstupy).
   Do Editoru se jde jen ze stránky / prvku, nikdy bez ID.

## Pravidla

- Žádné druhé úložiště: vše je projekce grafu (`/api/view`, `/api/graph`, `/api/canvas-plan`); zápis s digestem.
- Strukturu stránek mění jen Struktura v levém panelu plátna 2; plátno stránky ukazuje layout a logiku jedné stránky.
- Pracovní zadání (`spec`) se v Detailu prvku jen čte a otevírá v Editoru; Detail smí měnit jen název a účel (stejně jako dnes).
- Neznámé hodnoty se označí „nedostupné“ / „zatím nic“, nikdy se nevymýšlí (žádné ukázkové uzly).
- Barvy vrstev: frontend zelená, backend fialová, databáze jantarová, security červená, infrastruktura modrá, cache levandulová. Boxy layoutu mají barvu role (hlavička, navigace a patička modrá, úvod a výzva zelená, formulář fialová, boční panel levandulová, galerie jantarová).

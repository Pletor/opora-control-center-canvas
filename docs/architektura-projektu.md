# Architektura projektu – kontrakt obrazovek

Zdroj: sektor „Projekty a zdroje“ (`a74ccd78-5c02-4004-bdb1-fa3d6478946a`) v projektu OPORA Control Center
a obrázky na jeho kartách (Vygenerování domény → Architektura projektu → Editor stránek → Záložka Editor).
Kód (`frontend/project/architecture-editor/`) tento kontrakt provádí, nemění ho.

## Proces (pořadí je závazné)

1. **Mapy architektury** – výběr prostředí a domény. Řádek *Produkce* (štítek „Produkce“, „Aktivní prostředí“)
   a řádek *Vývoj* (štítek „Vývoj“, „Oddělený prostor pro změny a ověření“). Každá doména je karta:
   ikona druhu (web / aplikace / administrace), host, „druh · účel“, čip `ID` (plné ID v bublině, klik zkopíruje), odkaz **Otevřít mapu domény**.
   Slovo „projekt“ patří jen celému projektu; jedna doména je vždy „doména“ (Mapa domény, Navigace domény).
   Doména = sektor `site.kind = "application"` s jedním prostředím; vše má vlastní ID, domény ani funkce se nemíchají.
2. **Mapa domény** (jedna doména) – jediné místo, kde se mění struktura: stránky, podstránky, pořadí, navigace,
   přidání a odebrání. Vlevo karta domény (prostředí · doména, host s čipem ID, účel, **+ Přidat stránku**) a seznam
   stránek (ID v bublině); uprostřed **NAVBAR** hlavních stránek a karty stránek s podstránkami (**+ Podstránka**).
   Stránka (`site.kind = "page"`) nese vedle cesty nepovinný záměr člověka: **Cíl stránky** (`goal`, 1–200 znaků),
   **Působení** (`feel`, 1–120) a **Popisek v menu** (`navLabel`, 1–40; NAVBAR ukazuje `navLabel`, jinak název).
   Prázdné pole se neukládá. Sekce stránky (`sections`: role, název, záměr) navrhuje agent; karta stránky ukazuje
   cíl na jednom řádku a sekce jako štítky, formulář stránky je jen vypíše (`docs/architektura-pro-agenty.md` §3.1).
3. **Editor stránky** (jedna stránka, vlastní ID) – rychlá infografika: co stránka obsahuje a jak spolu části souvisí.
   Čtyři sloupce:
   - **Strom projektu / Knihovna prvků** (vlevo). Strom: projekt → *Produkce LIVE* / *Vývoj DEV* (sbalitelné) → doména
     (host, druh · účel) → stránky, aktivní zvýrazněná, **+ Stránka** pod každou doménou. Knihovna: rodiny prvků
     (Frontend, Backend, Databáze, Security, Testy, Cache, Cloud a infrastruktura) jako barevné dlaždice, hledání, přetažení.
   - **Mapa architektury** (plátno) – oblasti (přerušovaný rámeček) → sektory → uzly; barva podle vrstvy, porty vlevo/vpravo,
     vazby mezi nimi, „N uzlů“ na hlavičce, **+ Přidat komponentu / uzel / sektor / oblast**.
   - **Hierarchický editor komponenty** (vybraný prvek) – drobečková cesta, „<název> · vnitřní struktura“, oblasti → sektory → uzly
     se stavem (Hotovo / V řešení / Čeká), **+ Přidat uzel**, **+ Přidat oblast**; pod tím **Workflow uživatele**
     (řetěz uzlů podle vazeb `next`) a **Pipeline práce** (fáze uzlu: discover → define → build → verify → live).
     **← Zpět na mapu** zavře sloupec.
   - **Detail prvku** (vpravo) – *Pracovní kontext agenta*: prostředí, doména, stránka (s cílem a působením, jsou-li zadané), komponenta / uzel, cesta v repozitáři
     (`sourceRef`, jinak „navržená cesta“ s upozorněním, že není souborem). Záložky **Zadání** (název, účel, vstupní a
     výstupní port, kritéria dokončení, stav), **Vazby** (příchozí a odchozí vazby), **Práce** (fáze, uzavření, **Otevřít v Editoru**).
4. **Editor** (běžný) – detail pro agenty nad stejným ID. Do Editoru se jde jen ze stránky / prvku, nikdy bez ID.

## Pravidla

- Žádné druhé úložiště: vše je projekce grafu (`/api/view`, `/api/graph`, `/api/canvas-plan`); zápis s digestem.
- Strukturu stránek mění jen Mapa domény; Editor stránky ji jen zobrazuje a odkazuje do ní (**+ Stránka** otevře formulář v Mapě domény).
- Pracovní zadání (`spec`) se v Detailu prvku jen čte a otevírá v Editoru; Detail smí měnit jen název a účel (stejně jako dnes).
- Neznámé hodnoty se označí „nedostupné“ / „zatím nic“, nikdy se nevymýšlí (žádné ukázkové uzly).
- Barvy vrstev: frontend zelená, backend fialová, databáze jantarová, security červená, infrastruktura modrá, cache levandulová, oblast jantarová přerušovaná.

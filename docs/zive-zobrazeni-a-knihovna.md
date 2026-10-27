# Živé zobrazení, knihovna komponent a skripty místo tokenů

Dodatek ke kontraktu `docs/architektura-pro-agenty.md` (rozhodnutí uživatele 2026-10-27). Inspirace: TechViz Studio
(replika a rozbor v `P:\0. OSVC\8. Code\07. Aplikace\04.Architektura-projektu\analysis`); z ní bereme jen
naměřené hodnoty a chování, kód se nepřebírá.

## 1. Princip

- **Pohyb ukazuje jen skutečný stav.** Zdroje: proces karty (kuličky, nárok práce), běh harnessu a ověření,
  výsledek cesty zákazníka (`passed | failed | running`), druh toku na vazbě (`carries`), návrh a změna v
  OporaHubu, růst oblasti při tahu. Žádná simulace zátěže, propustnosti ani monitor procesů.
- **Klid je výchozí.** Trvale se hýbe jen to, co právě běží (karta s nárokem, běžící ověření, běžící cesta).
  Událost (přijato, odmítnuto, prošlo, spadlo) se ukáže jednou a utichne.
- **`prefers-reduced-motion: reduce`**: žádná animace ani přechod; stav nese barva, tvar a text.
- Každá animace je CSS na dílku (BEM třída, `@keyframes` v jeho `styles/*.css`), nikdy nový běh v JS na snímek.

## 2. Vazby podle `carries` (statické odlišení)

| `carries` | Barva | Čára | Význam |
|---|---|---|---|
| `navigation` | `#4ab8ff` | plná | zákazník přechází |
| `data` | `#58d7c1` | plná | čtení dat |
| `command` | `#b49cff` | plná, o 0,5 px silnější | odeslání nebo zápis |
| `event` | `#f4b94f` | čárkovaná `6 4` | událost |
| neurčeno | dnešní vzhled | | migrace bez odhadu |

Háček na hraně: třída `edge--carries-<hodnota>` (etapa 4a). Popisek druhu je v tooltipu, ne na čáře.

## 3. Katalog pohybu (hodnoty ze Studia → stav OPORY)

| Efekt | Stav OPORY | Hodnoty | Kde |
|---|---|---|---|
| Tok po vazbě: 2 tečky po trase hrany | cesta zákazníka právě běží (jen hrany na cestě) | tečka 5 px, glow `0 0 6px` barvy druhu, cyklus 1,05 s + 70 ms × (pořadí mod 4), linear | plátno, editor architektury |
| Zastavená tečka s křížkem | cesta spadla na této vazbě (`failedAt`) | staticky, barva `#ff5c78` | editor architektury |
| Puls jednou | cesta prošla / návrh přijat | 0,9 s, jako `flow-map-pulse` | editor, OporaHub |
| Zatřesení jednou | návrh odmítnut | 0,4 s, jako `flow-map-shake` | OporaHub |
| Čárkovaný puls okolo karty | čeká na člověka | 1,85 s ease-in-out, opacita 0,4 → 0,95, `1.5px dashed #f4b94fd1`, inset −3 px | plátno, velín |
| Výplň kroku | průběh ověření (hotovo/celkem) | přechod výšky 0,22 s | karta, OporaHub |

Existující pohyb zůstává a nezdvojuje se: `opora-working` (2 s, nárok), `node-card-stage-pulse` (1,4 s, běží),
`opora-added-pulse`, `office-beacon`, `flow-map-*`, `event-stream-in`.
Výkon: tečky jen na hranách běžící cesty (strop 40 hran), animace se pozastaví, když je dokument skrytý.

## 4. Interakce

- **Porty:** zásahová plocha 26 px, viditelný bod 10 px, obojí konstantní na obrazovce při každém zoomu;
  neplatný cíl při tahu má opacitu 0,55; focus-visible modrá linka; tooltip s druhem portu na hover i focus.
- **Nabídka vazby z výstupního portu:** dvě části, „Existující karty“ (jen kompatibilní, hledání podle názvu)
  a „Vytvořit a propojit“ (z knihovny). Karta i vazba vzniknou jednou změnou; Escape ruší. Nabídka nepřekrývá
  vstupy. Nová karta se položí vpravo od zdroje.
- **Oblast:** popisek velkými písmeny 10 px, tah karty ji zvětšuje (hotovo, `area-growth.ts`).

## 5. Knihovna komponent: přesný kontext pro agenta

Rozšiřuje existující `CatalogItem` (`frontend/editor/component-library/library-catalog/logic/library-catalog.ts`).
Všechna pole volitelná, lint `catalogLint` je hlídá.

| Pole | Tvar | K čemu |
|---|---|---|
| `tech` | 1–80 znaků | předvyplní `card.tech` (etapa 5) |
| `states` | 1–8 krátkých stavů | předvyplní `card.states`; u `command` povinně stav chyby |
| `ports` | `[{id, direction: in|out, carries}]` | při vložení navrhne vazby s `carries` |
| `fetch` | `{files: [], docs: []}` | co si agent stáhne do kontextu; lint ověří, že soubory existují |
| `fill` | seznam polí | co přesně má agent vyplnit (např. `sourceRef`, `spec.acceptance`) |

Vložení z knihovny je deterministické: skript složí kartu (název, záměr, `tech`, `states`, navržené vazby,
`fetch`) bez modelu. Agent dostane v `node-brief` jen díry k vyplnění (`fill`) a seznam `fetch`.

## 6. Skripty místo tokenů

Co jde spočítat, počítá skript; model jen vyplňuje, co skript označí jako díru.

| Skript | Výstup | Etapa |
|---|---|---|
| kontrola mapy `map_check` | díry podle pravidel §5 kontraktu | 6 |
| odvození přechodů cesty (trychtýř) | `segments`, `youAre`, `journey.broken`, `journey.unrealized` | 7 |
| výřez mapy `node-brief.architecture` | do ~600 tokenů | 7 |
| vložení z knihovny | karta + vazby + `fetch` + `fill` | L1 |
| kostra testu cesty | soubor testu podle výbavy harnessu (Playwright u webu) | 8 |

Data se neztrácejí: skripty jen čtou přijatou architekturu a zapisují přes stejné návrhy a změny grafu jako dnes.

## 7. Etapy dodatku

| # | Obsah | Závisí na |
|---|---|---|
| M1 | barvy a čáry `carries`, porty 26/10 px, tooltip | 4a |
| M2 | čeká-na-člověka puls, výplň kroků ověření | — |
| L1 | knihovna: `tech`, `states`, `ports`, `fetch`, `fill` + deterministické vložení | 4a, 5 |
| M3 | tok po vazbách běžící cesty, puls a zatřesení událostí | 7, 8 |
| M4 | nabídka vazby z portu | L1 |

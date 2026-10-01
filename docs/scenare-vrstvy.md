# Scénáře vrstvy: OPORA → kód → GitHub → Oracle

## Cíl

Ověřovat, že řetěz z `docs/synchronizace-pravdy.md` funguje tak, jak byl navržen. Každý scénář je spustitelný test nad skutečným gitem a skutečným API, ne popis. Co scénář odhalí, se buď opraví, nebo se zapíše sem jako nález s krokem kontraktu, který ho uzavře.

Linear zatím napojený není. Scénáře proto končí u trojice OPORA, kód v gitu a Oracle; místa, kde by vstupovala úloha, jsou v tabulce označená.

## Pravidla práce

- Scénář je test vedle modulu, ne dokument. Dokument drží jen seznam, stav a nálezy.
- Nález se zapisuje i tehdy, když se hned opraví. Záznam říká, co bylo špatně a proč.
- Nic se nepovažuje za hotové bez `uv run pytest backend`, `npm test` a `npm run build`.
- Aplikace ani scénáře nespouštějí žádný model.
- Když scénář narazí na chybějící část procesu, nesimuluje ji. Chybějící část je nález.

## Žebříček úrovní

Scénáře jdou od poslušného průchodu po někoho, kdo proces chce rozbít. Každá úroveň má vlastní soubor testů.

| Úroveň | Kdo hraje | Soubor |
|---|---|---|
| L1 | proces běží, jak byl navržen | `backend/canvas/test_sync_report.py` |
| L2 | běžné odchylky: smazaný soubor, přejmenování, zadání napřed | `backend/canvas/test_sync_scenarios.py` |
| L3 | agent dělá chyby: špatná vazba, souběžný zápis, commit mimo zadání | `backend/canvas/test_sync_adversarial.py` |
| L4 | kritik chce bránu obejít: podvržený důkaz, přepsaná historie, cesta ven z projektu | `backend/canvas/test_sync_adversarial.py` |
| L5 | poškozený svět: rozbitá data, zmizelá složka, zátěž a souběh | `backend/canvas/test_sync_broken_world.py` |

## Scénáře

| # | Scénář | Co ověřuje | Stav |
|---|---|---|---|
| S1 | Vazba na existující kód | uzel se zdrojem projde kontrolou `source`, echo nevzniká | hotovo |
| S2 | Smazaný soubor | `source-missing`, uzel nesmí do mainu | hotovo |
| S3 | Přejmenovaný soubor | `source-renamed` s novým názvem v důkazu | hotovo |
| S4 | Návrh, který už existuje | `planned-exists` | hotovo |
| S5 | Dvě karty na téže cestě | `duplicate-path` | hotovo |
| S6 | Zadání v2 proti kódu v1 | `spec-ahead`, `canMerge` nepravda, `canCommit` pravda | hotovo |
| S7 | Commit v mainu bez páru | `code-unclaimed` | hotovo |
| S8 | Pracovní prostor mimo main | `base-stale` | hotovo |
| S9 | Pracovní prostor bez uzlu | `workspace-orphan` | hotovo |
| S10 | Rozbitý odkaz v dokumentaci | `doc-path-missing` u dotčeného rozsahu | hotovo |
| S11 | Celá cesta k zelené | zadání → commit OporaHubu → kód → důkaz → zelený běh → `canMerge` | hotovo |
| S12 | Prázdná oblast a sektor | prázdný rozsah není zelený | hotovo |
| A1 | Vazba na neexistující cestu | API uložení odmítne | hotovo |
| A2 | Souběžný zápis zadání | druhý zápis selže, text nezmizí | hotovo |
| A3 | Smazaný uzel se zadáním | osiřelá data jsou vidět | hotovo |
| A4 | Commit mimo vlastněné cesty | `code-unclaimed` | hotovo |
| A5 | Zelený běh k cizímu commitu | rozsah nezezelená | hotovo |
| B1 | Cesta ven z projektu | API odmítne | hotovo |
| B2 | Podvržený trailer | pár sám o sobě bránu neotevře | hotovo |
| B3 | Přepsaná historie | report nespadne a nelže | hotovo |
| B4 | Chybějící větev main | report nespadne | hotovo |
| B5 | Smazaný `.git` | odpověď místo chyby 500 | hotovo |
| B6 | Přehnané vstupy | jasná chyba místo pádu | hotovo |
| B7 | Commit datovaný do budoucnosti | nesmí uzavřít `spec-ahead` | hotovo |
| B8 | Trailer bez sáhnutí na vlastněnou cestu | brána zůstane zavřená | hotovo |
| C1 | Poškozený graf v databázi | srozumitelná chyba místo pádu | hotovo |
| C2 | Zdrojová složka zmizí za běhu | vazby hlásí chybějící zdroj | hotovo |
| C3 | Ze souboru se stane složka | echo o druhu vazby | hotovo |
| C4 | Zadání u sektoru a oblasti | report nespadne | hotovo |
| C5 | Pět pater zanoření | oblast počítá i nejhlubší patro | hotovo |
| C6 | 200 uzlů a 40 commitů | report do 20 sekund | hotovo |
| C7 | Dva běhy kontrol za sebou | platí novější | hotovo |
| C8 | Pět souběžných dotazů | všechny projdou stejně | hotovo |

## Nálezy

| # | Nález | Důsledek | Stav |
|---|---|---|---|
| N1 | Prázdná oblast vycházela zeleně, protože oblast nesmí mít potomky a kontrola „vše pod ní je zelené“ procházela naprázdno | všech 8 oblastí skutečného projektu hlásilo hotovo | opraveno 2026-09-17, test v `backend/canvas/test_sync_verdicts.py` |
| N2 | `backend/memory/test_roles.py::test_reload_picks_up_a_changed_file` je nestabilní: dva rychlé zápisy dostanou na Windows stejný čas, protože hodiny tikají po zhruba 16 ms | brána na testech by padala náhodně | opraveno 2026-09-17: `backend/memory/roles.py` drží v mezipaměti otisk obsahu místo času úpravy |
| N3 | Důkaz kroku a zelený běh testů nikdo nezaznamenával, takže `evidenceComplete` a `checksGreen` byly vždy nepravda | žádný rozsah nemohl zezelenat | uzavřeno 2026-09-18: důkazem je proces ve stavu `done`, běh kontrol se zapisuje přes `POST /api/check-run` (`backend/canvas/check_runs.py`); scénář S11 projde celou cestu k zelené |
| N4 | OporaHub neexistoval, takže `opora-uncommitted` se nepočítalo a kontrola `spec` koukala jen na revizi | „zacommitované zadání“ se nedalo ověřit | uzavřeno 2026-09-18: `backend/canvas/opora_hub.py` + `POST /api/opora-commit`; brána 1:1 teď vyžaduje commit zadání a merge pustí jen zelený verdikt (`POST /api/opora-merge`) |
| N6 | `code-unclaimed` podle původního znění nemohlo nikdy vzniknout: commit nad vlastněnou cestou se párováním podle cest rovnou spáruje | echo o kódu bez zadání by mlčelo | opraveno 2026-09-17, význam změněn na „commit sáhl do kódu, který nikdo nevlastní“, kontrakt část 7 upraven |
| N7 | Pár postavený jen na traileru ve zprávě commitu otevíral bránu, aniž by se kód vůbec dotkl vlastněné cesty | stačilo napsat `Opora-Node: <uzel>@2` a rozsah mohl zezelenat bez řádky kódu | opraveno 2026-09-17: pár nese `touchesOwned` a brána ho uzná, jen když commit v mainu sáhl na vlastněnou cestu |
| N8 | `canCommit` padalo na echu `evidence-missing` a `checks-unknown`, takže každý spárovaný uzel měl zakázanou i práci ve větvi | odporovalo části 8 kontraktu; agent by nesměl pracovat na ničem, co už je v kódu | opraveno 2026-09-17: commit blokuje jen echo o vazbě (`source-missing`, `source-renamed`, `closed-area-touched`), zbytek blokuje pouze merge |
| N9 | Bez traileru ve zprávě commitu nešlo `spec-ahead` nikdy uzavřít: pár bez revize v kódu hlásil „poslední pár nese revizi None“ navždy | brána by zůstala zavřená každému, kdo si trailery nepíše, přestože kontrakt je má jako nepovinné | opraveno 2026-09-17: bez traileru rozhoduje čas, pár v mainu musí být novější než uložené zadání |
| N10 | Commit s datem v budoucnosti by se bral jako důkaz, že kód plní novější zadání | stačilo posunout hodiny a `spec-ahead` zmizelo | opraveno 2026-09-17: commit s datem po okamžiku pozorování se za důkaz nebere |
| N11 | Podvržený trailer `Opora-Node: <uzel>@99` v commitu, který se vlastněné cesty ani nedotkl, umlčel `spec-ahead` a otevřel kontrolu `pair` | zprávu commitu si pisatel určuje sám, takže to byl klíč od brány zdarma | opraveno 2026-09-17: revize z traileru platí jen u commitu, který sáhl na vlastněnou cestu nebo přišel z větve rozsahu; jinak je pár slabý |
| N12 | Zadání smazaného uzlu zůstalo v databázi bez jediného echa a uzel se stejným id ho tiše zdědil | tichá data, která nikdo nevidí, a riziko záměny | uzavřeno 2026-09-18: report osiřelá zadání i texty sbírá a hlásí je jako `workspace-orphan` |
| N13 | Vnořené sektory se vyhodnocovaly odshora dolů, takže rodič se ptal na potomka, který ještě neměl verdikt, a hlásil nehotovo i nad zelenými rozsahy | pět pater zanoření nikdy nezezelenalo | opraveno 2026-09-18: verdikty jdou zdola nahoru podle hloubky |
| N14 | Sektor a oblast dostávaly echo o hotovosti (`evidence-missing`, `checks-unknown`), které po nich kontrakt nechce | sektor se zelenými uzly zůstal červený kvůli vlastnímu chybějícímu důkazu | opraveno 2026-09-18: echo o hotovosti se ptá jen uzlu |
| N15 | Oblast počítala potomky podle `parentId`, jenže oblast nikdy není rodičem: členství je dané polohou na plátně | oblast nešla nikdy uzavřít | opraveno 2026-09-18: report posílá `areaId` z `backend/canvas/areas.py` a verdikt podle něj počítá členy |
| N16 | Souběžné dotazy na report sahaly na sdílené SQLite spojení bez zámku | pět dotazů naráz vracelo rozbité odpovědi | opraveno 2026-09-18: čtení drží zámek služby, git a disk zůstávají mimo něj |
| N17 | Oblast se zadáním nesla vysoké `spec-ahead`, které nešlo nikdy uzavřít: podle grafu nevlastní žádnou cestu, takže k ní pár nemohl vzniknout | trvalý vysoký šum v echu | opraveno 2026-09-18: pár oblasti vlastní cesty rozsahů, které leží uvnitř ní na plátně; vlastní scénář na to ještě chybí |
| N18 | Poškozený graf v databázi vrací klientovi hlášku dekodéru JSON a kód 409 | chyba je pravdivá, ale nesrozumitelná; poškozená data nejsou konflikt | otevřeno |
| N19 | Když se ze souboru stane složka, hlásí se `source-missing` („cesta chybí“), i když cesta existuje a nesedí jen druh | název echa říká něco jiného než důkaz | otevřeno |
| N20 | Když zmizí celá zdrojová složka, vznikne vysoké echo u každé karty zvlášť (u 200 karet 200 ech) a nikde není věta o kořenové příčině | zahlcení místo diagnózy | otevřeno |
| N5 | API nerozlišuje, kdo zapisuje; agent a člověk jdou stejným vstupem | krok 6 kontraktu nelze dokončit bez rozhodnutí, podle čeho se pisatel pozná | částečně uzavřeno 2026-09-18: zápis do OporaHubu nese autora a `by.kind == "agent"` je odmítnut; zbytek API autora zatím nezná |

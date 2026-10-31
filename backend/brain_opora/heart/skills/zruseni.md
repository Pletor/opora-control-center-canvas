# Zrušení a přejmenování: jeden úkol napříč aplikací

Čteš to, protože člověk ruší nebo přejmenovává dřívější věc (stránku, variantu, službu, text tlačítka, adresu).
Rozdělené na víc úkolů nebo s výčtem „zhruba“ to nechá v aplikaci zbytky: odkaz v menu, otázku ve FAQ, pole
formuláře, test, který starou věc dál tvrdí.

## Postup
1. **Vzorce.** Vypiš si, čím se rušená věc v kódu projevuje: název a jeho tvary (velká písmena, skloňování),
   adresa (`/cenik`), klíč v datech nebo payloadu (`varianta`), název komponenty a souboru, CSS třída,
   i **související pole**, která existovala jen kvůli ní (pole formuláře, volba v selectu, sloupec, text nápovědy).
2. **Hledání ve zdroji.** Pro každý vzorec `Grep` v `src/` a v testech, včetně textů: FAQ, menu, patička,
   nadpisy, hlášky, popisky polí, alt texty, meta. Nehledej jen v souboru stránky. Nic nevynechávej podle odhadu.
3. **Jeden úkol.** Zapiš jeden úkol, ne úkol na soubor:
   - `--file` pro každý soubor, kde hledání něco našlo (i test a styl);
   - `--do` vyjmenuje po souborech, co odstranit nebo přepsat a čím to nahradit (nový text doslova, kam vede
     odkaz místo zrušené adresy);
   - `--done-when "hledání <vzorec> v src/ nic nenajde"` pro **každý** vzorec z bodu 1, včetně souvisejících polí;
   - plus jedno pozorovatelné chování (např. „menu nemá položku Ceník a /cenik vede na 404 / přesměruje na /“).
4. **Testy.** Test, který tvrdí zrušenou věc, se smaže nebo přepíše na nové chování; dej ho do `--file`
   a napiš to do `--do`. Test nesmí zůstat jen „zelený, protože nic nekontroluje“.
5. **Ostatní úkoly.** Otevřený úkol fronty, který rušenou věc staví nebo zmiňuje, zruš (`cancel --task`) nebo
   jeho `--do` promítni do tohoto úkolu. Rozhodnutí zapiš (`decide`), ať se věc v dalším plánu nevrátí.

## Kontrola před zápisem
- Každý nalezený soubor je ve `--file`, každý vzorec má svůj `--done-when`.
- Žádný soubor z `--file` není v `--dont-touch` téhož úkolu.

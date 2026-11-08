# Další kontrakty po ověření prvního zápisu

OP-086DEE. Tento dokument rozděluje zbývající implementaci, nenahrazuje úplné zadání ani inventář. M1 musí nejprve doložit skutečný průchod Srdcem a obnovenou stránku.

## Úplný návrh nad přijatým plánem

Existující `plan --no-accept` nad přijatým grafem nepřenáší text, bloky, porty, fragmentRef a rozšíření existujících karet. Požadavek uživatele nesmí nástroj řešit výzvou k automatickému přijetí. Navázat na nativní návrhy grafu a obsahu, jejich validátory a přijetí. Uložený návrh musí obsahovat všechna zamýšlená data a jejich očekávané revize, aby UI i následující relace zobrazily stejný návrh. Návrh nesmí měnit přijaté dokumenty, pracovní stav karet ani spustit realizaci. Rozšíření schématu musí zachovat čtení starších návrhů; nevytvářet druhý graf ani paralelní pravidla validace.

Povinné důkazy: návrh se zadáním, textem a blokem/portem přežije reload; přijatá hlava a obsah karty se před přijetím nezmění; změněná revize podkladu vyvolá konflikt; přijetí v izolovaném projektu vytvoří správný obsah a vazby; opakované přijetí nevytvoří duplicity. Částečný neatomický výsledek musí být explicitní a obnovitelný.

## Trvalé pokračování po výzkumu

Existující `research.changed` v research_events samo není událostí sledovanou Srdcem v opora_events. Doplnit konkrétní trvalou návaznost do existujícího mechanismu buzení a vstupů. Klíč pokračování je výzkum a jeho revize v projektu/prostoru; duplicitní doručení nesmí znovu vytvářet plán. Úspěch znamená uložené ID návrhu a ověřené zpětné načtení, nikoli konec LLM procesu. Přerušený běh zůstává dohledatelný a lze jej obnovit. Zápis návrhu nesmí sám spouštět další obecný výzkum.

Stav běhu, platnost tvrzení, stav rozhodnutí a práce jsou oddělené. Výzkum bez zdrojů vytvoří mezeru a neověřený závěr. Částečné podklady vedou k částečnému návrhu a pouze lokálním blokacím. Historické výzkumy V1–V5 a jejich zpětné vazby zůstávají zachované.

## Konečný katalog schopností a oprávnění

Každý řádek inventáře musí dostat pojmenovaný způsob volání, popis vstupu a výstupu, ověření a rozlišení chyb. Znovupoužít stávající doménové rozhraní; nesmí vzniknout neomezený HTTP proxy ani obcházení oprávnění. Lidské rozhodnutí vystavit jako přípravu návrhu a čekání. Identitu autora nebrat z volitelného JSON pole. Samostatně ověřit zakázaný projekt/prostor a model organizací, který aplikace skutečně má; chybějící organizační kontext nepřejmenovat na prokázanou izolaci.

Pohled relace (výběr, zoom, filtry) má vlastní identitu relace a revizi; nemění společné pozice uzlů ani pohled jiné relace. Návrat uloženého stavu nesmí být označen za ověřený jen na základě shody ID.

## Obnova a předání práce

Nativní receipt chrání proti duplicitám, ale `operation_incomplete` zatím vyžaduje řízené smíření skutečných úložišť. Zvlášť ověřit hranici graf/soubory/SQL a dokončení re-pin běhů; dokončení graph receipt není potvrzení dokončeného re-pin. Pokračování nesmí potichu použít novou revizi ani nový identifikátor operace.

Předávky znovupoužijí existující packet, assignment snapshot, lease a execution fencing. Doložit soupeření dvou agentů, přerušenou relaci, řízené převzetí a stale write. Změna podkladu označí pouze závislé předávky k novému posouzení. Produktová realizace Ample zůstává oddělená od opravy plánovacího systému.
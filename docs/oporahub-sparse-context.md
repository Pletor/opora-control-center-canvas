# Kontext execution podle závislostí

Tato navazující etapa je rozpracovaná. Kontext v1 nadále používá konzervativní
kontrolu celého přijatého grafu. Níže je cílový kontrakt v2; samotný nový journal
nebo selektor neopravňuje server inzerovat hotové v2.

Implementovaný základ: `select_scope` a `project_graph` v modulu
`backend/editor/agent_packet/specification_scope.py` a explicitně aktivovaný
journal `database/repositories/opora_context_events.py`. Tyto funkce zatím
nejsou novou verzí veřejného execution API. Journal sleduje osm deklarovaných
SQL zdrojů; selektor rozlišuje grafový kontext, čtení obsahu a stav pro překážky.
`validate_accepted_lineage` v `backend/canvas/opora_execution_lineage.py`
ověřuje zvlášť přijatou historii grafu a vybraných zadání. Všechny kroky musí
mít manifest, správný otisk a nezměněnou projekci; výchozí limit je 256 revizí.
Výsledek `acceptedScopeUnchanged` neuděluje execution oprávnění a nedokládá
živé instrukce, texty, kresby, lease ani rozpočet. Ty kontroluje navazující vrstva.

Soukromý `opora_context_snapshot.capture` pořizuje v transakci úplné řádky osmi
SQL zdrojů včetně starších revizí, nejvýše 8 192 řádků a 8 MiB. `opora_context_replay.replay`
čte ověřený journal, porovná sémantickou projekci po každém přechodu a nakonec
porovná celý přehrávaný stav s novým SQL snímkem. Výchozí a maximální limit
jedné kontroly je 256 přechodů; překročení odmítne, nic se potichu nezkrátí.
Raw snímek ani raw digest nejsou veřejný podklad nebo capability. Výsledek
`liveScopeUnchanged` sám neověřuje přijatou historii, registry, soubory ani lease.

Čistá `project_sql_context` převádí soukromé řádky na skutečně čtené zadání,
instrukce, texty, scény kreseb, projektová pravidla/nastavení a stav překážek.
Vyžaduje SQL graph authority, ověří její otisk a složí sdílenou architekturu;
legacy souborový či Git fallback nepoužije. Texty a zadání uzlů architektury čte
z jejich vlastníka `architecture`; tuto volbu zachová v dokladu. To je výslovný
kontrakt připravované v2, nikoli změna dnešního v1 zachycení textu. Název a identita
projektu jsou dodané zmrazené vstupy; jejich původ a životní cyklus ověřuje volající.
Citlivé hodnoty zůstávají v interní projekci rozlišitelné před redakcí. Projekce
ani její SHA256 nesmějí samy sloužit jako veřejný kontextový token.

## Verze a neměnné oprávnění

`contextProtocolVersion: 2` je samostatné vyjednávání kontextu, nikoli číslo
execution protokolu rozpočtů. Kombinace budget-v2/context-v1 zůstává platná.
V2 se vyžádá výslovně; odmítnutí nebo chybějící pokrytí nikdy nevede k tichému
přepnutí na v1. Původní požadavky a původní chování v1 zůstávají kompatibilní.

Claim stále kontroluje očekávanou přijatou hlavu. Uloží původní přijatou revizi,
zadání, jeho digest, verzi selektoru a soukromý doklad závislostí. Pozdější
nesouvisející přijetí tuto identitu, rodinu rozpočtu, pokus ani pevný konec běhu
nemění. Heartbeat a první výsledek přidají oddělený doklad aktuální validace.
Přesná opakování zůstávají autentizovaná a vracejí historický výsledek před
novou kontrolou oprávnění. Žádné automatické recapture, reclaim či přijetí.

## Selektor musí odpovídat skutečným čtením

Výběr není celý propojený komponent grafu. Základem je cílová karta, její
předci a úplný podstrom. Doplní se konce vazeb skutečně čtených pro tento úkol,
jejich předci a podstromy zdrojových sektorů potřebné pro kontrolu překážek.
Samotné přidání konce vazby neznamená rekurzivně číst všechny jeho další vazby.
Vazby se vybírají podle konkrétních predikátů čteček, ne neurčitou tranzitivní
uzávěrou všech hran. Cyklus či chybějící potřebný konec je chyba.

Doklad obsahuje nejen vybraná ID, ale i negativní podmínky: nepřítomné děti,
hrany, brány, pravidla, rozhodnutí a kandidáty oblasti či navigace. Při změně
je nutné znovu vyhodnotit predikát i v případě původně prázdného výsledku.
Oblast se počítá nad úplnými kandidáty; souřadnice mohou změnit příslušnost,
i když se samy nepovažují za text zadání. Navigace zachová pořadí stránek
v příslušných doménách. Projektová pravidla a nastavení zůstávají sdílené,
pokud je skutečná čtečka vystavuje všem kartám.

Per-card specifikace, texty, instrukce, round, příchozí rozhodnutí a root/související
kresby se zachovají. Raw otisk před redakcí je soukromý; změna dvou rozdílných
citlivých hodnot se nesmí ztratit shodnou redakcí. Externí soubory, síť a obrazové
bajty nejsou zachycené jen tím, že se v zadání objeví odkaz. Deklarovaný access
set sám není OS sandbox ani oprávnění přijímat plán nebo měnit zdrojový kód.

## Přechody, ABA a pokrytí

Každá relevantní přijatá revize mezi origin a nynější hlavou musí projít
kontrolou. Relevantní A→B→A nebo odstranění a znovuvytvoření zneplatní původní
oprávnění; shodný konečný JSON nestačí. Chybějící, cizí, nesouvislá nebo příliš
dlouhá historie se odmítne, nikoli zkrátí. Původní accepted manifest je nutný.

Pro živá data se přidává transakční journal s původním a novým obsahem řádku.
SQLite triggery pokryjí i přímé SQL writery, import a obnovu; rollback vrátí
i journal. Enrollment je výslovné, uvnitř transakce, a před ním nevznikají nové
události. Události mají rostoucí pořadí, coverage ID a omezené bajty. Přetečení
zmrazí pokrytí, nikoli běžné starší zápisy; v2 potom nesmí vrátit platné oprávnění.
Journal se nesmí prořezat či obnovit zpět pod existující capability.

Instalace nastavuje `recursive_triggers` pro dané SQLite spojení, aby zachytila
i mazací část `INSERT OR REPLACE`. Zápis jiným spojením s vypnutým nastavením
pokrytí zmrazí. Limity jsou 4 096 událostí, 8 MiB na událost a 128 MiB bajtů
na projekt. Zmrazení ani změněná generace DDL se automaticky neopravují;
běžné starší zápisy mohou pokračovat, nové sparse oprávnění se nepřizná.
Přenos projektových dat kopíruje události před coverage metadaty, aby trigger
počítadla znovu nepřičetl již zaznamenané bajty. Přenáší se i profil projektu,
hlava sdílené architektury a její historie. Původní generace DDL zůstává
zachovaná; import do jinak vytvořené DB tím neobnoví staré oprávnění.
Původní a nový obsah řádku jsou soukromé podklady, nikoli veřejný activity feed.

Úplný původní/nový řádek umožní pozdější sémantické vyhodnocení, ale sám ještě
neprokazuje, že se změna týká úkolu. Validator musí projít relevantní přechody
a vyhodnotit uzavřený selektor. Události rollbacknuté transakce se nepočítají;
relevantní přechody zapsané v úspěšné transakci se posuzují konzervativně i při
následném návratu hodnoty v téže transakci. Čtení a validace mají konečné limity.

Pokrytí zahrne pracovní graph authority, stav, specifikace/texty/kresby,
projektové nastavení a skutečně čtené změny zdrojů či resolverů. Registry a
souborové zdroje nelze vydávat za pokryté projektovým SQL journalem. Neověřený
writer nebo změněná instalace triggerů znamená nedostupnost v2. Záznam bez
pokrytí nepovolí tvrzení „ABA bezpečné“. V1 zůstává funkční.

## Office a dokončení

Office musí buď zachytit task-affecting vstupy `prepareTask` / `withReaBrief`
v claimu, nebo je pro sparse dispatch vypnout. Statické pokyny vykonavatele jsou
zvlášť verzované; cesty, token a result endpoint jsou metadata oprávnění.
Restart ověří přesné uložené piny a nesmí přepnout verzi ani rozpočet.

Dokončení etapy vyžaduje skutečný průchod claim→nesouvisející změna→heartbeat
→výsledek, relevantní accepted/live ABA, negativní predikáty, souběhy, rollback,
restore a Office HTTP test se zachováním v1. Samostatný journal či hash nestačí.
README a přehled implementace se aktualizují až podle ověřeného chování.

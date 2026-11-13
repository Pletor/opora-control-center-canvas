# Kontext execution podle závislostí

Kontext v1 nadále používá konzervativní kontrolu celého přijatého grafu. Kontext
v2 se výslovně připraví přes POST `/api/oporahub/executions/context` s poli
`project`, `workspace`, `nodeId`, `contextProtocolVersion: 2`. Stejná verze se
přidá do claimu vedle očekávané přijaté hlavy a vráceného opaque kontextového
tokenu. Neúspěch nikdy nevede k tichému přepnutí na v1. Samotný journal nebo
selektor neopravňuje pokračovat v běhu; rozhoduje celá execution kontrola.

Implementovaný základ: `select_scope` a `project_graph` v modulu
`backend/editor/agent_packet/specification_scope.py` a explicitně aktivovaný
journal `database/repositories/opora_context_events.py`. Execution API je spojuje
se soukromým původním pinem a registry fence. Journal sleduje osm deklarovaných
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

Po výslovné přípravě v2 chrání SQL triggery i ukazatel přijaté hlavy projektu:
smí postoupit jen na existující revizi stejného scope, jejíž rodič odpovídá původní
hlavě. Přímý SQL rewind, delete/reinsert, REPLACE a přesun identity se odmítnou;
nový workspace může začít vlastním kořenem. Nezměněný ukazatel je povolený.
Tím se mezirevize neschová prostým vrácením pointeru. Celý obsah revize a manifestu
nadále ověřují repository hashe; samotný SQL trigger kontroluje strukturální
identitu a rodiče. Bez přípravy v2 se chování starších projektů nemění.

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
Aplikace každé své DDL zapisuje jako generaci schématu do `opora_schema_generations`
v téže databázi (append-only, `from_version → to_version`, autor a důvod). Pin
proto přijímá souvislý řetězec zapsaných generací od své verze k aktuální
`PRAGMA schema_version`; cizí DDL nechá mezeru a pin dál odmítne. Tabulka generací
nevstupuje do otisků schématu ani triggerů.
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

Pokrytí zahrnuje pracovní graph authority, stav, specifikace/texty/kresby,
projektové nastavení a skutečně čtené změny zdrojů či resolverů. Registry mají
samostatný monotónní fence s kontrolou zdrojů, generace a lifecycle; nejsou
pokryté projektovým SQL journalem. Souborové zdroje pokryté nejsou. Neověřený
writer nebo změněná instalace triggerů znamená nedostupnost v2. Záznam bez
pokrytí nepovolí tvrzení „ABA bezpečné“. V1 zůstává funkční.

## Office a dokončení

Office se zapíná proměnnou `AGENT_OFFICE_OPORA_CONTEXT_VERSION=2`; jiná nastavená
hodnota se odmítne a nenahrazuje se v1. Pro sparse dispatch vypíná dynamické
`prepareTask` / `withReaBrief`; zadání bere z neměnného assignmentu.
Statické pokyny vykonavatele jsou zvlášť verzované jako `opora-office-execution/2`;
cesty, token a result endpoint jsou metadata oprávnění.
Restart ověří přesné uložené piny a nesmí přepnout verzi ani rozpočet.

Dokončení etapy vyžaduje skutečný průchod claim→nesouvisející změna→heartbeat
→výsledek, relevantní accepted/live ABA, negativní predikáty, souběhy, rollback,
restore a Office HTTP test se zachováním v1. Samostatný journal či hash nestačí.
Skutečný Office HTTP průchod je ověřený pro budget-v1 i budget-v2 a relevantní
živé ABA. Piny, klíč a registry binding přežívají reopen; archivace oprávnění
odmítne. Ani tento režim není OS sandbox nebo důkaz ukončení procesů.

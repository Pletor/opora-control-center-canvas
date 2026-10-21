# Napojení kontextu v2 — implementační kontrakt

Tento kontrakt popisuje implementované výslovné napojení v2 a jeho hranice.
Základní invarianty a meze jsou v [kontextu podle závislostí](oporahub-sparse-context.md).

## Explicitní příprava a claim

Stávající GET execution context a claim bez `contextProtocolVersion` zachovají v1.
Nový POST `/api/oporahub/executions/context` přijme přesně `project`, `workspace`,
`nodeId`, `contextProtocolVersion: 2`. Vyžaduje identitu jako claim. Příprava
výslovně aktivuje SQL pokrytí a registruje vazbu zdrojů; nezaloží lease ani pokus.
Vrátí dostupnost, přijatou hlavu, opaque `contextVersion`, verzi kontextu a odděleně
execution protocol/budget. Žádné tiché snížení verze při odmítnutí.

Claim přidá volitelné `contextProtocolVersion: 2`. Očekávaná hlava i kontextový
token se porovnají uvnitř existující transakce před vytvořením lease. Token je
HMAC-SHA256 soukromé projekce a vazby zdrojů, s trvalým náhodným klíčem projektu;
raw digest ani raw snímek se nevrátí klientovi. Klíč ani pin se nikdy automaticky
neobnoví při poškození. Příprava nové pokrytí založí, ale zmrazené neopravuje.

Veřejné zadání obsahuje redigovaný uzavřený kontext, vybrané přijaté dokumenty,
původní přijatou revizi a opaque token. Soukromá tabulka uchová úplný výchozí
SQL snímek, metadata a binding zdrojů podle execution ID. Record veřejného běhu
nikdy neobsahuje soukromý pin. Limit soukromých pinů je 64 MiB na projekt.

## Zdroje a registry

Režim vyžaduje SQL graph authority a shodu s aktuálním složeným grafem. Žádný
Git/file fallback. Při claimu musí graf i vybraná zadání odpovídat přijaté revizi.
Výslovná příprava může jednorázově převést přijatý SQL draft (vestavěný,
local nebo empty projekt) na SQL authority bez změny grafu či přijaté revize.
Od té chvíle ji používají skutečné čtečky i všechny běžné zápisy grafu.
Původní draft řádek zůstane zachovaný, ale není náhradním zdrojem při chybě.
Git/file graf se takto automaticky nepřevezme; vyžaduje stávající přijetí grafu.
Registry projektů a workspaces mají samostatný monotónní fence: každá změna
relevantní identity, metadat či lifecycle zvýší generaci zaregistrované vazby.
Přesun, smazání a opětovné vložení se tím neztratí při A→B→A. Archivované
projekty/workspaces jsou nezpůsobilé. Jiný projekt nesmí zneplatnit tuto vazbu.

Fence není obecný activity journal ani společná transakce registry/Git/SQLite.
SQLite triggery a jejich schéma se ověří při každé kontrole. Ztráta pokrytí,
změna DDL generace, pokles či zmizení fence znamenají odmítnutí. Pin zachová
generaci a skutečnou identitu zdrojů; příprava/claim/validace ověří binding
před a po práci. Chrání standardní i přímé SQL writery, nikoli škodlivého
vlastníka databáze nebo procesu stejného OS.

## Heartbeat a výsledek

`active()` pro context-v2 ověří původní pin, registry fence, každou přijatou
mezirevizi a každý živý SQL přechod. Použije původní assignment a rozpočet;
nezmění rodinu, allocation, origin, epochu, pokus ani deadline. Lease a rozpočet
se ověří i po dražší validaci. Uloží se samostatný poslední doklad kontroly,
nikoli nový výchozí kontext. Doklad obsahuje kontrolovanou aktuální hlavu,
nikoli raw digest nebo snímek. Související změna nebo nedostupný doklad odmítne.

Autentizovaný přesný replay claimu/výsledku zachová existující pořadí a historii.
První nový výsledek a heartbeat vrátí verzi kontextu a oddělený doklad validace.
V1 nepřijme nové neznámé fields a nezmění chování kvůli novému režimu.

Připravený projekt má také SQL ochranu ukazatele přijaté hlavy: dovolí pouze
postup na scoped child revizi, nikoli rewind, delete/reinsert, REPLACE nebo
přesun identity. Starší projekt bez přípravy v2 tento nový guard neaktivuje.
Migrace kopíruje refy před klíči a zachová existující historii; nepovoluje tím
reaktivaci původního oprávnění po změně generace databáze.

## Office a důkazy dokončení

Office požádá o v2 jen výslovnou volbou dispatch. Uloží verzi, origin assignment
a jeho digest; restart nesmí přepnout na v1. Sparse dispatch nepřipojí dynamické
`prepareTask` ani `withReaBrief` vstupy mimo zachycené zadání. Stávající v1 cesta
zůstane zachovaná. Statická instrukce vykonavatele je označená vlastní verzí.

Dokončení vyžaduje claim→nesouvisející přijetí/živá změna→heartbeat→výsledek,
relevantní accepted/live/registry ABA, archivaci, reopen, rollback, restore,
identity/token/replay a rozpočtové kombinace. Office musí projít proti skutečnému
HTTP Canvas API. Dokumentace dostupnosti se změní až po těchto důkazech.

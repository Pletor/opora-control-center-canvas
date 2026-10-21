# Omezení oprávnění běhů agentů

Tento kontrakt rozšiřuje verzované zadání a execution lease. Canvas rozhoduje,
kolik běhů smí pro konkrétní přijaté zadání vzniknout a do kdy smí zapisovat.
Office při ztrátě oprávnění zastavuje pracovníka existujícím stop adaptérem.
Jde o omezení oprávnění a počet spuštění; není to garantované zastavení všech
potomků procesu, limit účtu poskytovatele ani peněžní či tokenový rozpočet.
Windows ConPTY dnes nemá prokázanou izolaci celého procesového stromu.

## Identita a trvalost

- Rodina je přesná trojice `(workspace, nodeId, acceptedRevision)` v projektové DB.
  Vlastník, request ID, restart, epocha ani změna pravidel ji nenahrazují.
- Člověk zapíše neměnnou revizi pravidel pro kartu a aktuální přijatou revizi.
  `maxRunSeconds` je celé číslo 30–86400, `maxAttempts` 1–100 a
  `maxRepairRounds` 0–99, nejvýše `maxAttempts - 1`. Žádné neznámé položky.
- Hlava pravidel je pro kartu a prostor, nikoli jen rodinu. Zápis používá
  `expectedPolicyHead`, `expectedAcceptedHead` a stabilní `requestId`.
  Přesné opakování vrátí původní zápis; změněný obsah stejného ID je konflikt.
- Revize pravidel ukládá rodiče, lidského autora, čas, scope a přesné limity.
  Agent ani chybějící UI relace nesmějí pravidla měnit nebo rušit.
- První nastavení trvale zařadí kartu. Neexistuje návrat k neomezenému v1 claimu.
  Po přijetí nové revize plánu je nutné lidské nastavení pravidel nové rodiny.
  Předchozí rodina, výdaje a běhy zůstávají v historii.
- První nastavení nesmí obejít již běžící oprávnění: vyžaduje uvolnění nebo
  expiraci aktuálního lease. Starší běhy stejné rodiny se vloží do účetní knihy
  jako již spotřebované pokusy; import ověřuje úplné záznamy a nepoužívá limit100.
  Jejich neznámý starý časový limit se zpětně nevymýšlí.
- Každé nové přijetí běhu spotřebuje jeden pokus ihned a nevratně. Uvolnění,
  neúspěšné spuštění, zrušení, timeout ani chybějící výsledek nic nevracejí.
  Transakce, která nebyla commitnuta, nespotřebuje nic.
- První běh je `initial`, další `retry`; od prvního nahlášeného výsledku rodiny
  je každý další běh `repair` a spotřebuje také opravné kolo. Klasifikaci určuje
  server z trvalé historie, nikoli označení od agenta. Není přidána automatická
  smyčka oprav. Nový claim musí uvést přesné ID posledního běhu rodiny, první null.
- Zvýšení limitu je nová lidská revize a nezmenšuje již spotřebované počty.
  Snížení pod spotřebované počty je dovolené a nepovoluje další spuštění.

## Admission a oprávnění

- Kontext zachovává stávající pole a přidává `executionProtocolVersion` a
  `budget`: enrollment, policy head, policy pro aktuální přijatou revizi,
  počty/zbývající kapacity, poslední execution ID a důvod blokování.
- Nezařazená karta zachovává přesný v1 protokol. V2 claim přidává
  `expectedBudgetPolicyHead` a `previousExecutionId`; žádné caller-supplied limity.
  Zařazená karta odmítne v1 i chybějící/neaktuální pravidla. Výslovný v2 požadavek
  nikdy tiše nepřejde na v1. Přesný commitnutý claim replay se vyřídí před novým
  přidělováním, ale nezíská nové oprávnění, pokud původní záznam již není aktivní.
- Jediná `BEGIN IMMEDIATE` transakce ověří plán/kontext, policy CAS, poslední běh,
  volnou kapacitu a lease, přidělí pořadí pokusu/opravy, epochu, token a immutable
  zadání. Samostatné SQLite connection nesmějí spotřebovat poslední místo dvakrát.
- V2 execution nese `executionProtocolVersion: 2` a neměnné `budget`:
  `policyHead`, `familyId`, `allocationId`, `attempt`, `repairRound`, `kind`,
  `admittedAt`, `runDeadlineAt`, `maxRunSeconds`. Časy jsou server UTC epoch seconds.
  Snapshot pravidel je uložen s alokací. Identita rodiny/pořadí má DB unique guards.
- `runDeadlineAt = admittedAt + maxRunSeconds`, po pomalém zachycení zadání.
  Lease končí nejpozději v tomto čase. Heartbeat mění jen liveness;
  expiraci nastaví na `min(now + ttlSeconds, runDeadlineAt)`.
- Kontrola skutečného serverového času běží před i po zachycení kontextu a před
  renew/result zápisem. Rovnost s deadline již znamená konec oprávnění.
  Změna policy nikdy neposouvá deadline již přijatého běhu.
- Trvalý časový high-water pro budget autoritu odhalí pozorovaný návrat hodin.
  Takový běh se neobnoví a nový claim/heartbeat/result je konflikt; čtení historie
  a lidské zrušení musí zůstat možné. UTC vyžaduje důvěryhodné hodiny serveru;
  návrat hodin, který server nikdy nepozoroval, není tímto prokázán ani vyloučen.
  Freeze je pro celou projektovou DB, netýká se nezařazených v1 karet a v této
  etapě nemá reset API. Při incidentu lze rušit běhy a číst historii; správce
  musí vyšetřit hodiny. Mazání clock/ledger tabulek není podporovaná obnova.
- Člověk může zrušit konkrétní běh s CAS epochy a stabilním request ID. Zrušení
  a odebrání pouze odpovídajícího tokenu lease jsou jedna transakce. Starý běh
  nesmí zrušit novější rezervaci. Zrušení nemění již uložený reported receipt.
- Přesné opakování commitnutého výsledku vrací původní receipt i po timeoutu
  nebo zrušení; nový/změněný pozdní výsledek se odmítne. Nic zde nepotvrzuje kartu,
  nepřijímá plán, neschvaluje review, nemerguje a nenasazuje kód.

## Office a pozorovatelné hranice

- Office vybere protokol podle contextu, zachová jeden request při nejisté síti
  a po odmítnutí v2 nikdy nezkouší v1 ani nový claim při automatickém restore.
- V2 DTO validuje přesná neměnná budget pole a jejich shodu na heartbeat/restore.
  Původní policy, allocation, attempt, deadline i assignment se drží v privátní
  capability; UI a helper nesmějí zveřejnit token.
- Lokální monotónní watchdog účtuje dobu požadavku a končí nejpozději na menším
  z lease a původního run deadline. Úspěšný, neúspěšný i zaseknutý heartbeat ani
  změna systémových hodin klienta nesmějí tento původní lokální strop prodloužit.
- Launch/resume/restore projdou dosavadním společným guardem. Odpojení a restart
  spotřebovávají čas původního běhu. Office při budgeted shutdown vyžádá stop;
  nesmí budgeted worker ponechat v hostu jako obecné `keep`.
- Stop požadavek není důkaz výstupu všech procesů. UI/docs rozlišují odebrané
  oprávnění, žádost o zastavení a výsledek stop adaptéru. Žádný hard process-tree,
  dolarový nebo tokenový limit se neprezentuje jako podporovaný.

## API a rozhraní

- Vlastní backend modul + router `/api/oporahub/execution-budgets`:
  GET context a GET `/history` mají `project`, `workspace`, `nodeId`;
  POST nastaví pravidla s výše uvedeným CAS a třemi limity.
  POST `/{executionId}/cancel` má scope, `epoch`, `requestId` a vyžaduje člověka.
  POST pravidel má přesně `project`, `workspace`, `nodeId`, `expectedPolicyHead`,
  `expectedAcceptedHead`, `requestId` a `limits: {maxRunSeconds, maxAttempts,
  maxRepairRounds}`. `limits` je objekt, nikoli další pole v kořeni požadavku.
- Kontext obsahuje lidské `canConfigure`/`unavailableReason`, aktuální policy,
  rodinu a omezenou historii. Read-only/archiv nesmí konfigurovat ani spouštět;
  historii a zrušení již běžícího oprávnění lze číst/provést i po archivaci.
- Nový frontend dílek OporaHubu zobrazuje výběr karty, aktuální pravidla,
  spotřebované pokusy/opravy, zbývající kapacitu, přesný limit oprávnění a historii.
  Aktivace/změna vyžaduje kontrolu snapshotu a výslovné potvrzení. Změna karty,
  prostoru, přijatého plánu nebo policy ruší rozepsané potvrzení. Žádné automatické
  opakování mutace; stabilní ID stejného potvrzeného úmyslu přežije nejistou odpověď.
- Execution historie ukáže budget a umožní lidské zrušení. Nezobrazuje skrytý
  token. Staré v1 záznamy se označí bez pevného časového limitu.
- Nové tabulky se připojí do schema/archive/restore paths. Staré zálohy nesmějí
  vymazat enrollment, policy, spotřebu, cancel nebo clock high-water ani doplnit
  další pokusy. Migrace je aditivní; staré execution záznamy se nepřepisují.

## Důkazy před dodáním této etapy

1. Skutečná factory/schema/human middleware: agent spoof odmítnut, policy CAS,
   přesný replay a změněný replay, read-only a archiv, žádný v1 downgrade.
2. Poslední slot přes dvě DB connection, transakční rollback, první/retry/repair,
   žádné vracení pokusů přes release/timeout/změnu vlastníka nebo policy.
3. Deadline před/na/po hranici, pomalý capture přes deadline, heartbeat cap,
   starý receipt replay, zrušení proti submit/takeover a restart/high-water.
4. Office fake-clock proof pro všechny heartbeat výsledky i restore a původní
   immutable pole; skutečný HTTP smoke Office klienta proti Canvasu v2.
5. Browser nastavení → potvrzení → historie/kapacita → zrušení; bez JS chyb,
   screenshot. README a odpovídající docs aktualizovány v obou PR.
6. Root backend/database, frontend testy + produkční build; Office typecheck,
   testy včetně size a build. Známé selhání původního Graphify se hlásí odděleně.

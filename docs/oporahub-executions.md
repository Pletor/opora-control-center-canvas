# Vykonávání přijatého zadání

Canvas rozhoduje, který běh smí odevzdat výsledek. Agent-office spouští pracovníka
a hlídá jeho oprávnění. GitHub uchovává změny kódu a jejich review. Převzetí karty
není schválení změny, odevzdání výsledku není nezávislé ověření ani dokončení karty.

## Převzetí a neměnné zadání

Karta musí patřit do zapisovatelného workspace s přijatou revizí zadání. Její
relevantní zadání i zadání souvisejících karet musí odpovídat přijaté verzi.
Uzavřenou kartu ani kartu blokovanou předchůdcem nelze převzít. Pracovní návrh
nejprve přijměte v OporaHubu; pracovník nesmí automaticky přijmout vlastní změnu.

Převzetí zachytí přijatou revizi a kontext zadání v neměnném snímku. Pracovník
pracuje z tohoto snímku, nikoli z opakovaně načítaného živého briefu. Zachycení
kontextu nezahrnuje obsah externích odkazů ani bajty obrázků; jejich neměnnost
tato verze nezaručuje.

Jediným zdrojem rezervace zůstává `card_leases`. V téže SQLite transakci se uloží
běh, snímek, klíč požadavku a rostoucí číslo převzetí (`epoch`). Číslo se po
uvolnění ani expiraci nevrací zpět. Platí dosavadní limit karet na vlastníka.

## Ztráta oprávnění

Heartbeat i první odevzdání ověřují aktuální rezervaci, token, epochu, expiraci,
přijatou revizi a kontext. Změna zadání nebo kontextu vyžaduje nové převzetí.
Uvolnění člověkem také zneplatní běh, i když jeho proces ještě běží.
Opožděné uvolnění starého běhu nesmí smazat rezervaci jeho nástupce.

Agent-office počítá zbývající čas z času serveru a monotónních hodin. Při výpadku
sítě může obnovu opakovat pouze do již známého termínu. Výslovné odmítnutí nebo
vypršení termínu pracovníka zastaví; jeho worktree zůstane k prohlídce.
Restart kanceláře vyžaduje opětovné ověření původního běhu. Starý uložený pracovník
bez tohoto oprávnění se automaticky nepřevede na nové převzetí.

Zařazení karty do nového protokolu je trvalé. Starší agentí zápisy jejího stavu
se odmítají i po expiraci rezervace; nestačí obejít nový endpoint. Člověk může
nadále provádět výslovné změny. Úpravy pracovního obsahu zůstávají oddělené od
potvrzení dokončení; změna kontextu zneplatní původní běh při další kontrole.

Totéž platí pro starší procesy připojené ke kartě: agent nesmí obejít ochranu
zápisem procesního výsledku nebo hotového kroku. Tyto procesy nemají vlastní
workspace, proto kontrola hledá zařazení karty v kterémkoli workspace projektu.
Výslovnou lidskou změnu určuje session, nikoli pole `by` v těle požadavku.
Starší procesní soubory zůstávají historií; jejich zápis není společně s databází
odolný proti pádu procesu a nenahrazuje nové execution potvrzení.

## Odevzdání a opakované požadavky

Výsledek je omezený JSON objekt s neprázdným `summary` (nejvýše 64 000 bajtů).
Server atomicky uloží potvrzení o přijetí, uzavře běh a uvolní rezervaci.
Stejný klíč a stejný obsah vrátí stejné potvrzení i při opakování po expiraci.
Jiný obsah pod stejným klíčem se odmítne. Nové odevzdání do uzavřeného běhu
neprojde. Odevzdané tvrzení ani odkaz na artefakt se automaticky nespouští.

Historie v OporaHubu umožňuje dohledat běh a jeho odevzdané výsledky. Token
nepatří do historie, veřejného stavu kanceláře, promptu, logů ani GitHubu.
Kancelář ho uchovává v soukromém souboru pro pomocný program odesílající výsledek;
pracovník čte samostatný soubor zadání.

## API

Prefix všech cest je `/api/oporahub/executions`. Zapisující požadavky vyžadují
identitu z middleware. `project` a `workspace` jsou vždy výslovné; změna aktuálně
zvoleného projektu v kanceláři nepřesměruje existující běh.

| Cesta | Účel |
|---|---|
| `GET /context?project&workspace&nodeId` | Dostupnost, přijatá revize a verze kontextu |
| `POST /claim` | Scope, karta, očekávaná revize/kontext, `requestId`, `ttlSeconds` |
| `GET /{id}/assignment?project&workspace` | Neměnné zadání; token v `X-Opora-Execution-Token` |
| `POST /{id}/heartbeat` | Scope, token, epocha a nové TTL |
| `POST /{id}/release` | Scope, token a epocha; uvolnění vlastního běhu |
| `POST /{id}/results` | Scope, token, epocha, `requestId` a `result` |
| `GET /?project&workspace` (volitelně `nodeId`) | Nejvýše 100 souhrnů běhů bez tokenů; bez filtru také běhy odstraněných karet |
| `GET /{id}/results?project&workspace` | Odevzdané výsledky konkrétního běhu |

TTL je celé číslo 30–3600 sekund. Chybějící identita vrací 428; konflikt
oprávnění nebo zastaralé očekávání 409. Token je oprávnění konkrétního běhu,
nikoli doklad nezávislé identity člověka. Lokální session není ochrana proti
úmyslnému napodobení identity jiným procesem stejného uživatele systému.

## Zavedení a omezení

Má-li přijatá revize manifest grafu, nové převzetí vyžaduje shodu pracovního
sémantického grafu s manifestem. Rozložení na plátně samo práci neblokuje;
neschválená změna struktury ji blokuje i mimo přebíranou kartu. Starší revize bez
manifestu zachovávají původní kontrolu zadání. Podrobnosti: [návrhy grafu](oporahub-graph-proposals.md).

Obnova zálohy migrace architektury je po uložení návrhu grafu, přijetí plánu, zařazení do řízeného vykonávání nebo
zavedení databázové autority grafu odmítnuta: stará záloha nesmí obnovit zaniklé
oprávnění ani odstranit přijatou historii. Běžná obnova pracovní verze plátna
nevrací přijatou revizi ani historii vykonávání.

Nové tabulky se přidávají bez mazání původních rezervací a historie. Nasazení
Canvasu musí předcházet zapnutí nového vykonavatele; kancelář při chybějícím API
odmítne převzetí. Nevytváří náhradní rezervaci starým protokolem.
Zálohujte databázi před nasazením. Návrat na starý server by odstranil kontrolu
trvalého zařazení karet, proto před takovým návratem zastavte dotčené vykonavatele.

Volitelná lidská [pravidla běhů](oporahub-execution-budgets.md) omezují počet
pokusů i opravných kol a dávají každému běhu pevný konec oprávnění. Jejich v2
protokol se po zařazení karty nedá obejít v1 claimem; nová přijatá revize vyžaduje
nové lidské nastavení. Nezařazené karty zachovávají výše uvedené v1 lease.
Tato vrstva neurčuje rozpočet peněz ani tokenů, neověřuje artefakty a nepotvrzuje
nasazení. Stop adaptér Office není izolace celého procesového stromu. Bez v2
pravidel je heartbeat krátkodobé oprávnění, nikoli celkový časový limit úkolu.
Atomické databázové přechody
nenahrazují distribuovanou transakci mezi Canvasem, GitHubem a procesem agenta.
Provoz předpokládá jeden serverový proces Canvasu: zámky grafu a souborů nejsou
sdílené mezi procesy. Test souběžných převzetí se dvěma SQLite spojeními dokládá
databázové rozhodování o rezervaci, nikoli bezpečnost souběžných změn grafu
z několika serverových procesů.

## Pozorování běhů

OporaHub může navíc číst nejvýše 100 neměnných záznamů z API poskytovatele doložených brokerem přes GET /api/oporahub/execution-observers?project&workspace&limit=100. Čtení vyžaduje identifikovaného člověka nebo agenta a přesný scope projektu i workspace; browser používá UI session. Zobrazení je samostatné od běžné execution historie: intent svazuje neměnnou revizi, commit, agenta a prostředí s původním execution; doložené čtení session nese poslední kumulativní tokeny, aktivní sekundy a ceníkovou spotřebu.

Nezkonfigurovaný pozorovatel, nakonfigurovaný ale neověřený provider přístup, prázdná historie a chyba čtení jsou odlišné stavy. Samotná konfigurace nepředstavuje přístup poskytovatele. Zobrazená ceníková spotřeba pochází z čtení brokera přes API poskytovatele, nikoli z faktury nebo tvrdého limitu. Sentinelské nuly bez ID session a provider statusu se nezobrazují jako nulová spotřeba. Stav idle znamená pouze nečinný provider readback; ukončení ukazuje jen odpovídající provider readback terminated. Ani opožděná spotřeba nemění platnost lease nebo povolení běhu. UI nic nespouští, nezastavuje ani neobnovuje automaticky.

## Uzavření smyčky: běh → PR → merge → plán

Po odevzdání běhu se k němu připojí právě jedno PR. Backend pak bez modelu a bez
ručního přepojování sám zapne trvalé sledování PR, zapíše merge nebo zavření bez
merge a označí kartu k lidskému uzavření. Zadání karty (`goal`, `non_goals`,
`acceptance`) se nikdy nemění.

| Cesta | Účel |
|---|---|
| `POST /{id}/pull-request` | `project`, `workspace` (nebo `projectId`, `workspaceId`), `requestId`, `repository` (`owner/name`), `number`, `headRef`, `headSha`; agent navíc `token` a `epoch` |
| `GET /{id}/pull-request?project&workspace` | Stejný tvar jako odpověď zápisu, navíc `events`; bez vazby 404 |

Odpověď obsahuje `executionId`, `cardId`, `acceptedRevision`, `repository`, `number`,
`headSha`, `state` (`open` / `merged` / `closed`), `bindingId` a provozní údaje
`enrollment`, `mergeSha`, `awaitingHumanClose` a `attention`.

Oprávnění: agent se prokazuje tokenem a epochou **tohoto** běhu, stejně jako
u heartbeatu a výsledků. Platí aktivní rezervace běžícího běhu, nebo běh, který
už odevzdal výsledek – kancelář PR připojuje po odevzdání, často po uvolnění
rezervace. Jiná epocha, token jiného běhu a běh bez rezervace i bez výsledku
(uvolněný, vypršelý) vrací 409. Člověk připojuje přes session bez tokenu.
Běh musí patřit k existující přijaté revizi a repozitář musí odpovídat projektu.

Opakování: stejné `requestId` se stejným obsahem vrátí stav bez další akce, jiný
obsah pod stejným `requestId` je 409. Totéž PR s novým `headSha` a novým
`requestId` jen aktualizuje SHA. Jiné PR (číslo nebo repozitář) pro běh, který
už vazbu má, je 409.

**Automatické zapnutí sledování.** Po uložení vazby server mimo zámky jednou
přečte GitHub (GET) kvůli číselné identitě repozitáře a PR a v jedné transakci
vytvoří vazbu [trvalého sledování](oporahub-reconciliation.md) pro přijatou
revizi běhu a aktuální SHA (`by: system / Execution PR link`, řízení
`auto-enroll`). Existuje-li už zapnuté sledování téhož PR, použije se. Tato cesta
nepřijímá plán ani review; lidské brány přijetí zůstávají. Při výpadku GitHubu
zůstane `enrollment: pending` a smyčka zkouší znovu s rostoucím odstupem (30 s
až 1 h). Bez GitHub repozitáře v projektu je `enrollment: unavailable`
a GitHub se nečte vůbec.

**Zápis výsledku.** Smyčka uzavření (vedle pracovníka sledování) čte neměnná
pozorování vazby. Mergnuté PR zapíše jednou událost `execution.merged`
(`mergeSha`, `prNumber`, klíč běh + merge SHA), vazbu označí `merged`, ještě
běžící běh ukončí stavem `released` (uvolní rezervaci) a nastaví
`awaitingHumanClose: true`. Potvrzení `done.confirmed` karty totiž podle
[kontraktu karty](karta-pro-agenty.md) zapisuje jen člověk s doloženými důkazy;
značka zmizí, jakmile člověk kartu uzavře. Zavření bez merge zapíše
`execution.pr_closed` a `attention: pr-closed-unmerged`; znovuotevření značku
zruší a další zavření je nová událost. Opakované čtení, restart ani souběh
nevytvoří druhou událost.

**Objevení podle trailerů.** Bez ručního volání API smyčka najde PR, jehož popis
obsahuje přesně jednu dvojici řádků:

```text
Opora-Execution: <executionId>
Opora-Revision: <acceptedRevision>
```

Čte jednu stránku (20) naposledy změněných PR repozitáře projektu, jen pokud
projekt má GitHub repozitář a nepřipojený běh. Revize, repozitář a cílová větev
musí odpovídat; nejednoznačný trailer se ignoruje. Výsledek je stejná vazba
(`source: discovery`) včetně automatického sledování.

Konfigurace prostředí: `OPORA_EXECUTION_PR_WORKER=0` smyčku vypne,
`OPORA_EXECUTION_PR_DISCOVERY_SECONDS` mění interval objevování na projekt
(výchozí 300, `0` vypne). Rate limit GitHubu zastaví další čtení do uvedeného
času. Pro další služby (např. stav agentů) slouží čtecí funkce
`list_execution_pull_requests(project_id, workspace_id)`: seznam vazeb se stejnými
poli včetně `mergeSha` a `planWrittenBack` (merge byl do běhu a karty zapsán).

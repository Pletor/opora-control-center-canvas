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
| `GET /?project&workspace&nodeId` | Nejvýše 100 souhrnů běhů bez tokenů |
| `GET /{id}/results?project&workspace` | Odevzdané výsledky konkrétního běhu |

TTL je celé číslo 30–3600 sekund. Chybějící identita vrací 428; konflikt
oprávnění nebo zastaralé očekávání 409. Token je oprávnění konkrétního běhu,
nikoli doklad nezávislé identity člověka. Lokální session není ochrana proti
úmyslnému napodobení identity jiným procesem stejného uživatele systému.

## Zavedení a omezení

Nové tabulky se přidávají bez mazání původních rezervací a historie. Nasazení
Canvasu musí předcházet zapnutí nového vykonavatele; kancelář při chybějícím API
odmítne převzetí. Nevytváří náhradní rezervaci starým protokolem.
Zálohujte databázi před nasazením. Návrat na starý server by odstranil kontrolu
trvalého zařazení karet, proto před takovým návratem zastavte dotčené vykonavatele.

Tato vrstva zatím neurčuje rozpočet peněz ani celkový počet opravných kol,
neověřuje artefakty a nesynchronizuje merge či nasazení. Heartbeat je krátkodobé
oprávnění, nikoli celkový časový rozpočet úkolu. Atomické databázové přechody
nenahrazují distribuovanou transakci mezi Canvasem, GitHubem a procesem agenta.
Provoz předpokládá jeden serverový proces Canvasu: zámky grafu a souborů nejsou
sdílené mezi procesy. Test souběžných převzetí se dvěma SQLite spojeními dokládá
databázové rozhodování o rezervaci, nikoli bezpečnost souběžných změn grafu
z několika serverových procesů.

# Verzovaný obsah plánu — implementační kontrakt 2b

Implementace etapy rozšiřuje přijaté revize o texty, scény kreseb a konfiguraci
zadání karet; výsledky dokončeného ověření jsou uvedeny níže. Navazuje na [grafové návrhy](oporahub-graph-changes.md)
a [kontext execution](oporahub-sparse-context.md). Nezahrnuje komentáře/rizikové
schvalování ani izolaci/účtování zbývajících etap.

## Model a rozsah

Samostatné neměnné `content-proposal` a `content-manifest` mají scope projektu
a workspace, content-addressed ID a omezený JSON. Přijatá revize získá volitelný
`contentManifestId`; starší revize bez něj zůstanou čitelné. Každé spec/graph
přijetí dosavadní obsahový manifest zachová. Historie odstraněných karet se nemaže.

Manifest má schéma1 a seřazené položky s klíčem `kind`, `target`, `field`,
`ownerWorkspace`, hodnotou `value` a revizí zdroje u textu/kresby. `kind` je
`text`, `drawing` nebo `config`. Text vlastní `document_workspace`; kresba je
vrstva workspace (kořen má target prázdný). Config má samostatná pole `actions`,
`rules`, `blocks`, `materials`, `downloadsUrl`. První čtyři pole vyžadují pole
včetně `[]`. Poslední pole je příznak boolean „Úloha stahuje URL“, nikoli adresa;
nepřítomný příznak se vyjádří null.
Platí původní podmínky bezpečnostního bloku pro vstupy. Blocks se normalizují stejně jako `_instructions`, bez pracovních
status/note/todo.done. Round zůstává precondition, mění jej jen existující human
operace otevření kola. GateNodeId a scenario už verzují grafové návrhy.

První návrh zachytí úplný obsah existujících uzlů a kořenovou kresbu jako základ.
Přijetí musí potvrdit `adoptBaseContentDigest`; nesmí bez upozornění přijmout jen
viditelný patch a ostatní obsah prohlásit za schválený. Při prvním přijetí se
základ znovu celý porovná. Další návrhy pracují s konkrétními položkami; nemění
nesouvisející pracovní obsah. Manifest nejvýše16384 položek/8MiB, návrh nejvýše
128 změn/12MiB, projekt nejvýše128MiB neměnných nových záznamů; odmítnutí nic
nezkrátí ani nesmaže. Obrázkové bajty a externí reference zůstávají mimo manifest.
Text má nejvýše 64000 znaků; scéna zachovává native omezení kresby. HTTP tělo
na těchto cestách má samostatný limit 12 MiB včetně streamovaného těla (`413`).
ID používá stejný `content_id` jako ostatní changesety: 40 hex znaků z SHA256
kanonického JSON. Čtení kontroluje ID, scope i typový formát, kvóty nic nemažou.

## API, rozdíl a konflikty

Samostatný router `/api/oporahub/content-changes`: GET list/detail, POST návrh,
POST `/{id}/rebase`, POST `/{id}/accept`. Návrh může vytvořit agent/člověk, přijetí
jen člověk. Create přijme přesně project/workspace/expectedAcceptedHead/subject/
changes; změna má `kind`, `target`, `field`, `value`. Text field=`text`, kresba
field=`scene`, config field z allowlistu výše. Explicitní stejná hodnota je
přípustná pro přijetí pracovního obsahu, který se liší od dřívějšího přijatého.

Záznam nese rodiče, graph digest, supersedes, zdrojové owner/revision/round,
pozorované `before`, přijaté `acceptedBefore` a požadované `value`. Diff rozlišuje
přijatý obsah, pracovní stav a návrh. Create/rebase nikdy nepíše native obsah.
Rebase na novou hlavu smí přenést nezměněné položky; souběžná změna stejné položky,
owneru nebo kola je explicitní konflikt, původní návrh zůstane. Konfliktní rebase
nic nepřijme ani nepřepíše. Nezávislé změny různých config polí lze přenést.

Accept přijme project/workspace/expectedAcceptedHead/reviewedProposalId/
adoptBaseContentDigest. Vyžaduje přesné neměnné ID, rodiče, přijaté preconditions
a native zdrojové preconditions. V jedné BEGIN IMMEDIATE transakci zapíše native
historii, nový manifest, přijatou revizi kind=`acceptance` a CAS hlavu. Nepřidá
druhý lease. Replay přijetí stejného návrhu vrátí stejnou revizi. Chyba rollbackne
i SQL journal. Konfigurace se sloučí do nejnovějšího stavu; pracovní statusy,
done/scenarioRun, kola a nesouvisející záznamy se návrhem nepřepisují. Nové bloky
mají neutrální pracovní stav; neplatné/dangling řídicí reference se odmítnou.
U potvrzené uzavřené karty nelze touto cestou změnit bloky ani porty; nejprve ji
otevřete existující lidskou operací. Přijetí nezmění potvrzení dokončení ani číslo
kola. Konfigurace `downloadsUrl: true` dál vyžaduje původní bezpečnostní blok pro
nedůvěryhodné vstupy. Návrh tuto podmínku neobchází.

### Přesný postup pro agenta a člověka

1. S identitou načtěte `GET /api/oporahub/content-changes?project=<id>&workspace=<id>`.
   Odpověď má nejvýše 100 `items`, `acceptedHead`, `contentManifestId`, `readOnly`
   a `canAccept`. Agent posílá `X-Opora-Actor: agent; name=<jméno>`; prohlížeč
   získá lidskou session přes `GET /api/access/ui-session`. Identita není pole JSON.
2. Na existující přijatou hlavu pošlete následující přesné tělo na
   `POST /api/oporahub/content-changes`:

   ```json
   {
     "project": "projekt",
     "workspace": "draft",
     "expectedAcceptedHead": "<acceptedHead z načtené odpovědi>",
     "subject": "Upřesnění pracovního postupu",
     "changes": [
       {"kind": "text", "target": "karta", "field": "text", "value": "Nový text"},
       {"kind": "drawing", "target": "", "field": "scene", "value": {"elements": []}},
       {"kind": "config", "target": "karta", "field": "rules", "value": []}
     ]
   }
   ```

   Odpověď je úplný neměnný návrh. Native owner, revize, kolo a obě původní hodnoty
   zachytí server; klient je nedodává ani nemění uložením návrhu pracovní obsah.
3. Člověk otevře **Změny obsahu → Otevřít změny obsahu** v OporaHubu a vybere přesný
   návrh. `GET /api/oporahub/content-changes/{id}?project=<id>&workspace=<id>` vrací
   `proposal`, `accepted` (ID přijaté revize nebo null), `acceptedHead`, `readOnly`
   a `canAccept`. Detail ukáže tři hodnoty i owner/revision/round a úplný JSON ke stažení.
4. Zastaralý návrh se výslovně převede přes
   `POST /api/oporahub/content-changes/{id}/rebase` s přesně
   `{project, workspace, expectedAcceptedHead}`. Úspěch vrací `rebased: true`, nový
   `proposal` a prázdné `conflicts`. Konflikt vrací `rebased: false`, `proposal: null`
   a položky `{kind, target, field, reason}`; původní návrh zůstává beze změny.
5. Po kontrole pošle pouze člověk `POST /api/oporahub/content-changes/{id}/accept`:

   ```json
   {
     "project": "projekt",
     "workspace": "draft",
     "expectedAcceptedHead": "<aktuální acceptedHead>",
     "reviewedProposalId": "<přesné ID zkontrolovaného návrhu>",
     "adoptBaseContentDigest": "<baseContentDigest prvního návrhu; jinak null>"
   }
   ```

   První přijetí v UI vyžaduje samostatné potvrzení celého výchozího obsahu s jeho
   otiskem. Jeho zavedení může zneplatnit běžící úlohy nad revizí bez manifestu.
   Výsledkem je přijatá revize s `contentManifestId`. Nejistý zápis UI automaticky
   neopakuje. Změněný základ vrací `409`; chybějící identita `428`.

## Upgrade projektu s dřívějším kontextem v2

Přidání `CONTENT_SCHEMA` do databáze, která již má aktivované sparse SQL pokrytí
z předchozí verze, změní `PRAGMA schema_version`. Dřív se proto původní v2
checkpoint odmítl jako změněná generace DDL. Teď aplikace každé své DDL dosvědčí
jako generaci (`database/repositories/schema_generations.py`) a pin přes souvislý
řetězec od své verze projde; otisky schématu a triggerů se dál porovnávají beze
změny. Staré události, coverage metadata, klíče, soukromé piny a přijatá historie
zůstávají beze změny. DDL mimo aplikaci nechá mezeru a pin dál odmítne; opakovaná
příprava coverage ji neopraví ani znovu nezařadí. Mezeru, kterou aplikace
neviděla (DDL starší verze po zápisu pinu, cizí DDL), lze přijmout jen výslovnou adopcí `tools/schema_adopt.py` s pravdivým autorem a důvodem;
přidá jeden řádek generace, nic nepřepisuje ani nemaže a bez `--write` jen ukáže,
zda by checkpointy prošly. Samotné `--db` vypíše stav: verzi teď, piny, celý
řetězec (kdo, kdy, proč), mezeru a přesný příkaz, který by ji uznal. Odmítnutý
pin říká totéž přímo ve zprávě chyby.

Běžný kontext v1 zůstává použitelný při splnění jeho dosavadních podmínek.
Tato verze nemá reset pro obnovení dřívější v2 coverage; nepřepisujte
fingerprinty, piny ani zapsané generace a nemažte důkazy pro obnovení běhu.
Jde o záměrné odmítnutí nedoložené kontinuity, které vyplývá z
[pravidel SQL pokrytí](oporahub-sparse-context.md). Nové projekty se zařazují
až po instalaci úplného schématu.

## Execution, historie a UI

Čtení přijaté revize ověří hash/scope manifestu. Lineage porovná jeho vybrané
položky v každé mezirevizi, včetně absence položek. Claim ověří aktuální pracovní
obsah vybraných položek proti přijatému manifestu před redakcí. Relevantní změna
odvolá původní execution; nesouvisející položky jiných karet jej nepřepnou na nové
zadání. Živé SQL přechody nadále ověřuje existující journal. Legacy revize bez
manifestu nepředstírá schválení textu/kresby/config.
Stejný výběr přijatého obsahu se před claimem kontroluje v kontextu v1 i v2.
V2 navíc porovná vybrané položky v každé přijaté mezirevizi. Nesouvisející změna
jiné karty tak může projít, relevantní změna i návrat A→B→A původní běh zneplatní.
Revize bez pole `contentManifestId` zůstávají čitelné s původní legacy sémantikou;
odkaz na chybějící nebo poškozený manifest se odmítne. Jakmile manifest existuje,
nová karta, kterou manifest vůbec nezná (přidaná návrhem grafu, který manifest jen
převezme), je přijatá jen v nativní prázdné podobě: prázdný text, prázdná kresba
a výchozí konfigurace, tedy totéž, co úplné přijetí nové karty zapíše. Jakýkoli
neschválený obsah navíc (text, kresba, konfigurace) ji drží nedostupnou do výslovného
obsahového přijetí. Chybějící položky se nedoplňují z živého Canvasu. Agent-state
pak u karty ukáže `claim / blocking / card_unavailable` s důvodem v `detail`.

OporaHub na stejné stránce zobrazí návrhy obsahu. Drawer otevře přesné ID, ukáže
tři hodnoty rozdílu, případnou adopci základu, konflikty a lidské přijetí přes
stejné API. Návrhy se zapojují také do rozhodnutí a aktivity na přehledu. Potvrzení
se ruší při zavření, změně scope nebo ID; stará odpověď jiného scope nenahradí
vybraný návrh. Chybějící API se ukáže jako nedostupné podklady. JSON a scény se
zobrazují jako text, nikoli HTML nebo spustitelný obsah. ✕/Esc vrací přehled.

Tabulky `opora_content_proposals` a `opora_content_manifests` jsou aditivní,
neměnné a zahrnuté do projektových migrací. Obnova staré architektonické zálohy
odmítne přepsat databázi s jakýmkoli uloženým obsahovým záznamem, i osiřelým.
Přijetí drží projektový scope a jednu transakci: chyba vrátí native historii,
obsahový manifest, přijatou hlavu i navázané SQL události před zápis.

## Závěrečné ověření etapy 2b

Etapa 2b (bod 9 checklistu) je dokončena v rozsahu tohoto kontraktu: texty, kresby a konfigurace mají neměnné návrhy, konflikty a explicitní lidské přijetí; přijatý obsah je svázán s manifestem a execution context v2; adopce základu je výslovná. Ověřeny byly dva nezávislé návrhy s přijetím/rebase/přijetím, konflikt stejné položky, owner architektury, zachování pokroku konfigurace, HTTP/browser průchod, související i nesouvisející změny context-v2 a rollback/restore.

Závěrečný backend běh skončil s 3 213 úspěšnými testy, 4 přeskočenými a jedním známým selháním z historického baseline: `test_map_refresh.py:219` očekává "watching", ale prostředí hlásí Graphify jako nedostupné; celý běh trval 1 520,14 s. Samostatný test upgradu databáze prošel (1 test). Frontend sada prošla v počtu 1 567 testů a build i headless-browser ověření proběhly. Sada tedy není zcela zelená kvůli uvedenému známému dluhu; změna ho nepovažuje za novou regresi. Data se nemazají.

# Rozšíření plánu

Samostatný modul OporaHubu pro aditivní návrhy a výslovné změny grafu. App vlastní
`useGraphProposals`; komponenty dostávají stav a callbacky. Strukturovaný formulář
vytváří karty, sektory, oblasti, rodičovské vztahy, zadání a volitelné vazby.
Existující prvky mají reference `@id`. Server vytváří stabilní ID a souřadnice;
klient odvozené hodnoty ani identitu autora neodesílá.

Prázdný Canvas může vytvořit první plán s `parentRevision: null`. První přijetí
vyžaduje kontrolu výchozího grafu a přebíraných zadání a checkbox svázaný s přesným
ID návrhu a otiskem grafu. Obnova, změna prostoru nebo výběru potvrzení ruší.
Převod na nový základ je samostatná akce tvořící nový neměnný návrh; nic se
automaticky nepřijímá ani nepřevádí. Změny existujících zadání zůstávají v sousedním
modulu `plan-changes`.

Historie čte souhrny, detail samostatně celý neměnný návrh. Nedostupný zapisovací
kontext nezakrývá historii. Generace požadavků oddělují prostor, obnovu a výběr;
souběžné mutace blokuje samostatná západka. Před POST se získá lidská session,
ale mutace se neopakuje ani při 428 nebo nejistém síťovém výsledku. Po chybě je
nutné obnovit stav. Po přijetí App obnoví Canvas, zadání i návazné důkazy pouze
pro stále aktivní projekt a prostor. Přijetí používá existující `trackSaveWrite`,
aby správce verzí rozlišil vlastní úspěšný zápis od změn v jiném okně. Nezahazuje
rozepsané změny ani nepotvrzuje předchozí externí změnu.

Veškerý obsah návrhu se vykresluje jako text, nikoli HTML. UI ukazuje ID,
souřadnice, vazby, zdrojové reference a všechna přidávaná/přebíraná zadání.
Přijetí plánu nepotvrzuje implementaci ani dokončení karty. Styl má BEM prefix
`graph-proposals`; čistá logika a transport mají sousední testy.

Nová vazba ve formuláři rozšíření má výběr „Co po vazbě teče“ (navigace, data, příkaz, událost, neurčeno);
„neurčeno“ klíč `carries` do návrhu neposílá, server (`opora_graph_build.py`) ho jinak přenese na vazbu.

`GraphEditForm` a `GraphNodeEdit` vytvářejí v2 návrhy úprav a odstranění nad
`acceptedGraph` a `workingGraph` z právě načteného kontextu. `graph-edits.ts`
odesílá pouze označená pole (`name`, `purpose`, `parentId`, `sourceRef`, `x`,
`y`, `size`); pracovní rozdíly jiných polí nepřebírá. Vazby mají explicitní
ID, oba konce a port `next`; druh toku `carries` se posílá jen při změně
(`null` = neurčeno), jinak ho server nechá, a kontrola změny ho ukáže česky
(`carriesChange`). Odstranění vyžaduje samostatný výběr všech potomků
a dotčených vazeb. Server hlásí chybějící identity; klient rozsah nerozšiřuje.
Prvek chybějící v pracovním grafu zůstává dostupný pro výslovné odstranění
z přijatého plánu. Nové prvky z původního formuláře tvoří samostatný v1 návrh.

`GraphChangeReview` ukazuje přijatý a pracovní stav před změnou i oba navržené
výsledky, všechny dopady na aktuální stavy, pravidla, rozhodnutí, autonomii,
reporty vazeb a přiřazení ticketů. Checkbox je svázaný s přesným ID v2 návrhu;
POST přijetí posílá `reviewedChangesId` a `adoptBaseGraphDigest: null`.
Neúplný detail nelze přijmout. Rebase je dostupný i při stejném otisku grafu,
protože se mohl změnit související stav. Server rozhoduje o jeho slučitelnosti.

Rozpracované úpravy i potvrzení se ruší při obnově kontextu nebo změně prostoru.
Před první úpravou lze převzít existující neprázdný graf bez pomocné karty:
adopční v1 návrh projde původní úplnou kontrolou grafu a zadání. Změněný
kontext sdílené architektury se přebírá pouze samostatně označeným checkboxem,
včetně možnosti návrhu obsahujícího jen tento krok. Review ukáže všechny
hranice před a po převzetí; sdílená architektura se tím nepřepisuje.

Po rozhodnutí o přijetí řádek návrhu v historii jednou odpoví pohybem: úspěšné přijetí
zeleně pulzne (`graph-proposals__entry--accepted`), přijetí zamítnuté serverem se zatřese
(`--refused`). Stav záblesku je čistá logika `decision-flash.ts` (s testem); hook ho
smaže po `animationend`, novém výběru nebo obnově. Při `prefers-reduced-motion` zůstane
jen barevný rám a stav nese text hlášení. Samostatná akce „zamítnout návrh“ v rozhraní
zatím není; třesení proto patří k zamítnutému přijetí.

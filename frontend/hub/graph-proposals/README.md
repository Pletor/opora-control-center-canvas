# Rozšíření plánu

Samostatný modul OporaHubu pro aditivní návrhy grafu. App vlastní
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

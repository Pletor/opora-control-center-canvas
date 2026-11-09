# Dokončení původní OPORY 2.0

Úkol Linie **OP-7BB14B** navazuje na nasazený `bed520de`. Výslovné upřesnění vlastníka: nepřidávat Centrum práce ani další souhrnnou sekci, neduplikovat existující funkce. Předchozí pokus OP-2F3310 byl odstraněn bez vlastního commitu či nasazení; zrušení zůstává v deníku Linie.

## Hledání a porovnání řešení

Rozšířit současné `knowledge-search` pro `resultType: solution`. Použít existující lokální sémantický worker nad již autorizovanými texty řešení, lexikální shodu a skutečné grafové vazby. Zachovat stabilní identity, kanonické zdroje, revize a nativní důkazy. Nepřidávat novou databázi ani druhý vyhledávač.

Česká významová parafráze musí najít různá relevantní řešení i bez společných slov. Více dokumentů stejného řešení ani společný zdroj nesmí vytvářet další řešení. Srovnání má uvádět doložené rozdíly specifikací, vstupy, společné zdroje a stav skutečného ověření, nikoliv vymyšlené architektonické závěry. Přiznat krácení i nedostupný model; fallback se nesmí vydávat za sémantické hledání. ACL ověřit před předáním textů workeru. Alespoň jedna zkouška použije skutečný instalovaný model.

## Přijaté revize Storyboardu

Zachovat současný Storyboard, API, editor a rozhraní služby. Přijetí scén zapojit do stávajících content proposals, content manifests a accepted head. Nepřidávat vlastní schvalovací systém. Historický snapshot musí být dohledatelný samostatně, při předávce připnutý k přijaté revizi.

Pracovní historie musí umožnit atomický SQL rollback při přijetí. Pokud je nutný nativní append-only store, import původních JSON je idempotentní, zachovává revize, tombstones a stabilní ID a nic automaticky nepřijímá. Původní soubory se neodstraňují. SQL se po převzetí stává jedinou pracovní autoritou; starý soubor nesmí tiše přepsat novější historii. Před živou migrací ukončit starší zapisující procesy nad stejnými daty. Popsat a ověřit export pro návrat pracovních dat; nové přijaté manifesty a assignmenty se nepřepisují ani nemažou. Aktivace nového typu přijatého obsahu vyžaduje kompatibilní běžící čtenáře.

Ověřit draft → návrh → přijetí → assignment v obou protokolech. Další relevantní změna musí vyvolat řízený konflikt, nesouvisející sourozenec ne. Staré `captured-at-claim` assignmenty zůstanou čitelné a neměnné. Obnovení staré scény vytvoří novou revizi. Nezvyšovat bez nutnosti verzi ani přesnou množinu v2 SQL zdrojů: Storyboard již vlastní autentizovaný pin.

## Spolehlivé nástroje Srdce a Pletora

Zpřesnit rozlišení stávajících příkazů: realizační balíček uzlu, tematická rešerše, identity řešení, přesná kanonická revize. Obecný požadavek nesmí být nesprávně hodnocen jen proto, že model zvolil platný `node-brief`.

Vyhodnocovat normalizované argumenty skutečného CLI parseru včetně shellového zápisu i Python argv, nejen sousednost slov v regexu. Zkoušky musejí mít jednoznačný účel a absolutní požadavek na úspěch jednotlivých schopností. Rovnost dvou neúspěšných baseline není důkaz spolehlivosti. Brain aktualizovat standardním kandidátem, skutečnými modelovými evaly a aktivací bez force; uchovat ostatní soubory a dovednosti.

## Skutečný provozní pilot

Použít skutečný gitový AMPLE `5b0b4471c24a4c5bac325d38ff23921c`, nikoliv stejnojmenný lokální registr ani dočasný testovací projekt. Nejprve prověřit existující plán, zadání a zdroj: již realizovanou funkci znovu nevytvářet. Pracovní prostor a běh musí být skutečné a dohledatelné.

Vstoupit standardní agentní relací; Srdce používá vlastní runtime oprávnění. Nevydávat se za člověka a neobcházet autorizaci přímým vydáním Heart tokenu. Provést rešerši s původem, přijatý kontrakt, připnutou předávku, skutečné testy kladného i záporného případu a nativní receipt. Kde je nutná realizace, opřít ji o skutečný commit a ověřené začlenění, ne o ručně vyrobenou deklaraci. Zapsat pravdivý výsledek, včetně nalezených překážek. Stale kontrolu provést bezpečně přes návrh/revizi, bez poškození existující práce.

## Důkaz dokončení

Jedna tabulka skutečných výsledků všech čtyř oblastí, přesné revize a odkazy na nativní důkazy. Relevantní integrační zkoušky, úplný backend, frontend a produkční build. Přesná zelená revize se nahlásí do Linie, přijme jako agent a začlení její službou. Procenta ani dílčí zelené testy nenahradí chybějící provozní průchod.

## Ověřený výsledek 9. 11. 2026

| Oblast | Skutečný výsledek a důkaz |
| --- | --- |
| Hledání a porovnání | Existující Rešerše používá hybridní hledání a zobrazuje uložené rozdíly, společné zdroje a skutečné ověření. Celá sada spustila skutečný lokální ONNX model: česká parafráze bez společných významových slov našla přesně dvě řešení ze dvou projektů. Živý Pletor v 16:08 UTC porovnal přihlašovací uzly AMPLE `9a6d5d3f-83b4-485c-aafe-125e9dff8758` a Tajemství Opory `a46135d9-a9fa-4372-87a1-19ad72596647`; načetl celé porovnání (4 276 znaků) a kanonický `ample_login_existing_auth@1` (6 000 + 885 znaků, stejný snapshot, konečné `nextOffset:null`). Chybějící specifikaci druhého projektu i neznámé provozní ověření výslovně přiznal. Nativní záznam je v `pletor/messages.jsonl`, jednotlivé čtecí akce v Claude JSONL příslušných relací. |
| Přijatý Storyboard | Na skutečné ověřovací kartě AMPLE `b727c1ac-e99f-48ee-8ec1-1efdca859aa9` vznikl obsahový návrh `dbacd4ee9a5fa9be8229ee34405543670557bc0a`. Srdce přijalo přesnou revizi `ab5dd5e19b0954ba7c7073bfb4cbf878c1ac9f21`, manifest `a98f2a966c8b2bebd7cbf3e03062a3a186d12acc`, zdroj Storyboardu revize 2 se třemi zachovanými ID momentů. Neměnný assignment níže obsahuje tyto přesné piny. Integrační testy navíc ověřují oba execution protokoly, konflikt změněné scény, nezávislého sourozence, historické assignmenty a atomický rollback. |
| Nástroje Srdce a Pletora | Standardně aktivovaný Brain skill `opora-control-center@3d37f9782a89cda5eb370c91721ccc7497ecbc48`, skutečný modelový eval `f33063fd482644ef8bc7238bc25bd440`: všechny čtyři požadované schopnosti prošly absolutní bránou. Bez force; ostatní dovednosti zachovány. Srdce v živém pilotu skutečně použilo nativní rešerši, canonical binding, verzovaný Storyboard, obsahový návrh/přijetí a vydání ticketu. Pletor skutečně zvolil čtení napříč projekty a dokončil vícečástový zdroj. Chybné vstupy modelu byly odmítnuty a opraveny pod původní identitou, nikoliv obejity lidským aktérem. |
| Provozní pilot | Skutečný AMPLE `5b0b4471c24a4c5bac325d38ff23921c`, workspace `03116e0b6f4e40dbabfc75241604ce9c`: canonical `ample_cache_integ_kontrakt@2`, binding `kb_bab4626e10070fd33699e8fda1573501@1`, přijatý Storyboard výše. Starý kontext byl odmítnut `409 execution_conflict`. Čerstvý execution `3a1938c33f1b4538b7a614c889165c57` zachytil neměnný assignment s digestem `ace83f0e92b9bb57a396084ccc9b9d8e7035699a2c607918b6b8d919120682ce`. Skutečné schválené příkazy s1/s2 prošly: 2 kladné a 3 záporné testy na čistém původním commitu AMPLE `c2dc67a71df5824b7916686e15886c57b6e42787`. Receipt `3f83e58a4d834675b4770ead1e3b0c3d` má stejné acceptedRevision/assignmentDigest a skutečné výstupy; ticket `tk_4630465439d54a7faf5f88153dc535e6` je nativně `verified`. |

Pilot ověřuje již existující cache, nepřidává druhou implementaci. Receipt je pravdivě
`agent-reported; not independently verified`; stav ticketu sám nenahrazuje důkaz
testů ani nezávislé ověření produkce. Nevznikl fiktivní produktový commit, merge či
uzavření karty. Nativní assignment a receipt lze přečíst přes
`/api/oporahub/executions/3a1938c33f1b4538b7a614c889165c57/assignment` a `/results`
v uvedeném projektu/workspace s příslušným oprávněním.

První přijetí obsahu zahrnulo výslovně zkontrolovanou dokumentační baseline:
1 464 položek, z nich 1 461 prázdných; obsah tvořila původní kresba s 19 prvky,
původní konfigurace prázdného bloku a nový Storyboard. Dalších 248 položek proti
prvnímu odhadu patřilo 31 již existujícím zděděným uzlům. Kontrola hashů potvrdila
nezměněné původní kresby, texty a všech 185 původních specifikací. Původní návrhové
popisky zůstaly návrhem. Před migrací byli zastaveni staří zapisovatelé a pořízena
ověřená SQLite záloha `migration-backups/OP-7BB14B-20261109T150952Z`; legacy JSON
zůstaly zachované. Postup exportu a omezení návratu jsou v
[storyboard-revize-a-navrat.md](../storyboard-revize-a-navrat.md).

Pilot použil nativní protokol v1: plán nemá graph-derived research records,
kanonické zdroje i přijatý Storyboard jsou přesto přesně připnuté. Legacy DDL
coverage guard aktuálních živých databází odmítá přípravu v2; nebyl resetován,
obcházen ani přepsán. Oba protokoly mají samostatné integrační pokrytí. Z výsledku
pilotu nelze tvrdit, že se živá historická databáze již zúčastnila předávky v2.

Implementace `46429553713986f6c5bb5bcc2e1c0f077bbfe975`: úplný backend a databáze
**7 207 passed, 21 skipped**, frontend **524 souborů / 2 914 testů**, produkční build
úspěšný. Skutečný sémantický test mezi přeskočenými není. Otisk zdrojů před/po celé
sadě souhlasí (`b892115863724e04fd88aea2ba4efc99249b03df8040b59982f3487301d931c2`).
Náhled Linie zároveň vykreslil skutečné hybridní hledání i porovnání bez UI chyby.
Závěrečné začlenění a nasazení dokládá deník Linie OP-7BB14B; samotné zelené testy
je nenahrazují.

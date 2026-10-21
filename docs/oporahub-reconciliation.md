# Trvalé sledování GitHub PR

OporaHub může pravidelně načítat stav vybraného PR a uchovat jeho výsledek u
konkrétní přijaté revize plánu. Sledování běží v backendu, i když zavřete panel
nebo prohlížeč. Po restartu serveru se rozpracované úlohy obnoví z databáze.

## Zapnutí a ovládání

Nejprve v [GitHub důkazech](oporahub-github.md) načtěte úplné pozorování PR pro
aktuální přijatou revizi. V panelu trvalého sledování vyberte tento serverový důkaz.
Prohlédněte přesnou revizi plánu, repozitář a jeho číselné ID, číslo a číselnou
identitu PR, zdrojový repozitář a cílovou větev. Potvrzení zapne pravidelné čtení
GitHubu. Klient neposílá vlastní výsledek merge ani libovolnou adresu repozitáře.

Zapnutí, obnovení a opakování vyžadují session člověka a zapisovatelný prostor.
Člověk může sledování pozastavit i při změně konfigurace nebo v prostoru jen pro
čtení, aby mohl zastavit další síťové požadavky. Agent nemůže podvrhnout souhlas
polem v JSON. Změny používají očekávanou generaci a jedinečné
ID požadavku: souběžná změna vyvolá konflikt, přesné opakování stejného požadavku
neprovádí akci znovu. Po nejistém síťovém výsledku nejprve obnovte seznam.

Výjimkou je PR připojené k běhu přijatého zadání: sledování pak zapne server sám
(řízení `auto-enroll`, autor `system / Execution PR link`), viz
[uzavření smyčky](oporahub-executions.md#uzavření-smyčky-běh--pr--merge--plán).
Pozastavení a obnovení takové vazby zůstávají lidskými kroky.

Pro jedno PR může být v prostoru zapnuté jedno sledování. Jiná PR mají vlastní
úlohy. Chcete-li stejné PR přiřadit k jiné revizi plánu, původní sledování nejprve
výslovně pozastavte a vytvořte nové z aktuálního důkazu. Historie se nemaže.
Pozastavení zastaví další načítání a zneplatní rozpracovaného pracovníka. Obnovení
ponechá původní vazbu na plán a znovu ověří konfiguraci. Ruční opakování pouze
naplánuje trvalou úlohu; neobchází čekání předepsané GitHubem.

## Co jednotlivé stavy říkají

Panel odděluje tři informace:

- Stav úlohy: naplánovaná, probíhající, opakovaná po chybě, pozastavená nebo
  dokončené dorovnání. Ukazuje další pokus, chybu a případné vypršení rezervace.
- Pozorovaný stav PR: otevřené, zavřené bez merge nebo mergnuté. Původní SHA a
  SHA merge jsou samostatné údaje. Pouhé zavření PR neprokazuje merge.
- [Pravidla review a kontrol](oporahub-review-policy.md): mají vlastní revizi,
  důkazy a platnost. Úspěšné načtení PR samo tato pravidla nesplní.

Při novém neúspěšném nebo probíhajícím pokusu zůstává předchozí úspěšný údaj
výslovně historickým pozorováním. Chyba nezahodí starý merge z historie, ale starý
výsledek se nevydává za čerstvou odpověď. Historie obsahuje pokusy a přechody;
opakované načtení stejného stavu nevytvoří další událost téhož merge.

Změna přijaté hlavy plánu nepřepne vazbu sledování. Původní PR se dál sleduje u
původní revize a panel ukáže, že jde o dřívější plán. Tak lze dohledat výsledek
rozpracované práce i po přijetí jiných změn. Tato vazba je lidsky potvrzené
přiřazení, nikoli důkaz, že kód splňuje celé zadání.

GitHub může pro merge, squash a rebase uvádět jiné výsledné SHA než SHA zdrojové
větve. Kontroly zdrojového SHA proto nejsou důkazem ověření výsledného merge
commitu. Pozorovaný merge také nepotvrzuje, že větev commit stále obsahuje po
revertu či force push, ani že byla aplikace nasazena. Sledování neprovádí merge,
přijetí plánu nebo automatické dokončení karty.

## Intervaly, výpadky a obnova

Otevřené PR se standardně kontroluje po pěti minutách. Zavřené PR bez merge má
delší interval, protože může být znovu otevřeno. Po úplném záznamu merge je
sledování dorovnané; neprovádí nepřetržité kontroly obsahu cílové větve.

Síťové chyby vedou k opakování s rostoucím odstupem. GitHub rate limit může další
pokus odložit déle; panel ukazuje skutečný další termín. Změna číselné identity
repozitáře/PR, cílové větve nebo místní konfigurace vyžaduje pozornost člověka.
Smazaný zdrojový fork sám nesmí skrýt historický merge známého PR.
Známý pokyn GitHubu k čekání se zachová i po pozastavení nebo zneplatnění výsledku;
obnovení sledování jej neobchází.

Úloha i rezervace jsou v SQLite. Síťové čtení probíhá mimo projektové zámky.
Záznam pozorování, případné nové události a posun úlohy se uloží jednou transakcí.
Při pádu před jejím dokončením se úloha po vypršení rezervace převezme znovu.
Opožděná odpověď starého pracovníka nesmí přepsat novější převzetí ani pozastavení.
Server používá omezený sériový pracovník; interval je plánovaný termín, nikoli
záruka přesného času při vytížení či rate limitu. Bez zapnutí se GitHub nečte.

Token se používá ze stejného prostředí jako u GitHub důkazů. API jej nevrací;
veřejná odpověď neobsahuje ani interní identitu vlastníka rezervace. Integrace
používá pouze GET na pevný GitHub API origin. Zavření aplikace přeruší načítání,
příští spuštění však uchová vazby i historii. Staré migrační zálohy nesmějí
přepsat novou autoritu a ztratit tuto historii.

Pro testy nebo provozní pozastavení automatického pracovníka lze server spustit
s `OPORA_RECONCILIATION_WORKER=0`. Vazby a fronta zůstanou uložené, automatické
čtení se však nespustí. Panel tento stav ukazuje; po odstranění přepisu a restartu
se pracovník znovu zapne. Výchozí stav je zapnuto, síťové čtení stále vyžaduje
výslovně založené sledování.

## API a ověření

Prefix je `/api/oporahub/reconciliation`: seznam, `/candidate` pro kontrolu
serverového důkazu, `/bindings` pro zapnutí, `/{bindingId}/control` pro
pozastavení/obnovení/opakování a `/{bindingId}/history` pro stránkovanou historii.
Podrobný [implementační kontrakt](oporahub-reconciliation-contract.md) popisuje
pole, hranice transakcí a požadované testy. Jde o samostatnou vrstvu vedle ručně
načítaných review důkazů a vedle výsledků vykonavatelů.

Význam GitHub údajů: [Get a pull request](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request).
Doporučení pro čtení: [GitHub REST API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api).

# Trvalé sledování GitHub PR

Modul připojuje přijatou revizi plánu k serverem ověřené numerické identitě repozitáře a PR. Člověk nejprve zvolí úplné pozorování, zkontroluje přesné identity a revizi a výslovně potvrdí trvalé čtení GitHubu. Změna plánu původní vazbu nepřepisuje: její výsledek zůstává historický.

`use-github-reconciliation.ts` vlastní požadavky a stav; App vlastní hook. Komponenty dostávají pouze model a callbacky. Čtení používá sdílený poller. Každý zápis má stabilní requestId pro nezměněný úmysl, očekávanou generaci nebo přijatou revizi a samostatné potvrzení. Klient neopakuje POST automaticky. Změna rozsahu nebo vybrané vazby ruší staré potvrzení; opožděné odpovědi nesmějí přepsat nový rozsah.

Panel odděluje zdraví úlohy, poslední skutečně pozorovaný stav PR a nezávislé review podle politiky. Selhání čtení zachovává označené historické pozorování. Sloučení PR neznamená ověřené review, nasazení ani přítomnost změn na současné cílové větvi. Merge SHA a pozorované head SHA se zobrazují zvlášť. Vypnutý automatický worker má viditelné vysvětlení.

Historie má nezávislé stránkování neměnných záznamů a pokusů. Dokončený proud se při čtení dalšího proudu znovu nepřipojuje. Žádné části serverové konfigurace, přístupové tokeny nebo raw JSON se do panelu nevkládají. Text vykresluje React; odkaz na PR vzniká pouze z ověřitelného tvaru názvu repozitáře a kladného bezpečného čísla PR.

Testy pokrývají projekci payloadů, CAS a scope, stabilní identifikátory úmyslu, potlačení opožděných požadavků, stránkování, bezpečný text, prázdné plátno, historický výsledek při chybě a absenci automatického opakování zápisu.

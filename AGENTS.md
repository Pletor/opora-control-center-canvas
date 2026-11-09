# Pravidla pro agenty

Platí `CLAUDE.md` a `docs/pravidla-struktury.md`.

Vývoj běží autonomně: identifikovaný agent si vytvoří úkol Linie přes API a pokračuje bez lidského schvalování. Po testech hlásí výsledky, technicky přijme přesnou zelenou revizi pod vlastní identitou (`accept --untested`), povolí začlenění a požádá službu OPORY o merge. Agent nezapisuje lidskou zkoušku ani se nevydává za člověka. Kontroly identity, rozsahu tokenu, aktuální hlavy, revize zadání, testů a cílové větve zůstávají povinné. Přímý push nebo merge do sdílené větve nenahrazuje službu OPORY.

Při opravě samotného autonomního založení úkolu lze nezbytné bootstrap změny následně zaevidovat v Linii; chybějící lidské schválení nesmí autonomní práci blokovat.

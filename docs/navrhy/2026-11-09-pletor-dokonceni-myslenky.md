# Pletora: prostor pro dokončení myšlenky

Kontrakt OP-B171BE, 9. 11. 2026. Navazuje na požadavek člověka: při přemýšlení neukončovat řeč a nezačínat práci před dokončením myšlenky.

## Příčina

Rozpoznávač již skládá úseky a přežívá běžné ukončení prohlížečové relace. Výchozí endpointMs=8000 ale zaměňuje osm sekund ticha za dokončení lidské myšlenky. finish() pak ihned vyvolává odeslání. Existující text „Máš čas dokončit myšlenku“ časový limit nepřiznává. Stejný kód je v původním Vite zdroji i běžícím snapshotu 7815984a.

## Výsledek

- Výchozí poslech nemá časový limit; práci spustí explicitní dokončení tlačítkem „Domluvil jsem“.
- Preference před touto změnou přejdou na ruční dokončení, ostatní hlasové volby se zachovají. Nově výslovně zvolený časový limit zůstává uložený.
- Volitelné automatické dokončení 4/8/12 sekund musí být v rozhraní jasně přiznané.
- Běžné pauzy a obnova rozpoznávání zachovají celý přepis. Zrušení neodesílá. Pozdní události starého rozpoznávače neodesílají.
- Odpověď na pozadí nemluví přes rozpracovanou myšlenku.
- Nepřidává se další model ani odhad úmyslu podle tečky či jednotlivého slova.

## Ověření

Minimálně minuta ticha, pokračování po obnově rozpoznávání, žádný požadavek před explicitním dokončením, právě jedna celá zpráva poté. Ověřit migraci preferencí, explicitní automatickou volbu po reloadu a existující odložené čtení. Prohlížečový důkaz používá řízené události rozpoznávání a zachytí síťové odeslání; není důkazem kvality fyzického mikrofonu ani služby rozpoznávání češtiny.

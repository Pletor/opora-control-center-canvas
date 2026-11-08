# Pletor vyslechne celou myšlenku

Úkol Linie: OP-5AED6F. Finální úsek z rozpoznávání řeči není souhlas člověka s odesláním. Pletor skládá více úseků do jednoho viditelného přepisu a odešle jej jednou, až skončí tah člověka.

Výchozí automatické dokončení čeká osm sekund; nová řeč odpočet ruší. Nastavení aplikace nabízí čtyři, osm nebo dvanáct sekund a ruční dokončení bez časového limitu. Tlačítko „Domluvil jsem“ odešle dosavadní přepis. Zrušení poslechu jej neodesílá. Nastavení je společné všem projektům.

Krátké ukončení služby rozpoznávání nesmí zahodit rozpracovanou myšlenku ani ji samo odeslat. Obnovení poslechu zachová přepis. Chyba mikrofonu není dokončení tahu. Pozdní události zastaveného rozpoznávání nesmí odeslat zprávu.

Odpověď na pozadí nesmí zastavit rozpracovaný poslech. Čeká, dokud člověk nedokončí nebo nezruší svůj tah; probíhající hlasová odpověď zůstává přerušitelná.

Ověření: více finálních úseků, pauza uvnitř myšlenky, nová řeč během odpočtu, ruční dokončení právě jednou, zrušení bez odeslání, obnovení rozpoznávání, finální a průběžný úsek současně, odložená odpověď a skutečné ovládání přepisu v prohlížeči se simulovanou službou rozpoznávání.

## Výsledek ověření

- `npm test`: 495 souborů, 2 835 testů prošlo.
- `npm run build`: prošlo včetně typové kontroly.
- Prohlížeč nad skutečnou aplikací Ample: automatický a ruční režim zachoval přepis přes restart a odeslal obě věty právě jednou; oznámení na pozadí nepřerušilo rozpracovanou myšlenku. Samostatně ověřeno automatické dokončení po osmi sekundách, Esc bez odeslání a uložení ručního režimu.
- Rozpoznávání a odpověď serveru byly při této regresní zkoušce simulované. Akustickou kvalitu skutečného mikrofonu musí potvrdit praktická hlasová zkouška.
- `pytest backend` byl spuštěn a přerušen při 7 %; kompletní backendová sada není touto opravou ověřena. Backendový kód se nemění.

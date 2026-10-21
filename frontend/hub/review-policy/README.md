# Místní pravidla GitHub review a kontrol

Samostatný dílek OporaHubu. App vlastní `useReviewPolicy`; komponenty dostávají
data a callbacky. Nastavení je neměnná serverová revize s CAS ukazatelem.
Editor odesílá pouze scope, očekávanou revizi pravidel, ID serverového důkazu
a pravidla. Identitu repozitáře, autora ani výsledek ověření klient neurčuje.

Povinné kontroly mají přesnou dvojici číselné ID aplikace + název. Reviewer
se určuje číselným ID GitHub účtu; login je jen nápověda. Obě minima a doba
platnosti se nastavují výslovně. App ID a název nejsou zárukou identity workflow;
účty nejsou nezávislé osoby. Commit statusy jsou pouze informativní.

Aktivace i vypnutí mají samostatný přehled a potvrzovací checkbox svázaný
s přesným payloadem, scope, akcí a CAS revizí. Změna formuláře, scope nebo
obnova potvrzení ruší. POST se po odmítnutí ani nejistém síťovém výsledku
neopakuje. Vypnutí přidává historickou revizi a nezobrazuje splnění prázdných
pravidel. Historie zůstává čitelná při nedostupném kontextu nastavení.

`usePolicyStatus` čte samostatné aktuální vyhodnocení pro vybrané číslo PR.
Změna scope, PR, přijaté revize, pravidel nebo nového pozorování zneplatní
opožděné odpovědi i původní badge. Probíhající či neúspěšný import nezachová
dřívější úspěch. Stav se každých 15 sekund čte z uložených serverových důkazů;
nejde o nové načtení GitHubu. Nové pozorování spouští jen tlačítko existujícího
modulu GitHub důkazů.

Lokální expirace používá rozdíl serverového expiresAt/evaluatedAt a odečítá
celou dobu status requestu. Monotónní čas prohlížeče a deadline timer odstraní
zelený stav i bez dalšího serverového výsledku. Server zůstává autoritou.
Panel ukazuje interval pozorování, čas vyhodnocení, expiraci, plnou revizi
pravidel, zadání, SHA a oddělené kontroly/review kódu/review zadání.

Historický detail GitHub pozorování má samostatné nezelené vyhodnocení;
v1 důkazy výslovně vyžadují nové pozorování pro tato pravidla. Veškeré názvy,
ID, blokující důvody a historie se vykreslují jako React text. Žádná operace
neslučuje PR, nepíše review na GitHub ani nedokončuje kartu.

Sousední testy ověřují projekci payloadu a limity, potvrzení, jednorázový
transport, izolaci požadavků, expiraci a bezpečnou prezentaci. Browser proof
používá skutečné izolované API a syntetický GitHub reader pro řízené schválení
a selhání; není důkazem skutečného schválení na GitHubu.

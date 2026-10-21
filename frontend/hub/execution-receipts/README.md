# Běhy agentů a nahlášené výsledky

Samostatný dílek OporaHubu čte historii všech karet nebo vybrané karty a neměnné receipty výsledků.
Stav `reported` znamená nahlášeno, nikoli ověřeno nebo dokončeno. Spouštění běhů
zůstává v Agent Office. Výsledky jsou prostý text, odkazy ani příkazy se nespouštějí.

App vlastní hook; komponenta dostává data a callbacky. Změna projektu, workspace,
karty, běhu či přijaté revize zneplatní opožděné odpovědi. Obnova je výslovná, bez
pollingu. Kontext může být nedostupný, ale uložená historie se přesto zobrazí.
Historie načítá nejvýše 100 souhrnů; receipty pouze pro vybraný běh. Žádný GET
nečte assignment token. Před identifikovaným čtením se obnoví cookie UI session.

Výchozí volba „Všechny karty včetně odstraněných“ čte historii celého projektu
a workspace bez filtru `nodeId` a bez požadavku na kontext živé karty. Funguje
i po odstranění poslední karty. Každý běh ukazuje původní ID karty; chybějící
karta je označená jako odstraněná nebo nedostupná. Výsledky stále patří původní
přijaté revizi. Selhání kontextu jednotlivé karty neblokuje historii ani detail
uloženého výsledku. Selhání samotného čtení historie zůstává viditelnou chybou.

Stav běhu interpretuje backend; frontend navíc neoznačí vypršelý nebo neplatný
číselný čas jako aktivní. Časy jsou Unix seconds ze serveru, nikoli odhad shody
hodin. Zobrazení je stav při načtení, nikoli živé potvrzení oprávnění.

Ověření: sousední testy přípravy GET/session, izolace požadavků, stavů a bezpečného
textu; integrační headless screenshot nad izolovanými daty, npm test a npm run build.

Veřejná historie ukazuje uloženého vlastníka a volitelný neměnný budget protokolu v2:
pokus, opravné kolo a pevný deadline. Starý v1 nemá zpětně vymyšlený pevný limit.
Lidské `canCancel` je oddělené od možnosti konfigurovat archivovaný prostor.
Zrušení vyžaduje kontrolu konkrétní execution a epochy, výslovné potvrzení a stabilní
requestId. Nemá automatický retry, nevrací pokusy a neodstraňuje reported receipt.
Přepnutí scope/běhu nebo zavření detailu ruší potvrzení. Odebrání oprávnění není
důkaz zastavení všech procesů.

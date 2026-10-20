# Běhy agentů a nahlášené výsledky

Samostatný dílek OporaHubu čte historii vybrané karty a neměnné receipty výsledků.
Stav `reported` znamená nahlášeno, nikoli ověřeno nebo dokončeno. Spouštění běhů
zůstává v Agent Office. Výsledky jsou prostý text, odkazy ani příkazy se nespouštějí.

App vlastní hook; komponenta dostává data a callbacky. Změna projektu, workspace,
karty, běhu či přijaté revize zneplatní opožděné odpovědi. Obnova je výslovná, bez
pollingu. Kontext může být nedostupný, ale uložená historie se přesto zobrazí.
Historie načítá nejvýše 100 souhrnů; receipty pouze pro vybraný běh. Žádný GET
nečte assignment token. Před identifikovaným čtením se obnoví cookie UI session.

Stav běhu interpretuje backend; frontend navíc neoznačí vypršelý nebo neplatný
číselný čas jako aktivní. Časy jsou Unix seconds ze serveru, nikoli odhad shody
hodin. Zobrazení je stav při načtení, nikoli živé potvrzení oprávnění.

Ověření: sousední testy přípravy GET/session, izolace požadavků, stavů a bezpečného
textu; integrační headless screenshot nad izolovanými daty, npm test a npm run build.

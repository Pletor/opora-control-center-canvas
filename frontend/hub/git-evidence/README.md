# GitHub důkazy

Samostatný dílek OporaHubu pro serverem načtená historická pozorování GitHubu. `components/GitEvidence.tsx` skládá formulář, historii a `GitEvidenceDetails`; dostává hotový model v props a změny předává callbackům. Síť a stav vlastní hook `logic/use-git-evidence.ts`, který volá rodič App.

Hook přijímá projekt, pracovní prostor, zapnutí prostředí a čítač změn přijatého zadání. Generace požadavků izolují projekty, prostory i obnovy. GET načítá pouze souhrny uložené historie; samostatný GET vybrané položky načte podrobnosti s vlastní ochranou proti opožděným odpovědím. POST výslovně načte nové GitHub pozorování; nikdy se automaticky neopakuje. Následný GET přepočítá historické verdikty vůči poslednímu známému SHA. Při jeho chybě zůstane jen právě uložený záznam a viditelná chyba, nikoli staré verdikty vydávané za aktuální.

UI odděluje review kódu, review konkrétní přijaté revize zadání a pozorované kontroly. Verdikty přebírá ze serveru. Vždy uvádí čas pozorování, plnou revizi a SHA; `complete:false` ukáže jako neúspěšný pokus bez předstíraných GitHub identit. Celkové ověření implementace se netvrdí bez politiky povinných kontrol a důvěryhodných poskytovatelů. Historie obsahuje nejvýše 100 položek. Lokální projekt bez GitHubu ukáže vysvětlení dostupnosti.

Značka `Opora-Plan` je pouze text k označení a zkopírování do samostatného řádku review. Tento dílek review neodesílá, neslučuje PR a nepřijímá zadání. Externí odkaz vzniká pouze z ověřitelného názvu repozitáře a kladného čísla PR na pevném github.com originu.

Testy vedle čisté logiky ověřují validační kontrakt importu, izolaci požadavků, bezpečné odkazy a odmítnutí opožděného úspěchu po novějším neúspěchu. Vzhled je v `styles/git-evidence.css` s předponou `git-evidence`.

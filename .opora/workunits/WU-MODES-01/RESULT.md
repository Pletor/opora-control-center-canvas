# Pracovní módy — implementovaný řez

## Ovládání
- Vlevo Struktura / Kreslení / Mapa. Módy zachovávají projekt a pracovní prostor, režim a vrstvu nese URL.
- Kreslení: skutečný Excalidraw 0.18.1, tužka, tvary, čáry/šipky, text, rámce a guma. Uložit kresbu nad plochou. Každá vrstva má vlastní lokální kresbu.
- Mapa: skutečné uzly celého aktuálního projektu; přerušované hrany znamenají obsahuje, plné explicitní propojení. Dvojklik otevře uzel ve Struktuře. Propojit lze i různé vrstvy stejného projektu.
- Export pro Archify vytvoří typed JSON ze stejného graphu. Není to vložený Archify renderer ani automatická analýza codebase nebo mezirepozitářové mapování.
- Nastavení plochy nahoře: viditelnost mřížky, skutečné přichytávání a rozteč; kreslení má vlastní nativní mřížku. Preference patří tomuto prohlížeči.

## Data a bezpečnost
Kresby nejsou uzly ani dependency hrany. Jsou lokální SQLite záznamy s append-only revizemi a CAS; nejsou zatím Git export/import. Neuložená práce přežije přepnutí módu/vrstvy v otevřené aplikaci, před úplným reloadem je nutné uložit. Konflikt nemaže místní práci; discard je výslovný. Probíhající save se při přepnutí bezpečně dokončí. Main zůstává read-only a bez importu kreseb. Obrázky, souborové importy a web embeds nejsou součástí tohoto řezu.
Nativní text/points/geometrie/Unicode/velikost jsou validované; rozbitý či nenačtený kreslicí modul nezruší celé UI. Mazání nadřazeného uzlu z Mapy opraví navigaci. Žádný LLM, voice, cloud collaboration ani remote write se nezapíná.

## Evidence
54 Python testů PASS; 27 Playwright PASS; build, Ruff, Prettier a nezávislé backend/frontend review PASS. Ověřené hashe a skutečné reporty jsou v evidence/modes-verification.json, modes-pytest.xml a modes-playwright.json. Source hash porovnání bylo provedeno nad finálními kontrolovanými soubory.
Počáteční JS má 417156 B; velký kreslicí modul je oddělený dynamic entry (1144816 B). Test manifestu a požadavků dokazuje, že jej Struktura nenačítá. Drawing smoke blokoval externí requesty a proběhl bez nich; fonty se kopírují lokálně. Npm production audit je bez známých vulnerabilities; uvedená upozornění zůstávají zdokumentovaná, nikoli skrytá.
Fixture export byl validován skutečným Archify CLI (standard, 9 kontrol); není to univerzální estetická garance všech velkých diagramů. Screenshoty drawing-rectangle.png, drawing-mobile.png a project-map.png jsou izolované testovací podklady.

## RED → GREEN / nalezené chyby
Chybějící UI/API a odmítané cross-layer hrany → implementováno. Ztráta měřených rozměrů mapových uzlů při výběru → controlled node state. Zpětná vazba nástrojů Excalidraw způsobila React185 → oddělené command/observed state. Starý onChange obnovoval explicitně zahozený draft → okamžité odpojení staré scény a generation guard. Malformed typ/points/text a příliš velká čísla → fail-closed validace. Nedostupný lazy modul → izolovaná chyba s návratem do Struktury.

## NEXT NODE
Obrázky/podklady u uzlů, Git export specifikací/kreseb, context compiler a skutečný LLM tunnel. Žádná z těchto věcí se nevydává za již hotovou.

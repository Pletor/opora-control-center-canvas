# Opora Control Center — Canvas

Samostatný nový Canvas. Není závislý na starém OporaCC, Bridge ani na předchozím pokusu OporaCC-v3.

## Pracovní módy — 2026-09-09

Vlevo přepínej **Struktura / Kreslení / Mapa**, nahoře otevři **Nastavení plochy**. Kreslení používá lokálně dodaný Excalidraw a ukládá kresbu podle projektu/pracovního prostoru/vrstvy tlačítkem **Uložit kresbu**. Mapa vychází ze skutečných uzlů a propojení; podporuje i vazby napříč vrstvami a export JSON pro Archify. Nakreslená šipka není automaticky strukturální vazba.

Neuložené kresby zůstávají při přepínání módů v otevřené aplikaci; před reloadem je ulož. Main je read-only. Import obrázků/souborů a automatické mapování codebase zatím nejsou součástí tohoto řezu. Podrobnosti a důkazy: [.opora/workunits/WU-MODES-01/RESULT.md](.opora/workunits/WU-MODES-01/RESULT.md).

`npm ci` instaluje i Excalidraw, `npm run build` zkopíruje fonty do lokálního dist. Runtime nevyžaduje CDN. Licenční notices jsou v `public/third-party-notices.txt` a ve výsledném buildu.

## Mazání položek — 2026-09-09

Vyber uzel/sektor a použij **Smazat uzel / Smazat sektor** v detailu. Klikni na vazbu a zvol **Smazat vazbu**. Vybraný repozitář lze **Odebrat** tlačítkem v horní liště. Vše má potvrzovací náhled; sektor zahrnuje potomky a související vazby. Zrušit/Escape nic nemaže; změněná revize vyžaduje nový náhled.

Odebrání repozitáře znamená odpojení z OporaCC, **ne smazání GitHubu nebo lokálních kopií**. Main je nadále pouze pro čtení. Předchozí graf a uložená zadání zachovává lokální DB; UI obnovení není součástí této verze. Viz [.opora/workunits/WU-DELETE-01/RESULT.md](.opora/workunits/WU-DELETE-01/RESULT.md).

## Aktuální stav — R01, 2026-09-09

**Toto je jediný primární projekt. Začni v [START-HERE.md](START-HERE.md).**
V detailu uzlu je editor cíle práce, omezení a podmínek dokončení: explicitní uložení, revize, konflikt dvou oken, zachování rozepsaného textu při přepínání a bezpečné chybové stavy. Zadání je lokální SQLite záznam, nikoli dosud Git-verzovaná specifikace. Před úplným reloadem je nutné rozpracovaný text uložit.

Od R01 běží Playwright na **8741** s vlastními daty; produkční **8740 se kvůli testům nezastavuje**. `OPORA_CANVAS_PORT` je explicitní serverová konfigurace host/origin gate (default 8740); při změně musí souhlasit s uvicorn `--port`.

Důkazy a zbývající scope: [.opora/workunits/WU-R01/RESULT.md](.opora/workunits/WU-R01/RESULT.md). Historický rozsah první verze níže zůstává zachovaný.

## Spuštění

```sh
uv sync
npm ci
npm run build
uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8740
```

Otevřít **http://127.0.0.1:8740/**. Výchozí pracovní prostor je prázdný lokální návrh bez repozitáře. Nic se samo neklonuje a žádný agent se nespouští.

## Technologie

React + TypeScript + React Flow (`@xyflow/react`), Vite pro statický klient; Python + FastAPI, SQLite a Git CLI pro aplikační služby. Přesné závislosti: `uv.lock` a `package-lock.json`. Ověřená Python verze je 3.12.11, Node 22.13.1.

Produkční běh potřebuje jen Python server + Git; Node slouží k sestavení statického frontendu. Načítání plátna nečeká na GitHub ani Bridge. Soubory klienta jsou lokální, žádné CDN/fontové API.

## Fungující rozsah

- Prázdné posouvatelné a zvětšovatelné plátno s minimapou.
- Vytváření sektorů a uzlů, zanoření do každého uzlu, drobečky, vazby mezi uzly stejné vrstvy.
- Uložení názvu/podstaty a pozic, potvrzení změny podstaty. Persistovaný graf v SQLite u lokálního návrhu; viewport v prohlížeči, vrstva v URL.
- Optimistická ochrana před přepsáním novějšího grafu jiným oknem.
- Explicitně schválené připojení GitHub HTTPS URL: skutečný Git clone do odděleného spravovaného adresáře, na pozadí se stavem jobu. Žádná kopie bez .git.
- Čistý main jako read-only pohled na **commit** `HEAD:opora-canvas.json`, nikoli na rozpracovaný soubor. Jméno výchozí větve se zjistí z repozitáře (nemusí být doslova main).
- Oddělené worktrees a větve `work/<id>` založené ze spravovaného mainu; vazba na uzel a popis vlastníka. Popis vlastníka není tvrzení o běžícím agentovi.
- Přepnutí main/pracovní prostor nemění checkout žádného existujícího pracovního stromu.
- Potvrzená synchronizace mainu z uloženého upstreamu: kontrola URL, větve, čistoty; fetch, fast-forward a readback SHA. Dirty stav nebo konflikt se nezahazuje.

## Co tato první verze nedělá

- Sama nespouští, neřídí ani nesimuluje agenty.
- Nevytváří GitHub fork ani pull request, neprovádí remote merge nebo push. Schválený merge probíhá v dosavadním GitHub workflow; poté lze main synchronizovat v aplikaci.
- Neimportuje automaticky schválený OPORA Brain strom ani odhadované uzly z názvů souborů. Chybějící `opora-canvas.json` v repozitáři je výslovný prázdný/missing stav. Graf se připraví ve worktree a začlení do repozitáře standardním review/merge.
- Lokální návrh zůstává samostatný; jeho automatický převod do připojeného repozitáře není implementován.
- Neoznačuje dokončení uzlů podle počtu souborů nebo tvrzení agenta. Důkazy/CI/PR lifecycle integrační panel je další samostatný řez.
- Nejde o sandbox vůči škodlivému procesu s plnými oprávněními aktuálního uživatele; `.data` a spravované repozitáře musí zůstat pod kontrolou uživatele.

## Data a bezpečnost

Výchozí data: `.data/production/canvas.sqlite`; kopie projektů a worktrees: `.data/production/projects/<id>/`. Tyto cesty nejsou verzované. `OPORA_CANVAS_DATA` je volitelná explicitní konfigurace alternativního adresáře.

Aplikace běží pouze na loopbacku. Zápisy vyžadují stejný Origin a JSON. API nepřijímá libovolné lokální cílové cesty: Git repo adresáře odvozuje server. GitHub URL neobsahuje userinfo/token/query. Git hooky, fsmonitor a rekurzivní submodules jsou pro Git příkazy vypnuté. Veřejné repo nevyžaduje token; privátní potřebuje předem nastavený serverový Git credential přístup. Formulář token nepožaduje; Git je neinteraktivní a při chybě přístupu job selže.

Žádný původní projekt, worktree, export nebo dokument nebyl smazán.

## Testy

```sh
uv run pytest -q
uv run ruff check backend tests scripts
npm run build
npx playwright install chromium
npx playwright test
```

Historický testovací popis před R01 (aktuální port je 8741, viz výše): Playwright spouští vlastní server na 8740, proto před ním zastavte produkční server. Má vlastní `.data/e2e-<čas>/` a skutečné dočasné Git fixture repozitáře; **nikdy nepoužívá `.data/production`**. Testuje prázdný draft, zanoření/reload, main proti dvěma izolovaným worktrees. Python testy navíc ověřují zablokování cizího Origin/Host, stale graf, cykly, pomalý Git proti bootstrapu, externě mergnutou revizi a ochranu dirty mainu.

`evidence/empty-canvas.png` je skutečný prázdný Canvas; screenshoty s názvem fixture jsou pouze důkazy testovacího průchodu a nejsou produkční data.

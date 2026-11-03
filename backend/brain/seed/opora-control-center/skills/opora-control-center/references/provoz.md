# Provoz aplikace: spuštění, zastavení, restart, build, kontrola

Kdy mě číst: máš Oporu spustit, zastavit, restartovat, přestavět frontend, ověřit, že běží správná verze,
nebo zjistit, proč agent na adrese nic nevidí. Platí pro agenta mimo okno aplikace (terminál, VS Code);
asistent v okně aplikace procesy neřídí (backend mu pustí jen `opora_read.py` a `opora_write.py`).

## Jeden příkaz, jeden zdroj nastavení

Z kořene repa Opory (ne z repa cílového projektu):

| Chci | Příkaz |
|---|---|
| spustit (sestaví frontend, když je starší než zdroje, otevře prohlížeč) | `uv run opora` (= `npm start`) |
| spustit bez prohlížeče, jako agent | `uv run opora --no-open` |
| spustit bez sestavení frontendu (vím, že `dist/` je aktuální) | `uv run opora --no-open --no-build` |
| jen vypsat výslednou konfiguraci (port, data, profil, zrcadlo) | `uv run opora --check` |
| druhá instance vedle běžící (jiný port, **jiná** datová složka) | `uv run opora --port 8791 --data .data/kopie --no-open` |
| náhled nad kopií dat (port 8790, `.data/preview`) | `uv run opora --profile preview` |
| jen backend pro Vite (`npm run dev` proxuje `/api`) | `uv run opora --profile dev` + `npm run dev` |

Nastavení: `opora.toml` (v gitu: `[app] host, port, data, open_browser`, `[build] frontend = auto|always|never`,
`[profiles.*]`, `[integrations]`) a `opora.local.toml` (mimo git, stejná struktura, má přednost: typicky
`[app] data` mimo repo, `[jev] provider`, `[mirror]`). Tajemství (klíče API) jen v `.env` nebo prostředí; `.env`
doplní jen proměnné, které systém nemá, a hodnoty se nikdy nevypisují. Do `opora.local.toml` a `.env` nepiš bez
pokynu člověka a nikdy je necituj do odpovědi.

Výchozí adresa je `http://127.0.0.1:8740/`. Port drží jediný proces: obsazený port = „běží už jiná instance?“
a start skončí. Datová složka (`registry.sqlite`, projekty, worktrees, snímky) je jedna na instanci; dvě instance
nad stejnou složkou nespouštěj. Přesun dat: `uv run python tools/move_data_root.py <stará> <nová> [--dry-run]`
při zastaveném backendu (zapíše novou `data` do `opora.local.toml`).

## Co se kdy projeví

- **Python (backend) se nehot-reloaduje.** Po změně v `backend/` nebo `tools/opora.py` restartuj proces.
- **Frontend** servíruje backend z `dist/`. Po změně ve `frontend/` spusť `npm run build` (sestaví i při startu,
  když je `dist/index.html` starší než zdroje); restart backendu netřeba, stačí obnovit stránku (Ctrl+F5 proti cache).
- `uv run opora --check` ani `/api/health` neříkají, která verze frontendu se servíruje: porovnej čas
  `dist/assets/index-*.js` s nejnovějším zdrojem, nebo `opora_read.py status` (`servedIndexSha256`,
  `backendIdentityAtStartup`).

## Zastavení a restart (Windows)

Zastav jen instanci, kterou jsi spustil nebo kterou ti člověk výslovně označil. Na jednom počítači může běžet víc
instancí (jiné relace agentů na jiných portech, např. 8745); cizí instanci nerestartuj ani nezabíjej, port si
nepřebírej. Proces najdi podle portu, ne podle jména (`python` běží i jinde):

```powershell
# kdo drží port
Get-NetTCPConnection -LocalPort 8740 -State Listen | Select-Object OwningProcess
# zastavit jen ten proces
Stop-Process -Id <PID> -Force
# ověřit, že je port volný
Get-NetTCPConnection -LocalPort 8740 -State Listen
```

Spuštění na pozadí z PowerShellu, aby relace agenta nečekala a výstup zůstal v logu:

```powershell
Start-Process uv -ArgumentList "run opora --no-open" -WorkingDirectory "<kořen repa Opory>" `
  -RedirectStandardOutput "<log>.out.txt" -RedirectStandardError "<log>.err.txt" -WindowStyle Hidden
```

Restart = zastavit podle portu → (po změně frontendu `npm run build`) → spustit → ověřit níže. Proces, který
spustí agent, je potomek jeho relace; člověk si Oporu často pouští sám (`uv run opora` ve svém terminálu),
pak ji po úpravách jen požádej o restart, nebo ji restartuj až na jeho pokyn.

## Ověření, že běží správně

```bash
python "<SKILL_DIR>/scripts/opora_read.py" --base-url http://127.0.0.1:8740 status
```

`status` vrací `health` (`/api/health` musí mít `status: ok` a `product: Opora Canvas`, jinak na adrese neběží
Opora), `projectCount`, `servedIndexSha256` a identitu backendu ze startu. Bez skriptu stačí HTTP:
`GET /` → 200, `GET /api/health` → `{"status": "ok", "product": "Opora Canvas"}`, `GET /api/bootstrap` → 200
s `projects`. Cesta `/api/status` neexistuje (404 není chyba). Chyba spojení = proces neběží nebo jiný port;
`uv run opora --check` ukáže, kde má běžet.

Před hlášením „hotovo“ po změně kódu Opory: `uv run pytest backend`, `npm test`, `npm run build` a výstupy
v odpovědi (pravidlo repa). Dva testy Graphify selhávají bez balíčku `graphify` v interpretru; nejsou tvou chybou.

## Ovládání okna (co agent dělá přes prohlížeč, ne přes API)

- Přímý odkaz do projektu vrací `opora_read.py view` v `links` (`project`, `editor`, `hub`); parametry
  `project`, `workspace`, `screen=canvas`, `environment=editor`, `mode=structure|…`. Neskládej ho z názvu projektu.
- Zkratky: `Ctrl+Shift+,` Struktura, `Ctrl+Shift+.` Schránka zadání (dock), `Esc` zavře dock.
- Schránka nahoře přepíná disciplíny po skupinách Kreslení · Logika · Provoz (otevřená je jen zvolená skupina,
  hlavička nese počet zapnutých neuronů a kolik věcí čeká na člověka); pilulka „Čeká na tebe“ proklikává
  disciplíny s čekajícími položkami a otevře Přehled. Totéž vidí agent v API: `opora_cycle.py next --discipline`.
- Připojení složky jako projektu, přepnutí projektu/workspace v horní liště, odpojení projektu a Nastavení dělá
  člověk v okně ([navigation.md](navigation.md)); agent to nespouští.

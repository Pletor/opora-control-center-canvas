# Vzdálený přístup: aplikace zůstává doma, ven vede tunel

Cíl je jednoduchý: uživatel je v jiném městě, otevře si aplikaci na veřejné adrese a jeho
terminálový agent tam smí volat API — brát úkoly z karet a pouštět workflow. Cíl **není**
přestěhovat aplikaci někam do cloudu.

## Proč ne Vercel (ani jiný hosting funkcí)

Aplikace není stateless web. Drží se čtyř věcí, které jsou fyzicky na tomto počítači:

1. **SQLite na disku.** `registry.sqlite` a `projects/<id>/project.sqlite` (viz `database/README.md`)
   jsou soubory, na které se píše transakčně. Serverless běh nemá trvalý disk a paralelní
   instance by si o zámky rozbily hlavu.
2. **Datový kořen a repozitáře.** Projekty ukazují na skutečné složky a git worktree na tomto
   stroji (`OPORA_CANVAS_DATA`, `backend/project/workspace`). Bez nich není co číst ani co větvit.
3. **Srdce, brána a RLM.** `/api/brain/heart*`, `/api/gate*` a `/api/rlm*` spouštějí Claude Code nebo
   placené volání na **tomto** počítači pod jeho předplatným a s přístupem k jeho souborům. To se nedá provozovat z cizího datacentra.
4. **Lokální modely.** Sémantika (ONNX), Ollama a OpenViking běží na loopbacku tohoto počítače.

Proto aplikace běží dál doma a veřejnou adresu jí dá **tunel**.

## Jak to funguje

```
prohlížeč / vzdálený agent ──https──▶ Cloudflare ──tunel──▶ 127.0.0.1:8740 (tento PC)
```

`cloudflared tunnel --url http://127.0.0.1:8740` je „quick tunnel“: nepotřebuje účet ani doménu
a vrátí náhodnou adresu `https://<jméno>.trycloudflare.com`. Cloudflare drží TLS, k nám přichází
obyčejné HTTP a skutečné schéma nese hlavička `X-Forwarded-Proto`.

Tunel sám o sobě nic nechrání — kdokoli s adresou by byl uvnitř. Ochranu dělá aplikace:

### Režim se zapíná dvěma proměnnými prostředí

| Proměnná | Význam |
|---|---|
| `OPORA_PUBLIC_HOSTS` | seznam povolených jmen, oddělený čárkou; `*.trycloudflare.com` je povolená přípona |
| `OPORA_ACCESS_TOKEN` | přístupový token, nejméně 24 znaků |

Režim je aktivní **jen když jsou nastavené obě**. Bez nich se hranice chová přesně jako dřív:
Host musí být `127.0.0.1:<port>` nebo `localhost:<port>`, cokoli jiného dostane 403.
Rozhoduje o tom jediný modul `backend/app/remote_access.py`, který používá middleware
v `backend/app/factory.py`.

### Co platí pro veřejný Host

- **Token na každý `/api/*`, i na GET.** Buď `Authorization: Bearer <token>`, nebo cookie
  `opora_access` (HttpOnly, Secure, SameSite=Strict). Porovnává se v konstantním čase.
  Chybí-li nebo nesedí: `401 {"error": "Přístup vyžaduje token."}`.
- **Statika bez tokenu.** Jinak by se přihlašovací obrazovka neměla jak načíst.
- **Origin proti `https://<host>`** (schéma z `X-Forwarded-Proto`), zápisy navíc pořád chtějí
  `Content-Type: application/json`. Limit těla 2 MB, bezpečnostní hlavičky a `Cache-Control: no-store`
  zůstávají.
- **Srdce, brána, Jev a RLM jsou zvenčí zakázané.** `/api/brain/heart*`, `/api/gate*`, `/api/brain/jev*`
  a `/api/rlm*` vrací 403 „Tohle běží jen na tomto počítači.“ i s platným tokenem. Tyhle routy spouští agenta
  na tomto počítači; token otevírá aplikaci, ne řízení procesů na stroji.
- **Loopback se nemění.** Doma nic token nepotřebuje.

### Přihlášení prohlížeče

| Routa | Co dělá |
|---|---|
| `GET /api/access/status` | `{remote, authenticated, host}`; jde i bez tokenu, aby SPA věděla, co ukázat |
| `POST /api/access/login {token}` | ověří token a nastaví cookie `opora_access` |
| `POST /api/access/logout` | cookie zruší |

Frontend to obsluhuje v `frontend/app/access-gate/`: při startu se zeptá na stav a jen když je
`remote && !authenticated`, postaví přes celou obrazovku přihlašovací formulář. Když kterékoli
volání `api()` dostane 401, pošle událost okna `opora:access-required` a brána se vrátí — i uprostřed
práce. Token se nikdy neukládá do `localStorage` ani do URL; drží ho jen cookie prohlížeče.

Venku s platným přihlášením stojí dole uprostřed obrazovky malá pilulka „Vzdálený přístup · <host>“
s tlačítkem **Odhlásit**. To pošle `POST /api/access/logout`, cookie `opora_access` zmizí a brána
se hned zamkne zpátky na přihlašovací formulář s větou „Odhlášeno…“; aplikace se znovu otevře jen
tokenem. Hodí se na cizím nebo sdíleném počítači, kde se nechce čekat, až cookie vyprší. Doma
(loopback) se pilulka ani tlačítko neukážou.

## Postup (tři kroky)

```powershell
powershell -ExecutionPolicy Bypass -File tools\opora_remote.ps1
```

Skript ověří `cloudflared` (a když chybí, vypíše `winget install --id Cloudflare.cloudflared`),
vyrobí token do `.data\remote-access.token`, spustí backend se správnými proměnnými, spustí tunel,
najde veřejnou adresu a vypíše dva řádky pro vzdálený počítač. Opakované spuštění nezaloží druhý
tunel, jen znovu vypíše platnou adresu; `-Stop` tunel zastaví.

Na vzdáleném počítači potom:

```powershell
$env:OPORA_ACCESS_TOKEN = '<token z obrazovky>'
python opora_read.py --api-base https://<jméno>.trycloudflare.com status
```

## Jak s tím pracuje vzdálený terminálový agent

`opora_read.py` (skill `opora-control-center`) má dva režimy: `--base-url http://127.0.0.1:PORT`
je domácí a zůstává loopback-only, `--api-base https://HOST` je tunel a jde **jen** s tokenem
v proměnné prostředí `OPORA_ACCESS_TOKEN`. Skript pak sám posílá `Authorization: Bearer` a `Origin`.
Token se nikdy nepíše do příkazu, souboru, poznámky ani do výstupu — jinak skončí v historii shellu
a v logu agenta.

Čtení (`view`, `state`, `node-text`, `snapshot`) je stejné jako doma. Zápisy jdou přes
stejné API jako z prohlížeče, se stejnými revizemi a digesty; přes tunel je navíc potřeba hlavička
`Origin: https://<host>` a `Content-Type: application/json`. Asistent a RLM
zůstávají loopback-only — agenta obsluhuje počítač, na kterém skutečně běží.

## Na co si dát pozor

- **Kdo má adresu i token, má plný přístup pro zápis.** Žádné role, žádná jen-pro-čtení varianta.
  Token je heslo k celému plátnu; posílat ho jen zabezpečeným kanálem.
- **Výměna tokenu:** smazat `.data\remote-access.token` a spustit skript znovu. Starý token
  okamžitě přestane platit (backend se restartuje s novým) a otevřené prohlížeče dostanou 401.
- **Počítač musí zůstat zapnutý a připojený.** Uspání = aplikace je venku nedostupná.
- **Adresa quick tunelu se mění při každém spuštění.** Není to trvalá doména; starou adresu
  neber jako důkaz identity serveru. Trvalá adresa by znamenala účet u Cloudflare a pojmenovaný
  tunel — to je jiné rozhodnutí, tenhle dokument ho nepředjímá.
- **Tunel nechrání nic sám.** Bez `OPORA_ACCESS_TOKEN` by adresa byla otevřená; proto se vzdálený
  režim zapíná jen když jsou nastavené obě proměnné najednou.
- **Log tunelu** (`.data\remote-tunnel.log`) obsahuje jen adresu a stav, nikdy token. `.data` je
  v `.gitignore`, takže se token nedostane do repozitáře.

Testy hranice: `backend/app/test_remote_access.py` (`uv run pytest backend/app -q`),
rozhodnutí brány: `frontend/app/access-gate/logic/access-gate.test.ts` (`npm test`).

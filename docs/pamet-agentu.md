# Paměť agenta podle role

Agent v Opoře dosud začínal každý úkol od nuly. Karta mu dala zadání, ale nikdo si nepamatoval,
co se u stejné práce naučil minule — ani v tomhle projektu, ani v jiném. Paměť podle role tuhle
díru zavírá: **kompetence si pamatuje, projekt jen upřesňuje.**

Paměť běží v samostatném serveru **OpenViking** (HTTP na `http://127.0.0.1:1933`, API v1).
Opora ho čte a zapisuje do něj; **aplikace přes něj nikdy nespouští žádný model**. Extrakci
paměti z uzavřené session dělá OpenViking uvnitř sebe (svým vlastním LLM přes Ollama), Opora
o tom dostane jen identifikátor úlohy.

---

## Mapování: role, projekt, karta

OpenViking pojem „projekt“ ani „karta“ nezná. Zná účet, uživatele a jeho *peery*. Opora tuhle
strukturu drží v adresách a ve štítcích:

| Opora | OpenViking | Adresa |
|---|---|---|
| role agenta (`role-frontend`…) | `user` | `viking://user/{role}/memories/…` |
| projekt Opory (`draft`, `p1`…) | `peer` | `viking://user/{role}/peers/{project}/…` |
| sekce prostoru karty | resource | `viking://user/{role}/peers/{project}/resources/cards/{nodeId}/{sekce}.md` |
| poznámka / poučení / rozhodnutí | resource | `…/cards/{nodeId}/{kind}-{časová značka}.md` |

**Role** je trvalá kompetence, ne osoba a ne projekt. Seznam je verzovaný v
`library/agent-roles.json`: `role-frontend`, `role-backend`, `role-db`, `role-cloud`,
`role-cache`, `role-security`, `role-tests`, `role-architect`. Karta si roli drží v poli
`agentRole` (volitelné, výchozí `null`); starší uložený stav bez něj zůstává platný.

**Půjčka** (`lend`) je výslovný dotaz do paměti *jiné* role. Každá položka je označená
`origin: "lent:<role>"`, nikdy `self` — agent tak vidí, že si čte cizí zkušenost. Čte se
klíčem půjčující role, protože jen ten smí do její paměti.

---

## Identita: klíč na roli

OpenViking běží v režimu `auth_mode: api_key`. V něm si **identitu odvozuje z předloženého
klíče** a hlavičky `X-OpenViking-Account` / `-User` / `-Actor-Peer` už nic neurčují: buď je
ignoruje (požadavek proběhne jako uživatel toho klíče, ne jako požadovaná role), nebo je
odmítne — `X-OpenViking-Account: default` s uživatelským klíčem vrátil živě **403**.

Z toho plyne jediné pravidlo, na kterém tahle část stojí:

> **Jedna role = jeden uživatel OpenVikingu = jeden klíč.** Hlavičkou se za roli vydávat nelze.

| Klíč | Kdo ho drží | Co s ním smí |
|---|---|---|
| **správcovský** (`OPORA_OPENVIKING_ADMIN_API_KEY`) | prostředí procesu Opory | jen zakládat uživatele a obnovovat jejich klíče (`/api/v1/admin/...`) |
| **klíč role** (`role-frontend`…) | `app_settings` → `openviking.roleKeys` | veškerá data té role: vybavení, zápis, zrcadlení, session |

Správcovským klíčem může být kterýkoli klíč, který server na `/api/v1/admin/*` pustí: klíč
uživatele s **rolí `admin`** v daném účtu (ten smí zakládat uživatele jen ve svém účtu), nebo
**kořenový klíč serveru** `server.root_api_key` z `ov.conf` (ROOT, smí všude). Pozor na past:
`~/.openviking/ovcli.conf` drží klíč uživatele `admin`, jenže ten má u serveru roli `user` —
na `/admin/*` dostane `403 PERMISSION_DENIED: Requires role: root, admin`. Ověřeno živě proti
v0.4.17.1: provisioning tam projde jen s kořenovým klíčem. Kořenový klíč naopak na **datová**
API nedosáhne, takže si role svými klíči musí projít.

Klíčem role Opora **nikdy** nezakládá uživatele a správcovským klíčem **nikdy** nesahá na data
role — provisioning je jediné místo, kde se správcovský klíč použije.

### Rozdání klíčů (provisioning)

`POST /api/memory/provision {"confirmed": true}` → `MemoryService.provision_roles()`. Pro každou
roli z `library/agent-roles.json`:

1. **klíč už máme** → nechá se být (`reused`). Regenerace by zneplatnila klíč, se kterým právě
   někdo pracuje.
2. **uživatel u serveru existuje, klíč nemáme** → `POST …/users/{role}/key` vydá nový
   (`admin_regenerate_key`). Starý klíč nelze přečíst zpět; jiná pravdivá cesta není.
3. **uživatel neexistuje** → `POST …/users` ho založí s rolí `user` (`admin_register_user`).

Vrací `{status, account, provisioned:[id rolí], reused:[…], errors:[{role, reason}]}` — jen jména
rolí a důvody chyb. **Klíč se nikdy nevrací žádným API a nikdy se neloguje.** Jedna selhaná role
neshodí ostatní: výsledek je pak `partial`.

Klíče jsou **místní tajemství**. Leží v `registry.sqlite` (`app_settings`, klíč
`openviking.roleKeys`, JSON `{role: klíč}`) vedle ostatního nastavení aplikace — soubor patří
k datům, ne do gitu. Kdo ho má, má paměť všech rolí. Smazání řádku znamená jen „spusť provisioning
znovu“ (role se obnoví novým klíčem), ne ztrátu paměti.

---

## Co Opora volá

| Účel | OpenViking | Kterým klíčem |
|---|---|---|
| zdraví | `GET /health` (bez ověření; odpověď **nemá** obálku `result`) | libovolným |
| vybavení | `POST /api/v1/search/search` s `mode="list"` a `target_uri` | klíčem role |
| zápis | `POST /api/v1/content/write` (+ `POST /api/v1/content/set_tags`) | klíčem role |
| uzavření karty | `POST /api/v1/sessions` → `…/messages` → `…/commit` | klíčem role |
| stav úlohy | `GET /api/v1/tasks/{id}` | klíčem role |
| seznam uživatelů | `GET /api/v1/admin/accounts/{účet}/users` (`result` je **pole**) | správcovským |
| založení role | `POST /api/v1/admin/accounts/{účet}/users` | správcovským |
| nový klíč role | `POST /api/v1/admin/accounts/{účet}/users/{role}/key` | správcovským |

Odpověď je obálka `{status, result, time}`, chyba `{status, error:{code, message}}`.

**Proč `mode="list"` a ne `mode="context"`.** Skládací režim `context` by uměl rozpočet a
ořez sám, ale **neumí `target_uri`** — server na něj vrací 400. Paměť role se ale musí číst
rozsahově (zvlášť role, zvlášť projekt), takže Opora používá `list` a blok si skládá sama
(`MemoryService._bounded`, ≈4 znaky na token, pořadí skóre sestupně a pak URI). Obráceně platí,
že parametry jen pro `context` (třeba `peer_scope`) se do `list` neposílají — server by je
také odmítl.

---

## Co OpenViking neumí (a co s tím Opora dělá)

- **Nezná projekt ani kartu.** Opora je vyjadřuje adresou (`peers/{project}/resources/cards/{nodeId}/`)
  a štítky `k=v` (`opora=1`, `role=`, `project=`, `node=`, `kind=`, `section=`). U zprávy session
  jde projekt do těla jako `peer_id` — hlavička `X-OpenViking-Actor-Peer` v režimu `api_key` neplatí.
- **Commit je asynchronní.** `POST …/commit` vrací `task_id` a končí; extrakce běží na pozadí.
  Opora úlohu **nečeká** — uzavření karty v Opoře na výsledku paměti nestojí.
- **Nemá důvěru ani expiraci.** Položka nenese confidence ani TTL. Jediné, co Opora vydá dál,
  je `score` z vyhledání a `origin` (`self` / `project` / `lent:<role>`). Nic se nevydává jako
  ověřený fakt; paměť je popis stavu, ne pravda o kódu.
- **Extrakci dělá jeho vlastní model.** Běží uvnitř OpenVikingu (Ollama). Opora tam posílá
  data, nikdy příkaz modelu, a sama žádný model nespouští.
- **První vybavení každého dotazu je pomalé.** Nový dotaz se musí zavektorovat modelem v Ollamě;
  živě to trvalo ~21 s, tentýž dotaz podruhé 0,1 s (server si ho drží). Proto má klient dva
  stropy: 5 s (`TIMEOUT_SECONDS`) pro `health()` a správu rolí (`admin_*`), a 30 s
  (`DATA_TIMEOUT_SECONDS`) pro data — `search`, `write`, `session_*`, `task` — aby i první,
  ještě nezavektorované vybavení stihlo doběhnout, místo aby pravdivě, ale zbytečně skončilo
  jako `unavailable`. Oba stropy jde přepsat proměnnými `OPORA_OPENVIKING_TIMEOUT` /
  `OPORA_OPENVIKING_DATA_TIMEOUT`.

---

## Rozhraní Opory

`backend/api/editor/memory_routes.py`, prefix `/api/memory`:

| Metoda | Cesta | Tělo | Vrací |
|---|---|---|---|
| GET | `/status` | — | `{status, reason, url}` (+ `missingRoles` u `needs_provisioning`) |
| GET | `/roles` | — | `{roles: [{id, label, description}]}` |
| POST | `/provision` | `{confirmed}` | `{status, account, provisioned, reused, errors}` |
| POST | `/recall` | `{role, project, workspace, nodeId, query, maxTokens}` | `{status, role, items, rendered, truncated}` |
| POST | `/remember` | `{role, project, workspace, nodeId, kind, text, confirmed}` | `{status, uri, tagsApplied}` |
| POST | `/lend` | `{fromRole, toRole, query, maxTokens}` | jako recall + `fromRole` |
| POST | `/settings` | `{enabled}` | nový `/status` |

Klíče se kontrolují přesně; překlep i chybějící pole končí 409. `role: null` znamená „rozhodni
podle karty“ — server ji přečte z `agentRole` uzlu. `remember` vyžaduje `confirmed: true`, do
sdílené paměti role zapisuje člověk. `provision` vyžaduje `confirmed: true` také — zakládá
uživatele u cizího serveru.

Paměť se objevuje ještě na třech místech:

- **Balíček karty** (`node-brief`) nese `context.roleMemory = {status, role, items}`. Karta bez
  role dostane `{status: "skipped", reason: "karta nemá roli"}`. Pravidla nese node-brief
  v `boundaries` (`nodeRules`, `projectRules`); klíč `context.memory` v node-brief není.
  `context.memory.rules` patří balíčku podkladů (`packet/preview`, `packet/snapshot`) a ten
  zůstává beze změny — čte ho předání externímu agentovi. Do `orientation.readingOrder` přibude položka
  „Paměť role“ jen tehdy, když paměť opravdu něco nese.
- **Hook** (`SessionStart`) přidá krátký blok (≤ 1500 znaků) a přesný příkaz
  `… memory "<dotaz>"`, a to **jen** když je paměť `configured` a karta má roli. Bash povoluje
  podpříkaz `memory` s právě jedním argumentem do 2000 znaků.
- **Zápis na pozadí**: uložení prostoru karty ji zrcadlí (`mirror_workspace`), potvrzení
  `done.confirmed` ji předá jako session (`commit_card`). Obojí je vedlejší účinek — chyba se
  zahodí a **uložení v Opoře nikdy nespadne**.

Bootstrap klienta (`GET /api/bootstrap`) nese `memory: {enabled, status}`. Zapnutá paměť tam má
`status: "unknown"`, protože bootstrap záměrně **nevolá síť**; skutečnou dostupnost říká až
`GET /api/memory/status`.

---

## Provoz

Server se spouští z repozitáře OpenVikingu (Docker compose); **Opora ho nikdy nestartuje sama**.

| Proměnná | Výchozí | K čemu |
|---|---|---|
| `OPORA_OPENVIKING_URL` | `http://127.0.0.1:1933` | adresa; musí být `http` na loopbacku |
| `OPORA_OPENVIKING_ADMIN_API_KEY` | — | **správcovský** klíč; jen provisioning rolí |
| `OPORA_OPENVIKING_API_KEY` | — | starší název téhož; čte se, když chybí ten správcovský |
| `OPORA_OPENVIKING_ACCOUNT` | `default` | účet OpenVikingu, ve kterém role žijí |
| `OPORA_OPENVIKING_ENABLED` | vypnuto | **výchozí** poloha přepínače, než ho člověk nastaví |
| `OPORA_OPENVIKING_TRUSTED_IDENTITY` | vypnuto | posílat hlavičky identity; **jen** pro nasazení `auth_mode: trusted` |
| `OPORA_OPENVIKING_TIMEOUT` | `5.0` | timeout (s) pro `health()` a `admin_*`; přepíše `TIMEOUT_SECONDS` |
| `OPORA_OPENVIKING_DATA_TIMEOUT` | `30.0` | timeout (s) pro `search`, `write`, `session_*`, `task`; přepíše `DATA_TIMEOUT_SECONDS` |

Přepínač je nastavení **celé aplikace**, ne projektu: uložený je v `registry.sqlite` v tabulce
`app_settings` pod klíčem `openviking.enabled`. Uložená volba přebíjí výchozí hodnotu z prostředí.
Ve stejné tabulce leží pod `openviking.roleKeys` klíče rolí (viz „Identita: klíč na roli“).

Uvedení do provozu má proto tři kroky: **1.** nastavit `OPORA_OPENVIKING_ADMIN_API_KEY` a zapnout
paměť, **2.** zavolat `POST /api/memory/provision {"confirmed": true}`, **3.** ověřit
`GET /api/memory/status` = `configured`. Dokud kterákoli role nemá klíč, stav je
`needs_provisioning` a `missingRoles` říká které.

Přenos je přísný: jen `http` na loopback, bez proxy, bez
přesměrování, timeout 5 s pro zdraví a správu rolí / 30 s pro data, strop odpovědi 512 kB.

## Když paměť není

Opora zůstává plně použitelná. Každá metoda vrací pravdivý stav místo prázdného výsledku:

- `disabled` — přepínač je vypnutý; nic se nikam neposílá.
- `unavailable` — server neodpověděl (nespuštěný, špatná adresa, chyba obálky), **nebo role nemá
  klíč** (`Role nemá klíč; spusť provisioning.`). V odpovědi je důvod, položky jsou prázdné.
- `needs_provisioning` — server žije, ale chybí správcovský klíč nebo klíče rolí; `missingRoles`
  říká které. Hook ani balíček karty v tomhle stavu paměť do kontextu nepřidají.
- `skipped` — karta nemá roli, nebo není co zrcadlit.
- `configured` — server odpověděl, každá role má klíč a výsledek je jeho.

Nikdy se nevrací vymyšlený obsah, nikdy se prázdná odpověď nevydává za „role si nic nepamatuje“
a žádná z těchto situací nezabrání uložení práce v Opoře.

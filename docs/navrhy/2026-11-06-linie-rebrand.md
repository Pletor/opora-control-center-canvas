# Linie L7 – významy, důkazy a rebrand editoru

Datum: 2026-11-06, revize 2026-11-07 po druhé oponentuře. Navazuje na L6 (`2026-11-06-linie-barvy-a-zamereni.md`).
Větev `feat/velin-linie-strom-barvy-rebrand` (dítě `feat/velin-linie-strom-barvy`), kulička `OP-546BB9`. Návrh: Claude
Design, projekt `27995fdc-9d56-462e-a37d-08447c45e9d6`, soubor `Linie v3.dc.html` (živý prototyp celého cyklu; snímky
`.opora/velin-linie-v3-*.png`). Prototyp je referenční obraz chování, ne zdroj pravdy; pravdu nese tento kontrakt.

## Proč

Člověk: „Ať je to live zobrazení … posouvá, roste … Vše co umí git, musí umět i editor … spárovat úkoly s commity
a hotové plány z plátna 2, 3.“ Oponentura (6. 11.): před implementací zpřesnit význam stavů, zjednodušit výchozí pohled,
nedomýšlet nic, co data nedokazují; Pletor má vysvětlovat ověřený stav, ne ho hádat.

Tento dokument je **kontrakt významů a důkazů** (krok 1) a kontrakt rozložení a ovládání (krok 2). Kód ho provádí,
nemění.

## 1. Co je Linie a co není

- Linie **není** jiné zobrazení gitu. Git graf (`LinieGraph`) ukazuje jen git. Linie ukazuje **práci nad gitem**:
  řádek = větev, kulička = evidovaný úkol (`OP-XXXXXX`), čas zleva doprava; git je v ní jedna vrstva.
- Ve všem, co git ví, se Linie s gitem **shoduje 1:1**: commit = skutečný sha a čas, merge se kreslí jen po
  skutečném merge do skutečného cíle, větev řádku je skutečná větev, rodič podle `tree.py`.
- Vše ostatní (plán, přijetí, kontroly, nasazení, agenti, připomínky) je **evidence s vlastním zdrojem** a vlastním
  důkazem. Chybějící data znamenají „nevím“, nikdy „není“.

## 2. Stav úkolu: pět os, jeden souhrn

Kulička nemá jeden stav. Backend vrací pět os, každou s důkazem; souhrn pro graf se **vypočítá** z nich.

| Osa | Hodnoty | Důkaz |
|---|---|---|
| `work` | `not_started` · `in_progress` · `submitted` | relace agenta / commit na větvi / hlášení `linie report` |
| `checks` | `missing` · `running` · `passed` · `failed` – vždy **pro konkrétní sha** | výstup `report --check`, CI, `npm test` |
| `acceptance` | `pending` · `accepted` · `stale` (přijato pro jiný sha než HEAD) | záznam přijetí člověkem (`accept` s sha) |
| `integration` | `none` · `merged` **do konkrétního cíle** | merge commit v gitu (sha, cíl) |
| `deploy` | `{ env: sha }` – kde běží která revize | událost nasazení z prostředí, ne tag |

### 2a. Jedno vyhodnocení

Souhrn, jeho pravidlo (`reason`), **další krok** (`next`), výrok Pletora i **povolené akce** (`allowed` / `blocked` s
důvodem) vznikají v **jedné funkci** nad týmiž důkazy (`evaluate(ticket) → {key, text, reason, next, allowed, blocked}`).
Nikdy nesmí detail říkat „člověk znovu přijme“, když pravidlo akci `accept` zakazuje. Testy ověřují, že pro každý
klíč souhrnu je `next` konzistentní s `allowed`.

Vyhodnocuje se **nejdřív aktuální pokus a revize (HEAD = poslední neopuštěný commit pokusu), teprve pak celý úkol**.
`checks` a `acceptance` platí jen pro sha, pro které byly zaznamenány; pro jiný HEAD jsou „chybí“ / „zastaralé“.
Historické začlenění nepřebije novou, dosud nezačleněnou revizi: má-li úkol commit po `integration.at`, hodnotí se
nová revize a souhrn nese předponu „nová revize po začlenění <sha>“.

Pořadí pravidel (první platné vyhrává):

| Klíč | Podmínka | Další krok | `allowed` |
|---|---|---|---|
| `blocked` | ruční block | člověk odblokuje | `unblock` |
| `merged` | `integration.merged` ∧ žádný commit po `integration.at` | nasazení potvrdí prostředí; jinak „nenasazeno, nevím“ | – |
| `todo` | `work.not_started` | kancelář založí pokus | `attempt` |
| `wip` | `work.in_progress`; bez živé relace = „probíhá (neověřeno)“ | agent odevzdá / agent se přihlásí | – |
| `failed` | `work.submitted` ∧ `checks.failed(HEAD)` | agent opraví a odevzdá novou revizi | – |
| `nocheck` | `work.submitted` ∧ (`checks.missing` ∨ `checks.sha ≠ HEAD`) | CI ověří HEAD; bylo-li přijetí pro starší sha, teprve pak nové přijetí | – |
| `checking` | `work.submitted` ∧ `checks.running(HEAD)` | čekáme na CI | – |
| `stale` | `checks.passed(HEAD)` ∧ `acceptance.accepted(sha ≠ HEAD)` | člověk znovu přijme HEAD | `accept` |
| `pending` | `checks.passed(HEAD)` ∧ `acceptance.pending` | člověk rozhodne | `accept` |
| `accepted` | `checks.passed(HEAD)` ∧ `acceptance.accepted(HEAD)` ∧ `integration.none` | služba začlení do rodiče (znovu ověří) | `merge` |

Nasazení se do souhrnu nikdy nemíchá; je to vlastní značka. `block`/`unblock` je povolen vždy.

Zakázané zkratky (dnešní kód je částečně používá, L7 je odstraní):

| Zkratka | Správně |
|---|---|
| push = hotovo | push = revize dostupná na originu; hotovo = `work.submitted` + `checks.passed` pro ten sha |
| zahozený commit = revert | `abandoned` je rozhodnutí o práci (kostka s ✕, `work` jde dál); revert je nový commit v gitu |
| stash = odložená kulička | `parked` je rozhodnutí o úkolu; stash Linie neeviduje |
| tag = nasazeno | tag je značka revize; `deploy` jen z potvrzení prostředí (`POST /deploy {env, sha}`) |
| worktree = agent | worktree je adresář; agent je časově omezená vazba `{agent, worktree, from, to}` |

## 3. Identita a vazby (datový kontrakt, ne prototypová zkratka)

- **Úkol** (`ticket`, `OP-…`) má stabilní identitu a `planCardId` (karta plátna 3) a přes ni `directionCardId`
  (karta plátna 2). Jeden úkol může mít **víc pokusů** (`attempts[]`: větev, agent, relace, od–do), víc PR, víc
  repozitářů; jeden PR může řešit víc úkolů (`prs[]` s `ticketIds[]`).
- Vazba úkol ↔ git artefakt je buď **potvrzená** (trailer `Opora-Mark` v commitu, PR založený službou, `report`
  s sha) nebo **navržená** (shoda jména větve / textu) a navržená se kreslí tečkovaně a nikdy nevstupuje do souhrnu.
- **Značka propojuje práci, nedokazuje operaci.** Squash, merge, revert, rebase a stav PR se čtou jen ze **záznamu
  služby OPORY** (merge log s `{ticket, source_sha, target, result_sha, mode}`) a od **poskytovatele PR**; stejná značka
  ve více commitech je obyčejný průběh práce, změna sha není rebase a posun cílové větve není rebase. Co není v záznamu,
  je `unconfirmed` a UI to píše „neověřeno“, nikdy jako fakt.
- Každý důkaz nese **zdroj** (`git log`, `CI`, `záznam přijetí`, `merge log`, `GitHub`, `agent-office`, `událost
  prostředí`) a UI ho ukazuje u každé osy.
- Kulička má v každém seskupení touž identitu a výběr; nikam „nepřeskakuje“. V pohledu podle větví leží na větvi
  posledního pokusu, v pohledu podle plánu u své karty plátna 3.

## 4. Společné API pro editor i Pletora

`GET /api/pletor/linie/board` (rozšíření) a `GET /api/pletor/linie/work/{id}` vrací pro každý úkol:

```json
{
  "id": "tk_…", "mark": "OP-546BB9", "planCardId": "…", "directionCardId": "…",
  "axes": { "work": {...}, "checks": {...}, "acceptance": {...}, "integration": {...}, "deploy": {...} },
  "summary": { "text": "čeká na přijetí 1aebfc1", "reason": "work.submitted & checks.passed & acceptance.pending" },
  "evidence": [ { "kind": "commit|pr|check|accept|deploy|session", "ref": "…", "url": "…", "at": "…" } ],
  "summary": { "key": "pending", "text": "…", "reason": "…", "next": "Člověk rozhodne o přijetí 1aebfc1." },
  "allowed": ["accept", "block"], "blocked": { "merge": "acceptance.pending – nejdřív přijetí" },
  "incomplete": ["deploy", "prs"],
  "attempts": [...], "prs": [...], "commits": [...], "notes": [...]
}
```

a celý board nese `snapshot: { id, builtAt, sources: { git: {verifiedAt, ok}, prs: {...}, checks: {...}, sessions:
{...}, deploy: {...} } }`. **Čas sestavení snímku a čas posledního úspěšného čtení každého zdroje jsou dvě různé
věci**; obnovení stránky ani nový render je neomlazuje a stejný `snapshot.id` neznamená, že zdroje byly čteny současně.
Zdroj starší než práh (výchozí 10 min) je v UI „zastaralé“ a jeho osy padají do `incomplete`. Pletor smí tvrdit jen to,
co je v `axes` + `evidence`, vždy se zdrojem a stářím: „L6 čeká na přijetí revize 1aebfc1. Kontroly této revize prošly
(CI, před 2 min). Začlenění ani nasazení potvrzené nemám. Stav PR neznám, GitHub neodpověděl (před 16 min).“ Každé
tvrzení je proklik na důkaz; `next` je týž text jako v detailu. Operace (`accept`, `merge`, `block`, `abandon`, `park`,
`attempt`) backend při provedení **znovu ověří** proti aktuálnímu gitu; nesoulad = 409 s důvodem.

### 4a. Žádost srdci (člověk → Pletor → srdce → plátno 3 → ticket → kancelář)

`POST /api/pletor/requests {text, idempotencyKey}` vrátí ihned `{id, steps: [accepted]}` a zapíše do deníku jen
„žádost přijata“. Kroky `plan` (srdce doplnilo kartu plátna 3), `ticket` (kulička založena), `attempt` (relace
kanceláře, větev), `commit` se do žádosti i do deníku přidají **až po skutečném potvrzení** každého z nich a každý nese
`{at, by, evidence}`. Selhání kroku zůstává viditelné (`failed`, `why`); opakování se posílá se stejným klíčem a backend
nevytvoří druhý ticket, pokus ani větev (kontrola podle klíče a jména větve). Žádost je zobrazená v panelu Pletora jako
řetězec kroků a ve frontě „Pletor“ jako „N otevřených žádostí“.

## 5. Git vrstva: co editor ukazuje

Vše, co git má, se dá v Linii vidět; nic se nedělá přímo gitem z prohlížeče.

| Git | V Linii | Zdroj |
|---|---|---|
| commit | kostka na čáře práce; sha při přiblížení; hover sha · zpráva · čas · úkol | `git log` větve |
| větev / rodič | řádek a strom (L5) | `tree.py` |
| merge | plný oblouk do cíle + bod; barva cíle | merge commit |
| PR otevřený | pilulka `PR #350` na čárkované šipce plánu; stav review barvou | GitHub API (když nedostupné: `incomplete: ["prs"]`, pilulka šedá „neověřeno“) |
| PR sloučený | oblouk merge nese číslo PR | GitHub + merge commit |
| squash merge | oblouk z posledního commitu práce do jednoho commitu cíle; kostky práce zůstávají, cíl má jednu | merge log služby (`mode: squash`); bez záznamu „začleněno · způsob neověřen“ |
| revert | nová kostka se šipkou zpět k revertovanému sha | záznam služby `revert {sha}`; commit s `This reverts` je jen navržená vazba |
| rebase / posunutý cíl | kostky se přesunou; tenká stopa „bylo zde“ do dalšího snímku; `acceptance.stale` | záznam služby `rebase {from, to}`; pouhá změna sha nebo posun cíle rebase nedokazuje |
| tag | svislá značka na řádku s názvem | `git tag` |
| nasazení | značka `env@sha` na řádku cíle, jen z potvrzení prostředí | `POST /deploy` |
| worktree | pruh pod osou větve, tečkovaná odbočka; při vazbě na agenta jméno agenta a od–do | `git worktree list` + relace |
| opuštěná práce | kostka s ✕ a odbočkou; souhrn úkolu nezmění | `abandon {sha, why}` |

Operace přes službu OPORY (každá zapíše do deníku, každá se znovu ověří): založit pokus (větev z rodiče podle jména),
otevřít PR, přijmout (s sha), začlenit (`linie.py merge`), označit opuštěné, zaparkovat, blokovat, potvrdit nasazení.
Interaktivní rebase a force-push editor neumí záměrně.

## 6. Rozložení a ovládání (L7 UI)

- **Fronty odpovědnosti** nad lištou: Člověk · Pletor · Srdce · Tickety · Kancelář · Git. Nejsou to fáze výrobního
  pásu, ale pohledy na to, **kdo má míč**: člověk vstupuje znovu při každém přijetí, kontrola vrací práci kanceláři,
  jedna kulička může být ve dvou frontách (čeká na přijetí člověka a zároveň má otevřený PR). Každý počet má jednotku
  („3 rozhodnutí“, „2 otevřené žádosti“, „5 plánů“, „0 ticketů“, „4 úkoly“, „2 PR“), nikdy holé číslo. Klik na frontu
  ztlumí vše ostatní, nemění měřítko ani posun.
- **Panel Pletora** vpravo nahoře: výrok z jednoho vyhodnocení (§2a) včetně „Další krok“, pak čas sestavení snímku a
  stáří každého zdroje zvlášť (zastaralé zvýrazněno), povolené akce (zakázané šedé s důvodem z téhož pravidla), pole
  „Zadat srdci“ a pod ním řetězce žádostí (§4a) s kroky přijato · plán · ticket · relace · commit; selhání červeně,
  opakování se stejným klíčem.
- **Čitelnost**: základní písmo 13,5 px, popisky kuliček 11,5 px, vedlejší texty kontrastem ≥ 4,5:1 (`--dim` světlejší
  než dnes), názvy kuliček zkráceny až po 34 znacích, celé v detailu.
- **Jeden posuvný prvek**: sticky časová hlavička nahoře, sticky sloupec názvů vlevo, výška ze zbývajícího prostoru
  (žádné `100vh − 230px`). Název leží na ose linky, jeden řádek textu s výpustkou, celé jméno v detailu. Šířka názvů
  tažením (160–420 px, `localStorage pletor.linie.names`), pod 1100 px úzký režim a detail jako překryv.
- **Společná časová souřadnice**, žádný `MIN_GAP` posouvající čas. Kolize řeší jen popisky: přednost vybrané kuličce,
  pak střídání nad/pod, nejvýš **dvě patra**, dál shluk „+N“ s plným výčtem v detailu; při oddálení seskupení.
  Řádek s pruhy worktree pod osou má popisky kuliček **jen nad osou** (pruhy a jejich jména jsou pod ní); pilulka PR na
  merge oblouku leží u cíle (65 % délky), ne ve středu, aby nepřekrývala popisek zdrojové kuličky.
- **Poloha výběru je stálá**: přepnutí vrstvy, sbalení řádku, seskupení i automatické rozbalení pruhů worktree pro
  vybranou kuličku se kompenzuje posunem (`scrollTop += Δy vybrané kuličky`); pruhy se otvírají pod osou, takže osa
  vlastního řádku se nehne.
- **Přiblížení**: kolečko nad grafem = čas blíž/dál kolem kurzoru (do 15 min přes plátno), Shift+kolečko a boční
  kolečko = posun, tažení = ruka všemi směry, `Vše`, `Teď`, `↻ Výchozí`. Značky osy 5 min … 6 h podle hustoty.
- **Orientace se nemění sama**: klik, detail ani živá aktualizace nesmí změnit měřítko ani odsunout výběr. Automatický
  posun jen při zapnutém „Sledovat živě“ (výchozí vypnuto); nové události přibývají bez posunu.
- **Výběr**: okamžitý klik (žádných 250 ms), stabilní prstenec + zvýrazněný řádek (bez trvalého pulzování), detail se
  otevře. `⌖ Zaměřit` a `✎`/F2 jako samostatné ovládací prvky s plochou ≥ 24 px. Esc zavře nejbližší vrstvu
  (přejmenování → detail → nic) a označí událost za zpracovanou (`stopPropagation`), Velín ji nedostane.
- **Vrstvy a výchozí pohled**: výchozí = větve, kuličky, souhrn a ověřené začlenění. Commity, worktree, plány ostatních
  kuliček a tagy jsou vrstvy (přepínač v liště, uloženo pro aplikaci); pro vybranou kuličku se její commity, plán a
  worktree ukážou vždy. Deník dole **výchozí sbalený** s počtem nových událostí.
- **Písmo**: názvy a texty běžným písmem aplikace, monospace jen pro sha, značky OP a větve.
- **Seskupení řádků**: `podle větví` (strom L5) · `podle plánu` (řádek = karta plátna 2, pod ní kuličky plátna 3,
  úkoly bez pokusu šedé na řádku plánu). Drobek nad detailem: plátno 2 › plátno 3 › kulička, klik otevře kartu.
- **Detail kuličky** (záložky): Souhrn a osy s důkazy · Plán (text karty plátna 3, kritéria) · Git (pokusy, commity,
  PR, merge) · Relace agentů · Připomínky a vylepšení (pole + „Zapsat připomínku“ / „Navrhnout vylepšení“, zápis jde do
  deníku i do kuličky, agent ho vidí v `node-brief`).
- **Deník**: každá událost (kulička, commit, stav, přijetí, merge, PR, opuštěno, fork, worktree, nasazení, připomínka)
  s časem, značkou, textem a větví; klik označí kuličku. Zdroj: evidence backendu, ne jen prohlížeč.
- **Živost**: vznik kuličky (krátké zvětšení), nakreslení merge jednou, růst čáry práce; žádné trvalé animace šipek.
  `prefers-reduced-motion` vše vypne.

## 7. Pořadí stavby (vlak PR, každý sloučitelný sám)

1. **Kontrakt významů a důkazů** – tento dokument + `axes`/`evidence`/`snapshotId` v backendu (`work.py`, `board.py`,
   modely), testy pravidla souhrnu včetně `stale`, squash, chybějící GitHub.
2. **L7 rozložení a ovládání** – frontend podle §6 na větvi `…-rebrand`; vitest na kolize popisků, souhrn, Esc, zoom.
3. **Napojení skutečných dat** – PR, tagy, worktree, opuštěné, nasazení; co není evidováno, nese `incomplete` a v UI
   „neověřeno“.
4. **Vazby na plán** – `planCardId`, `directionCardId`, seskupení podle plánu, drobek; společný board pro Pletora.
5. **Operace a pokročilé události** – přijetí s sha, PR ze služby, opuštěno/parkování/nasazení, revert a rebase stopy.

## 8. Ověření před přijetím

Scénáře, na kterých se pozná spolehlivost (každý má test nebo živou sondu na náhledu):
nová revize po schválení bez kontrol (→ `nocheck`, další krok „CI ověří HEAD“, `accept` zakázán), nová revize po
schválení s kontrolami (→ `stale`, `accept` povolen), commit po začlenění (→ hodnotí se nová revize, ne `merged`),
posunutý cíl merge (→ 409 při merge; rebase jen ze záznamu služby), squash merge (→ jeden commit cíle, oblouk
z posledního commitu práce, `mode: squash` z merge logu), nedostupný GitHub (→ `incomplete: ["prs"]`, pilulka
„neověřeno“, zdroj PR „zastaralé“, souhrn bez PR), agent bez aktuální relace (→ „probíhá (neověřeno)“), nasazená jiná
revize než HEAD (→ značka `env@sha` na starším sha, souhrn beze změny), obnovení stránky (→ stáří zdrojů se nezmění),
žádost srdci se selháním relace (→ krok `failed` viditelný, opakování stejným klíčem nevytvoří druhý pokus), pro každý
klíč souhrnu `next` ⇔ `allowed` (tabulka §2a).

Před hlášením hotovo každého PR: `uv run pytest backend/agi_pletor backend/api/agi_pletor -q`, `npm test`, `npm run build`,
živě na náhledu z Velína, `linie.py report`.

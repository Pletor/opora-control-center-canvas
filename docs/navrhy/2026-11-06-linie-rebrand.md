# Linie L7 – významy, důkazy a rebrand editoru

Datum: 2026-11-06. Navazuje na L6 (`2026-11-06-linie-barvy-a-zamereni.md`). Větev `feat/velin-linie-strom-barvy-rebrand`
(dítě `feat/velin-linie-strom-barvy`), kulička `OP-546BB9`. Návrh: Claude Design, projekt
`27995fdc-9d56-462e-a37d-08447c45e9d6`, soubor `Linie v2.dc.html` (živý prototyp; snímky `.opora/velin-linie-v2-*.png`).

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

Souhrn (`summary`) a jeho pravidlo, v tomto pořadí:
`blokováno` (ruční block) → `začleněno do <cíl>` (integration.merged) → `čeká na přijetí <sha>` (work.submitted ∧
checks.passed ∧ acceptance.pending) → `přijetí zastaralo` (acceptance.stale) → `kontroly selhaly <sha>` →
`odevzdáno, bez kontrol` → `probíhá` → `nezačato`. Nasazení se do souhrnu nikdy nemíchá; je to vlastní značka.

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
  "verifiedAt": "…", "incomplete": ["deploy", "checks"],
  "allowed": ["accept", "merge", "block"], "blocked": { "merge": "acceptance.pending" },
  "attempts": [...], "prs": [...], "commits": [...], "notes": [...]
}
```

a celý board nese `snapshotId` (stejný snímek pro graf, detail i Pletora). Pletor smí tvrdit jen to, co je v `axes`
+ `evidence`, a vždy s `verifiedAt`: „L6 čeká na přijetí revize 1aebfc1. Kontroly této revize prošly. Začlenění ani
nasazení potvrzené nemám. Ověřeno před minutou.“ Každé tvrzení je proklik na důkaz. Operace (`accept`, `merge`,
`block`, `abandon`, `park`, `attempt`) backend při provedení **znovu ověří** proti aktuálnímu gitu; nesoulad = 409
s důvodem.

## 5. Git vrstva: co editor ukazuje

Vše, co git má, se dá v Linii vidět; nic se nedělá přímo gitem z prohlížeče.

| Git | V Linii | Zdroj |
|---|---|---|
| commit | kostka na čáře práce; sha při přiblížení; hover sha · zpráva · čas · úkol | `git log` větve |
| větev / rodič | řádek a strom (L5) | `tree.py` |
| merge | plný oblouk do cíle + bod; barva cíle | merge commit |
| PR otevřený | pilulka `PR #350` na čárkované šipce plánu; stav review barvou | GitHub API (když nedostupné: `incomplete: ["prs"]`, pilulka šedá „neověřeno“) |
| PR sloučený | oblouk merge nese číslo PR | GitHub + merge commit |
| squash merge | oblouk z posledního commitu práce do jednoho commitu cíle; kostky práce zůstávají, cíl má jednu | detekce podle `Opora-Mark` v squash commitu |
| revert | nová kostka se šipkou zpět k revertovanému sha | commit s `Revert` + `This reverts` |
| rebase / posunutý cíl | kostky se přesunou; tenká stopa „bylo zde“ do dalšího snímku; `acceptance.stale` | změna sha při stejném `Opora-Mark` |
| tag | svislá značka na řádku s názvem | `git tag` |
| nasazení | značka `env@sha` na řádku cíle, jen z potvrzení prostředí | `POST /deploy` |
| worktree | pruh pod osou větve, tečkovaná odbočka; při vazbě na agenta jméno agenta a od–do | `git worktree list` + relace |
| opuštěná práce | kostka s ✕ a odbočkou; souhrn úkolu nezmění | `abandon {sha, why}` |

Operace přes službu OPORY (každá zapíše do deníku, každá se znovu ověří): založit pokus (větev z rodiče podle jména),
otevřít PR, přijmout (s sha), začlenit (`linie.py merge`), označit opuštěné, zaparkovat, blokovat, potvrdit nasazení.
Interaktivní rebase a force-push editor neumí záměrně.

## 6. Rozložení a ovládání (L7 UI)

- **Jeden posuvný prvek**: sticky časová hlavička nahoře, sticky sloupec názvů vlevo, výška ze zbývajícího prostoru
  (žádné `100vh − 230px`). Název leží na ose linky, jeden řádek textu s výpustkou, celé jméno v detailu. Šířka názvů
  tažením (160–420 px, `localStorage pletor.linie.names`), pod 1100 px úzký režim a detail jako překryv.
- **Společná časová souřadnice**, žádný `MIN_GAP` posouvající čas. Kolize řeší jen popisky: přednost vybrané kuličce,
  pak střídání nad/pod, nejvýš **dvě patra**, dál shluk „+N“ s plným výčtem v detailu; při oddálení seskupení.
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
nová revize po schválení (→ `acceptance.stale`), posunutý cíl merge (→ 409 při merge, stopa rebase), squash merge
(→ jeden commit cíle, oblouk z posledního commitu práce), nedostupný GitHub (→ `incomplete: ["prs"]`, šedé pilulky,
souhrn bez PR), agent bez aktuální relace (→ `work.in_progress` bez důkazu relace = „neověřeno“), nasazená jiná revize
než HEAD (→ značka `env@sha` na starším sha, souhrn beze změny).

Před hlášením hotovo každého PR: `uv run pytest backend/agi_pletor backend/api/agi_pletor -q`, `npm test`, `npm run build`,
živě na náhledu z Velína, `linie.py report`.

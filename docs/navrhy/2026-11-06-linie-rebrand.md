# Linie L7 – významy, důkazy a rebrand editoru

Datum: 2026-11-06, revize 2026-11-07 po druhé oponentuře. Navazuje na L6 (`2026-11-06-linie-barvy-a-zamereni.md`).
Větev `feat/velin-linie-strom-barvy-rebrand` (dítě `feat/velin-linie-strom-barvy`), kulička `OP-546BB9`. Návrh: Claude
Design, projekt `27995fdc-9d56-462e-a37d-08447c45e9d6`, soubor `Linie v3.dc.html` (živý prototyp celého cyklu; snímky
`.opora/velin-linie-v3-*.png`). Prototyp je referenční obraz **vzhledu a ovládání** (přebírá se 1:1); **význam dat a
operací** nese tento kontrakt. Simulace prototypu (ukázkový scénář, náhodná sha, vymyšlené zdroje) ani jeho známé
chyby se nepřebírají. Přijetí jednotlivých vozů není přijetí Linie; to přijde až po ověření společného UI a API podle §8.

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

Vyhodnocuje se **nejdřív aktuální pokus a revize (HEAD = skutečná špička větve pokusu podle gitu / `headSha`
z hlášení), teprve pak celý úkol**. Označení commitu jako opuštěného HEAD nemění (viz §5): editor i Pletor vždy hodnotí
kód, který na větvi skutečně leží.
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
| `accepted` | `checks.passed(HEAD)` ∧ `acceptance.accepted(HEAD)` ∧ `integration.none` | bez povolení: člověk povolí začlenění; s povolením platným pro dvojici (HEAD, špička cíle): služba začlení (znovu ověří) | `allow_merge` → po povolení `merge`; posun cíle vrací `allow_merge` |

HEAD se bere ze **skutečné špičky větve** (git), ne z posledního hlášení: commit bez hlášení znamená `work.in_progress`
pro novou revizi a kontroly i přijetí starší revize pro ni neplatí; `accept(sha)` s jiným sha než špička = 409
`head_moved`. Povolení začlenění platí pro dvojici `(sourceSha, targetSha)`; když se cíl posune, povolení propadá a
pravidlo nabídne nové. Při nedostupném gitu zůstává poslední známá špička a `incomplete` nese `git`.

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
| PR otevřený | pilulka `PR #350` na čárkované šipce plánu; stav review barvou | GitHub API; při výpadku zůstává **poslední známý stav** označený „zastaralé · nyní neověřeno“, `incomplete: ["prs"]`; zdroj nese `lastSuccessAt` i `attemptedAt` zvlášť; výpadek PR nikdy nezneplatní začlenění doložené merge logem |
| PR sloučený | oblouk merge nese číslo PR | GitHub + merge commit |
| squash merge | oblouk z posledního commitu práce do jednoho commitu cíle; kostky práce zůstávají, cíl má jednu | merge log služby (`mode: squash`); bez záznamu „začleněno · způsob neověřen“ |
| revert | nová kostka se šipkou zpět k revertovanému sha | záznam služby `revert {sha}`; commit s `This reverts` je jen navržená vazba |
| rebase / posunutý cíl | kostky se přesunou; tenká stopa „bylo zde“ do dalšího snímku; `acceptance.stale` | záznam služby `rebase {from, to}`; pouhá změna sha nebo posun cíle rebase nedokazuje |
| tag | svislá značka **u commitu** (lehký i anotovaný); tag patří objektu, ne větvi – řádek, na kterém se kreslí, je prezentační volba (větev, kde commit leží první), ne vlastnictví | `git for-each-ref refs/tags` |
| nasazení | značka `env@sha` na řádku cíle. Zápis nasazovacím skriptem po ověření běžící revize = „potvrzeno prostředím“; ruční zápis z Velína = „hlášeno člověkem“ a nikdy se netváří jako potvrzení prostředí; backend ověří oprávnění zapisujícího pro dané prostředí | `POST /deploy {env, sha, by}` |
| worktree | pruh pod osou větve, tečkovaná odbočka. Jméno agenta a od–do jen při **explicitní vazbě** relace na pokus `{ticket, attempt, repo, worktree}` s aktuálním heartbeat/lease; samotný výpis `git worktree list` dává jen adresář bez agenta a bez od–do | `git worktree list --porcelain` + vazba relace |
| opuštěná práce | kostka s ✕ a odbočkou; **evidence rozhodnutí**, nemění git, HEAD ani osy: opuštěný commit může zůstat předkem HEAD a jeho změny v kódu; odstranění změn je samostatná git operace (revert) | `abandon {sha, why}` |

### 5a. Merge log a nasazení přežijí částečné selhání

- Každé začlenění službou má **identifikátor operace** a dva záznamy: `started {op, ticket, repo, source_sha, target,
  target_sha_before, mode, by, at}` před gitem a `finished {op, result_sha, ok, at}` po ověření výsledku v gitu.
  Opakovaný požadavek se stejným `op` (nebo stejnou dvojicí `source_sha` → `target`, která už má `finished.ok`) **neprovede
  další merge**, jen vrátí záznam. Záznam `started` bez `finished` je „operace zahájena, výsledek neověřen“ a UI ho tak píše.
- Historie se **nedopočítává** jako záznam operace služby. Starší začlenění lze doložit gitem (merge commit, `--is-ancestor`)
  nebo GitHubem (PR merged) a důkaz nese tento původ (`src: git` / `src: GitHub`); způsob (squash/merge) bez záznamu zůstává
  „způsob neověřen“. Neexistence merge logu sama o sobě nedokazuje ani začlenění, ani jeho absenci.
- Živá relace dokazuje aktivitu jen s explicitní vazbou na pokus (úkol, pokus, repozitář, worktree) a čerstvým heartbeat;
  „agent někde běží“ nestačí.
- Nová data **nezapínají uživateli vrstvy**: zpřístupní přepínač a obnoví obsah, zvolená viditelnost i poloha grafu zůstávají.

Operace přes službu OPORY (každá zapíše do deníku, každá se znovu ověří): založit pokus (větev z rodiče podle jména),
otevřít PR, přijmout (s sha), začlenit (`linie.py merge`), označit opuštěné, zaparkovat, blokovat, potvrdit nasazení.
Interaktivní rebase a force-push editor neumí záměrně.

## 6. Rozložení a ovládání (L7 UI)

- **Fronty odpovědnosti** nad lištou: Člověk · Pletor · Srdce · Tickety · Kancelář · Git. Nejsou to fáze výrobního
  pásu, ale pohledy na to, **kdo má míč**: člověk vstupuje znovu při každém přijetí, kontrola vrací práci kanceláři,
  jedna kulička může být ve dvou frontách (čeká na přijetí člověka a zároveň má otevřený PR). Každý počet má jednotku
  („3 rozhodnutí“, „2 otevřené žádosti“, „5 plánů“, „0 ticketů“, „4 úkoly“, „2 PR“), nikdy holé číslo. Klik na frontu
  ztlumí vše ostatní, nemění měřítko ani posun.
- **„Čeká na tebe“** (L7g): klik na frontu Člověk neukazuje jen ztlumený graf, ale nad grafem **seřazený seznam
  rozhodnutí**. Pořadí počítá služba, ne prohlížeč: vůz, který blokuje ostatní, první; jinak zdola nahoru po stromu
  (nejhlubší dítě dřív), pak stáří. Každý řádek: název, revize, co je ověřené (kontroly, shoda náhledu), věta „začlení
  `X` do `Y`, pak bude na řadě `Z`“ a **jedno tlačítko „Přijmout a začlenit“**, které provede `accept` → `allow_merge`
  → `merge` v jednom kroku služby (`POST /work/{id}/accept-merge`, idempotentní podle `op`, zastaví se na prvním 409 a
  vrátí důvod větou). Když to nejde (posunutý cíl, chybějící kontroly, cizí revize), řádek říká proč a nabídne
  **jedinou** opravnou akci (znovu přijmout špičku, spustit kontroly), nikdy tři tlačítka ve třech stavech. Prázdný
  stav: „Nic nečeká na tebe. Pracují: …“. Graf a detail kuličky slouží ke zkoumání, ne k rozhodování. Důvod: člověk
  2026-11-07 nevěděl, co a v jakém pořadí slučovat, a zaseklé povolení z posunutého cíle nešlo v UI opravit.
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
3. **Napojení skutečných dat (L7c)** – merge log s `op`/`started`/`finished` (§5a), PR s posledním známým stavem a
   `lastSuccessAt`, tagy u commitu, nasazení s původem (prostředí / člověk) a oprávněním, worktree s explicitní vazbou
   relace, `abandon` jako evidence bez změny HEAD; co není evidováno, nese `incomplete` a v UI „neověřeno“. Testy: abandon
   zachová HEAD a přidá důvod; výpadek GitHubu nechá poslední stav PR jako zastaralý a nezneplatní merge log; opakovaný
   merge se stejným `op` nic neprovede; tag ≠ nasazení; worktree bez vazby nemá agenta; příchod dat nemění vrstvy ani posun.
4. **Vazby a revize plánu (L7d)** – zjištěno v kódu (7. 11.): tělo ticketu je od vydání neměnné (`tickets.body` nemá
   UPDATE), ale `machine.cardId` plní jen srdce a `cardVersion` posílá klient bez ověření; karta plánu nemá v datech rodiče
   na plátně 2 (rodokmen existuje jen u knihovny `derived_from`, typované spojení je jen `machine.intent.workflowVersionId`).
   Proto:
   - **Vydání práce zmrazí referenci** `issued: {cardId, cardRevision, at}`; `cardRevision` čte server z karty při
     vydání, ne z klienta. Snímek textu a kritérií v `body` zůstává (už dnes). Detail ukáže rozdíl proti aktuální kartě.
     Nové zadání = nová revize ticketu, historie se nepřepisuje.
   - **Přijetí platí pro dvojici** `(sha, cardRevision)`: změna kritérií na kartě při stejném sha dává
     `acceptance.state = 'stale_plan'` s důvodem; staré přijetí zůstává historickým záznamem.
   - **Vazba se ověřuje**, ne prohlašuje: `planCardId` jen když karta existuje v projektu a je na plátně plánu;
     `directionCardId` přes `workflowVersionId` (plátno 2). Stavy vazby: `none` („bez plánu“), `card_missing`,
     `source_unavailable`, `ambiguous` – jen první znamená „bez plánu“.
   - **Seskupení je jiný pohled na týž snímek** (`snapshot.id` se nemění, žádné nové čtení); výběr a časový rozsah
     zůstávají, svislá poloha se kotví k vybrané kuličce.
   - **Počty front mají definici**: „Srdce: N plánů čeká na rozpracování“ = karty plánu bez vydaného ticketu;
     „Tickety: N ticketů čeká na pokus“ = `summary.key = todo`; agregace nad týmž projektem, filtrem a snímkem jako graf.
   - Testy: změna kritérií bez změny sha → `stale_plan`; karta smazána ≠ bez plánu; přepnutí seskupení nezmění `snapshot.id`.
5. **Operace a žádosti (L7e)** – zjištěno v kódu: větev dnes zakládá agent, služba git jen čte (`work.create`), rozlišení
   lokální/publikovaná se neukládá; `block/defer/resume` běží bez gitu, ale nezapisují `by`; brána ani tickety nemají
   idempotenční klíč (vzor `request_id + digest` je v `opora_execution_budgets`, `opora_execution_pull_requests`);
   doménový deník neexistuje (`activity_log` je ořezávaný HTTP log, `opora_events` je trvalý outbox s `id`
   AUTOINCREMENT); revert/rebase v Linii nikde není. Proto:
   - **Pokus** (`attempt`) eviduje `{repo, baseRef, baseSha, branch, createdBy: agent|service, published: bool}`; větev
     dál zakládá agent z přiděleného `baseSha`, služba ověří skutečný výsledek při `report` (`merge-base` na `baseSha`,
     existence `refs/remotes/origin/<branch>` → `published`). Jméno větve rodiče jen **nabízí**; operace přijme a ověří
     `repository`, `baseRef`, `baseSha`, `target`. Existující větev se nepřevezme bez ověření a nikdy nepřepíše.
   - **Operace a git**: `accept`, `merge`, `revert`, `attempt` vyžadují git a znovu ověří HEAD; `block`, `park`, `unblock`,
     `resume`, `abandon` běží i při výpadku gitu, ověřují jen oprávnění a revizi evidence a zapisují `by`.
   - **Idempotence každého kroku**: klíč + digest obsahu; stejný klíč se stejným obsahem vrátí týž záznam, s jiným obsahem
     409 `idempotency_conflict`. Po pádu mezi založením větve/PR a zápisem evidence se služba zotaví porovnáním s gitem
     a GitHubem bez duplikace (`started`/`finished` jako u merge logu §5a).
   - **Žádost srdci (§4a)** se může větvit: jedna žádost → více ticketů a pokusů; řetězec `plan → ticket → attempt →
     commit` je souhrn skutečně propojených záznamů; trailer `Opora-Mark` určuje vazbu, nepotvrzuje splnění žádosti.
   - **Revert** je samostatná operace s `{repo, branch, sha, expectedHead}`; konflikt se hlásí jako nedokončený
     (`conflict`, merge --abort), nikdy jako hotový. **Rebase se jen eviduje** (`rebase {from, to}` ze záznamu služby),
     neprovádí.
   - **Deník Linie** = nové druhy `linie.*` v `opora_events` (stabilní `id`, pořadí, `refs: {ticket?, request?, op?,
     env?}`); událost nemusí mít kuličku; „nových“ se počítá od posledního přečteného `id`, ne od času; klik otevře důkaz.
   - Testy: pád po založení větve před zápisem evidence → zotavení bez duplicity; stejný klíč s jiným textem → 409;
     blokace při nedostupném gitu projde a nese `by`; revert s konfliktem není `finished`; žádost se dvěma tickety.
6. **Uzavření (L7f)** – integrační dokončení a důkaz společného fungování, žádné nové backendové funkce; nutné opravy
   backendu dovoleny. Frontend převezme data z L7c (tagy u commitu, worktree s agentem jen při vazbě, nasazení s původem,
   opuštěné kostky, PR s posledním známým stavem), UI z L7d/L7e (podle plánu, záložka Plán s rozdílem, deník z
   `opora_events`, řetězce žádostí, pilulka PR na 65 %, „Sledovat živě“). Tři opravy nalezené v kódu L7a/L7b se dělají
   hned na jejich větvích: stáří zdrojů roste nezávislým časovačem i při výpadku API (`lastSuccessAt`, „nyní
   nedostupné“); board a otevřený detail sdílejí revizi (akce blokované, dokud se `headSha` liší); jedna cesta akcí z
   `allowed`/`blocked` včetně `allow_merge` (staré `workActions` pryč). Scénáře §8 se ověří živě na náhledu z Velínu a
   staré styly a stavy se mažou až po ověření, že je nic nečte. Dvě kuličky „nahrazeno stromem“ se uzavírají ručně se
   zachovaným důvodem a vazbou na nástupce, ne automaticky jako splněné.
7. **Čeká na tebe (L7g)** – po L7f, samostatný vůz z integrované špičky: backend `accept-merge` (jedna operace nad
   stávajícími `accept`/`allow_merge`/`merge`, žádná nová evidence) a řazení fronty člověka ve `evaluate`/`board`
   (`queues.human[]` s pořadím a větou „pak bude na řadě“); frontend dílek `LinieHumanQueue` nad grafem podle §6.
   Hotovo když: člověk na projektu s vlakem tří vozů vidí jeden seznam v pořadí zdola nahoru, jedno tlačítko projede
   vůz za vozem a při posunutém cíli dostane větu s jedinou opravou; test na pořadí a na zastavení na 409.
   **L7g postaveno** (7. 11., `linie/human_queue.py`, `LinieHumanQueue`): mezi vozy vlaku musí agent nahlásit novou
   špičku rodiče (merge dítěte ji posune, kontroly platí pro sha); tlačítko „spustit kontroly“ chybí, služba je nespouští.

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

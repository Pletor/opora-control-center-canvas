# Srdce OPORY – rezidentní LLM za jednou bránou

Stav: návrh k rozhodnutí (2026-10-28).

Podklady:
- eval o víc sezeních m1 (`.claude/hillclimb/opora-vs-bare/multi/`);
- průzkum kódu OPORY a agent-office;
- dokumentace Claude Code;
- ověřovací běh poradce (§2).

## 1. Proč

Eval m1 (Zelený balkon, 4 sezení) ukázal, kde je problém. Kvalitu OPORY dorovná terminál s receptem (C) za 0,5–0,8 USD
na sezení. Agent v OPOŘE (A) stál 3–8 USD na sezení. V navazujících sezeních spálil asi 100 volání před první úpravou kódu
a jednou překročil 60 min.

Většina A volání padla na obřad: převzetí, graf, kroky a odevzdání. Agent při tom udržoval plátno, a to přes bránu
stavěnou pro člověka.

**Myšlenka.** Plátno má jednoho správce, totiž **srdce**. Je to LLM, které žije v OPOŘE u projektu, plátno zapisuje jen ono
a dělníkům rozdává přesné úkoly. Dělníci jsou relace z agent-office a do OPORY vstupují jedinou branou. Plátno nepíšou,
jen pošlou požadavek a odpověď dostanou do brány. Determinismus (pozorovatel gitu, zkoušky, kolize) dělá všechno,
co nepotřebuje úsudek. Srdce se budí jen na to, co úsudek potřebuje.

## 2. Ověřená fakta

| Fakt | Zdroj |
|---|---|
| Claude Code má poradce: `/advisor`, nastavení `advisorModel`, flag `--advisor <model>`. Funguje v `-p` i v Agent SDK. Dvojice Haiku 5.5 (hlavní) + Opus (poradce) je podporovaná od v2.1.293, lokálně běží v2.1.312. | code.claude.com/docs/en/advisor.md |
| **Ověřeno během:** `claude -p --model haiku --advisor opus` odpověděl správně a poradce se zavolal. Haiku stál 0,0045 USD, poradce 0,157 USD. **Poradce dostal celý kontext (37,8 tis. tokenů)**, takže jedna porada stojí asi 35 kol Haiku. | lokální běh 2026-10-28 |
| Počet porad nejde nastavit ani omezit, rozhoduje model. Za porady se platí z limitu předplatného a Opus má vlastní limit. | advisor.md |
| Rezidentní běh: `--input-format/--output-format stream-json`, `--resume <id>`, `--session-id`. Resume **neobnoví** `--settings` ani `--mcp-config`, ty se musí předat znovu. | headless.md, sessions.md |
| Limit: `rate_limit_event {status, resetsAt, utilization}`, `system/api_retry` s `rate_limit` a hook `StopFailure` s matcherem `rate_limit`. Zbývající kvótu přes API číst nejde. | errors.md, agent-sdk/typescript.md, hooks.md |
| Hradba v Claude Code: PreToolUse hook (`permissionDecision: deny`) a pravidla deny, která mají přednost před hookem. **Deny pravidlo nechytí tentýž program přes jinou cestu ani uvnitř `sh -c`**, takže hlavní hradba musí stát na serveru. | hooks.md, permissions.md |
| **Předplatné:** v `-p` vždy vyhraje `ANTHROPIC_API_KEY`, pokud je v prostředí, proto ho proces musí odstranit (asistent to už dělá, `command.py:92-108`). Consumer Terms §3.7 zakazují „automated or non-human“ přístup, kromě API klíče nebo výslovného povolení. Dokumentace zároveň uvádí, že nebrání „end user … signing in to the unmodified Claude Code binary with their own subscription“. | authentication.md, legal-and-compliance.md, anthropic.com/legal/consumer-terms |
| OPORA už má asistenta: `claude -p` stream-json, `--resume`, `WindowsJob`, watchdog, nejvýš 3 procesy, SSE událostí (`backend/claude_code/assistant/`). Hlavní model smí být jen opus, sonnet nebo fable (`command.py:21-22`). | kód |
| Budíky, které už existují: outbox `opora_events` zapisovaný v téže transakci, `PROCESS_SIGNAL`, nálezy strážců a SSE `/api/oporahub/events`. Vlákna na pozadí vlastní lifespan (`factory.py:179-195`). | kód |
| Identita: `X-Opora-Actor: agent; name=…` si agent deklaruje sám. Agent s `agentAutonomy.full` se počítá jako člověk (#137). **Tokeny rolí neexistují.** Routy asistenta nevolají `require_human`, chrání je jen loopback. | `human_session.py`, `authority.py`, `assistant_routes.py:151-170` |
| agent-office relace usazuje „push“ způsobem: jednorázový brief a obřad převzetí (`execution-dispatch.ts`). Brána, kde by si dělník řekl o další úkol, schránka ani stálý vedoucí agent v něm nejsou. | `agent-office/src/server/opora/` |

## 3. Tři vrstvy

```
            ┌──────────── HRADBA (server OPORY) ────────────┐
dělník ──►  │ BRÁNA /api/gate/*  ──►  determinismus          │
(agent-     │   token dělníka         ├─ odpoví hned (next, fakta)
 office)    │                         └─ událost ──► JEV (třídění)
   ◄────────┤ schránka ◄── odpověď           │ jen „chce úsudek“
            │                                 ▼
            │                     SRDCE (Haiku + poradce Opus)
            │                     token srdce: jediný zapisovatel plátna
            └───────────────────────────────────────────────┘
člověk ──► velín (cookie UI): schvaluje záměr, vidí doklady, má přednost
```

| Vrstva | Dělá | Nedělá |
|---|---|---|
| **Determinismus** | Odpovídá na `next` z fronty, zkouší commity, hlásí kolize větví, páruje commity s kartami, uzavírá karty při zelených zkouškách. | Nepíše úkoly ani plán. |
| **JEV** (`choice`/`score`/`noul`) | U každé události rozhodne `auto` / `srdce` / `člověk` / `nic`, přiřadí commit ke kartě a vyhodnotí vážnost. | Nepíše text. |
| **Srdce** | Rozkládá záměr na karty a kroky, píše úkoly, přeformuluje úkol po druhém selhání, řeší kolize řazením, odpovídá na otázky dělníků a hlásí konflikt se záměrem do velínu. | Nepíše kód aplikace. Neschvaluje změnu záměru. Nepracuje bez události. |

## 4. Kde srdce žije

**Proces.** Modul `backend/brain_opora/srdce/` (§4a). Supervizor je vlákno vlastněné lifespanem (vzor `GuardianManager`).

**Spánek na localhostu.** Když OPORA běží na loopbacku, supervizor se spustí automaticky. Srdce pak **spí**:
- proces Claude Code neběží a nic se neplatí;
- probudí ho až událost, kterou pustí rozhodovací model, nebo zpráva člověka.

Na každý projekt připadá nejvýš jeden proces srdce. Přes tunel (vzdálený přístup) se srdce nebudí a brána je jen
pro loopback.

Spouštění převezme `SessionProcess` a `WindowsJob` z asistenta. Stavební kód příkazu bude vlastní, protože asistent
Haiku jako hlavní model nepovoluje a jeho pravidla jsou psaná pro člověka.

```
claude -p --input-format stream-json --output-format stream-json --verbose
  --model haiku --advisor opus
  --session-id <uuid> | --resume <uuid>
  --setting-sources project --settings <heart-settings.json>   # hooky hradby, deny pravidla
  --strict-mcp-config --mcp-config <prázdný>                    # REA až ve fázi H5
  --allowedTools "Read,Grep,Glob,Bash(python <heart>/opora_heart.py:*)"
  --permission-mode dontAsk
  --append-system-prompt-file <heart-prompt.md>
  --add-dir <zdroj projektu>                                     # jen čtení kódu
cwd = <data>/heart/<project>/       env: bez ANTHROPIC_API_KEY, OPORA_HEART_TOKEN=…
```

**Životní cyklus: budí se, odbaví dávku, usne.**
1. Událost, kterou JEV označí `srdce`, padne do fronty srdce. Supervizor sbírá dávku 60 s, pak proces spustí
   (`--resume`), nebo použije ten, který už běží.
2. Srdce dostane jednu zprávu. V ní je deterministický **snímek** (stav plánu, padlé zkoušky, otevřené tikety, kolize,
   maximálně 4 tis. tokenů) a seznam událostí. Historii z paměti nečte.
3. Odbaví práci přes `opora_heart.py` (§6) a skončí krátkým záznamem do deníku srdce.
4. Po 10 min bez práce supervizor proces ukončí. Další budíček udělá `--resume`.

**Paměť a rotace.** Pravdou je OPORA, ne kontext modelu: plán, deník (`node_journal_revisions`), rozhodnutí
(`desktop_v3_state`) a tikety brány. Když kontext relace přeroste **60 tis. tokenů**, začne supervizor novou relaci
(`--session-id`) a předá jí čerstvý snímek.

Důvod: každá porada poradce dostane celý kontext (§2). Malý kontext tak znamená levné porady a tohle je hlavní páka
na cenu srdce.

**Kdy se poradit.** V promptu srdce je to vyjmenované:
- rozklad záměru na plán;
- konflikt požadavku se záměrem;
- druhé selhání téhož úkolu;
- kolize, kterou nejde vyřešit pořadím.

Jinak Haiku jedná sám. Počet porad Claude Code omezit nedovoluje, proto ho supervizor měří (`modelUsage` Opus na
dávku). Když porady přesáhnou strop dne, spustí srdce bez `--advisor`.

## 4a. Modul `brain-opora`: tři vrstvy, tři složky

Rozhodnutí člověka (2026-10-28): každá vrstva je samostatná složka. Práce na srdci se dělí podle nich a jedno PR sahá
do jedné složky. Python balík nesmí mít pomlčku, proto se jmenuje `brain_opora`.

```
backend/brain_opora/
  README.md                 # příběh tří vrstev, tok události, kdo smí co
  determinismus/            # vrstva 1: bez modelu, zdarma, okamžitě
    brana.py                #   /api/gate: relace, požadavky, schránka (logika; router v api/)
    tokeny.py               #   tokeny rolí člověk / srdce / dělník, middleware hradby
    fronta.py               #   fronta úkolů, next z fronty, report → zkoušky sha
    snimek.py               #   deterministický snímek projektu pro srdce (≤ 4k tokenů)
    udalosti.py             #   odběr opora_events + PROCESS_SIGNAL → kandidáti na budíček
    schvaleni.py            #   klasifikace nástrojů (převzato z assistant/approvals.py)
  rozhodovani/              # vrstva 2: JEV, typované odpovědi choice / score / noul
    vratny.py               #   událost → auto | srdce | člověk | nic
    prirazeni.py            #   commit bez traileru → karta (score)
    zdroje.py               #   směrovač podkladů (převzato z assistant/router.py, rlm_rank.py)
  srdce/                    # vrstva 3: Claude Code pod předplatným, Haiku + poradce Opus
    supervizor.py           #   spánek, budíček, dávka 60 s, stropy, rate_limit_event
    prikaz.py               #   sestavení CLI (§4), bez ANTHROPIC_API_KEY
    proces.py               #   SessionProcess + WindowsJob (převzato z assistant/)
    proud.py                #   stream-json → události (převzato z assistant/stream.py, event_log.py)
    relace.py               #   session-id, resume, rotace nad 60k tokenů
    prompt.md               #   role srdce, kdy se poradit, co nesmí
    opora_heart.py          #   jediný nástroj srdce (§6)
backend/api/brain_opora/    # routery: gate_routes.py, srdce_routes.py (kanál člověka)
```

Testy leží vedle modulů (`test_<modul>.py`). Hranice mezi vrstvami jsou pevné:
- determinismus nevolá model;
- rozhodování jen vybírá a nepíše text;
- srdce nezapisuje mimo `opora_heart.py`.

**Asistent se předělá na kanál člověka do srdce.** Rozhodnutí člověka: dnešní asistent nefunguje správně. Z průzkumu
jsou známé tyhle vady:
- Haiku nesmí být hlavní model;
- `rate_limit_event` se neřeší a chybí strop kvóty;
- routy nekontrolují člověka, chrání je jen loopback;
- čekání na schválení člověkem až 10 min blokuje relaci;
- zpráva během běžícího kola dostane 409.

Nové řešení:
- Okno asistenta v aplikaci posílá zprávy srdci stejného projektu přes `api/brain_opora/srdce_routes.py`, s rolí člověk.
- Zpráva člověka má přednost před frontou dělníků a během kola se zařadí, nevrací 409.
- Použitelné části `backend/claude_code/assistant/` se přesunou do vrstev podle stromu výše. Zbytek se po přechodu
  **smaže** i s testy a README (pravidlo mazání slepých uliček).
- Frontendový panel asistenta zůstane a změní jen API.

## 5. Hradba a brána

**Hlavní hradba stojí na serveru.** Hooky a deny pravidla v Claude Code jsou jen druhá vrstva, protože je jde obejít
(§2). Role nese token, ne deklarovaná hlavička.

| Role | Jak vznikne | Smí |
|---|---|---|
| **člověk** | cookie UI `opora_ui` (dnes) | všechno |
| **srdce** | token vydá supervizor při startu procesu a předá ho jen jeho env | čtení, zápis plátna, plánu a karet, tikety brány, eskalace do velínu; nesmí schvalovat záměr ani měnit autonomii |
| **dělník** | `POST /api/gate/sessions` (volá agent-office) vrátí token relace s TTL | jen `/api/gate/*` a čtecí allowlist |
| bez tokenu | — | u projektu se srdcem jen čtení; zápis vrátí 403 `{hint: "vstup přes /api/gate"}` |

Middleware vychází z dnešního `require_authority` (`factory.py:218-236`). U projektu bez srdce platí všechno jako dnes,
srdce se zapíná po projektech.

**Brána: požadavek → odpověď do schránky.**

| Volání | Tělo | Odpověď |
|---|---|---|
| `POST /api/gate/sessions` | `{project, workspace, worker: {office, floor, name}}` | `{token, expiresAt}` |
| `POST /api/gate/requests` | `{kind: "next"\|"ask"\|"report"\|"change", body}` | `{ticketId, status, answer?}`: `next` a `report` odbaví determinismus hned, `ask` a `change` jdou přes JEV ke srdci |
| `GET /api/gate/inbox?after=<seq>&wait=30` | — | odpovědi na tikety relace (long-poll), bez cizích tiketů |

`next` vrací úkol v pevném tvaru:

```json
{"taskId": "t-14", "nodeId": "kontakt", "why": "zkouška form.aria_invalid padá od 9f8e",
 "do": "…", "files": ["src/sections/contact/ContactForm.tsx"], "doneWhen": ["form.aria_invalid", "journey.kontakt"],
 "dontTouch": [{"path": "src/components/Layout.tsx", "heldBy": "t-15"}],
 "context": {"intent": "klidně, bez nátlaku", "rules": ["…"], "pattern": "knihovna/…@1"},
 "commit": "Opora-Node: kontakt · Opora-Task: t-14"}
```

Když je fronta prázdná, `next` vrátí plán, pravidla a stav zkoušek. Dělník pak pracuje jako rameno C a nečeká.

`report` přijme `{taskId, sha, summary}`. Ověření nedělá dělník, ale determinismus: zkouší sha a uzavírá kartu.

**Úložiště.** Tikety a fronta úkolů potřebují **nové tabulky** `gate_tickets` a `heart_tasks` v `project.sqlite`.
Existující tabulky se nemění. Zakládání tabulek schvaluje člověk před fází H0.

## 6. Nástroje srdce

`opora_heart.py` je jediný skript srdce. Má úzké příkazy a každý je jedno volání:
- `snapshot`
- `plan-apply --json -` (dávka plánu; přes token srdce je srdce jediný zapisovatel, takže odpadá 409 kvůli souběhu)
- `task-put`, `task-revise <id>`
- `ticket-answer <id>`
- `escalate --to human`
- `journal`

Chyba vrací `code` a `hint`, jako #139.

Srdce nemá Edit ani Write do zdroje projektu. Kód píšou jen dělníci.

## 7. Limity a cena

- **Kvótu srdce sdílí s dělníky.** Při `rate_limit_event` se `status: rejected` nebo `allowed_warning` nad 80 %
  `utilization` srdce usne až do `resetsAt` a fronta čeká. Determinismus a brána běží dál, takže `next` funguje.
  **Dělníci mají přednost.**
- **Stropy (nastavení projektu):**
  - budíčků za hodinu: 6;
  - porad za den: 20;
  - odhad ceny za den: z `total_cost_usd`, je to jen ceníková náhražka, ne skutečný limit.

  Velín ukazuje spotřebu srdce zvlášť.
- **Odhad:** dávka Haiku se snímkem do 10 tis. tokenů stojí řádově setiny USD (ceníkově), porada 0,1–0,2 USD.
  Ověří se v evalu (§10).

## 8. agent-office

Dnes agent-office usazuje „push“: převezme kartu (`executions/context` → `claim` → `assignment`) a předá brief s bundlem.

U projektu se srdcem se to změní:
1. Bridge si vyžádá token relace (`/api/gate/sessions`).
2. Brief dělníka bude: „`opora gate next`, pracuj, commit s trailerem, `opora gate report`“.
3. Bundle i převzetí odpadají.
4. Seat plánovače v režimu opora/router u takového projektu není potřeba, plánuje srdce.

Změny v agent-office jsou samostatné PR v jeho repozitáři (fáze H3).

## 9. Rozhodnutí člověka

**Rozhodnuto (2026-10-28):**
- Tři vrstvy jsou samostatné složky modulu `brain_opora` (§4a).
- Na localhostu v OPOŘE automaticky spí LLM pod předplatným.
- Asistent se předělá na kanál člověka do srdce (§4a).
- Díra v routách asistenta zanikne s přechodem asistenta, zvláštní PR odpadá.

**Zbývá rozhodnout:**
1. **Znění pravidla o místech modelu** (`CLAUDE.md`, `docs/asistent.md` → `backend/brain_opora/README.md`). Návrh:
   „Mozek OPORY (`brain_opora`): srdce = Claude Code pod předplatným (Haiku + poradce Opus), spí na localhostu, budí ho
   rozhodovací model JEV z událostí nebo zpráva člověka, stropy v nastavení projektu. Asistent v okně je kanál člověka
   do srdce.“ Zrcadlo zůstává.
2. **Riziko předplatného.** Consumer Terms §3.7 zakazují automatizovaný přístup bez API klíče, pokud není výslovně
   povolený (§2). Srdce poběží pod předplatným, se stropy a jako jeden uživatel. Přepnutí na API klíč zůstane jedno
   nastavení (`[brain] auth = "subscription" | "api_key"`).
3. **Nové tabulky** `gate_tickets` a `heart_tasks` (§5).

## 10. Fáze

Každá fáze je malé PR s testy vedle modulů.

| Fáze | Obsah | Hotovo, když |
|---|---|---|
| **H0** | Kostra `backend/brain_opora/` se třemi složkami a README, bez chování. | Struktura, kontrola `router-v-api` zelená. |
| **H1** `determinismus/` | Tokeny rolí, `/api/gate/sessions\|requests\|inbox`, tabulky, deterministický `next` a `report` (fronta, snímek, zkoušky sha). | Dělník projde S2 jen přes bránu, bez srdce, s ručně zadanými úkoly. |
| **H2** `srdce/` | Supervizor (spánek na localhostu), proces Haiku bez poradce, budíček z `opora_events`, `opora_heart.py`, rotace relace; přesun procesu a proudu z asistenta. | Událost „zkouška padá“ vytvoří úkol ve frontě do 2 min. |
| **H2b** `srdce/` | Kanál člověka: panel asistenta mluví se srdcem, zpráva se zařadí, starý `claude_code/assistant/` se smaže. | Panel funguje se srdcem, 0 odkazů na starý modul. |
| **H3** `rozhodovani/` | JEV jako vrátný a přiřazení commitů, přesun směrovače, poradce Opus se stropem, `rate_limit_event`. | Srdce se probudí jen na události vyžadující úsudek, porady jsou změřené. |
| **H3b** | agent-office: bridge přes bránu. | Relace z agent-office dostane úkol a odevzdá ho bez převzetí karty. |
| **H4** | Eval m2 na Zeleném balkonu: C proti D (brána a determinismus) a E (D + srdce). | Tabulka kvality, ceny dělníků a ceny srdce. |
| H5 | Výzkum s REA (rozbor vzoru do knihovny) a REA jen pro srdce. | Až po H4, podle výsledků. |

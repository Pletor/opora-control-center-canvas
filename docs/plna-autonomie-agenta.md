# Plná autonomie agenta

Stav: kontrakt, rozhodnutí uživatele 2026-10-28. Kód ho provádí, nemění.

## 1. Proč

Uživatel: „vše mohl ovládat agent a nebylo to závislé na člověku.“ Dnes spoustu akcí smí jen člověk s relačním
dokladem UI (`backend/app/human_session.py`, `require_human` v `backend/canvas/activity_log.py`, kontroly
`by["kind"] == "human"` ve službách): přijetí návrhů grafu a změn obsahu, přijetí zadání, commit a přijetí do
mainu, hromadné potvrzení, svěření autonomie, obnovení verze plátna, review policy, rozpočty běhů, úklid aj.
Agent tak bez člověka nedokončí práci.

## 2. Pravidlo

Projekt má přepínač **plná autonomie agentů** (výchozí vypnuto). Zapnout a vypnout ho smí **jen člověk v UI**
(jediná lidská akce, která zůstává; agent si autonomii nikdy nesvěří sám). Když je zapnutý, agent
(`X-Opora-Actor: agent; name=…`) smí v tomto projektu **všechno, co smí člověk**, kromě výjimek v §4.

Oddělit **oprávnění** od **původce**:
- `request.state.actor` (původce) zůstává `agent` – záznam činnosti, události, deník a review dál říkají, že to
  udělal agent, s jeho jménem. Nikdy se nezapíše „člověk“.
- Nové `request.state.authority` ∈ `human | agent | unknown`: `human` pro člověka s dokladem **a** pro agenta
  v projektu se zapnutou plnou autonomií. Všechny brány „jen člověk“ čtou `authority`, ne `actor`
  (jedna funkce, např. `require_authority(request, project, message)`; služby, které dnes porovnávají
  `by["kind"] == "human"`, dostanou rozhodnutí oprávnění zvenku, ne vlastní odhad).
- Každá akce provedená agentem díky plné autonomii se v záznamu činnosti označí `autonomy: "full"`, aby šla
  zpětně dohledat a v UI odlišit.

## 3. Úložiště a API

- Stav přepínače v existujícím nastavení projektu (`/api/project-settings`, stejné úložiště jako ostatní
  nastavení projektu). **Žádná změna schématu tabulky**; pokud by bez ní nešlo, implementace se zastaví a zeptá.
- `GET /api/project-settings?project=` vrací `agentAutonomy: {full: bool, since?, by?}`.
- Zápis jen člověk (`require_human` zůstává u tohoto jednoho zápisu i u přístupových rout).
- agent-state a node-brief nesou `autonomy: {full: bool}`, aby agent věděl, že může přijímat a uzavírat sám.
- Velín a hlavička projektu ukazují trvalý štítek „Plná autonomie agentů“ a přepínač.

## 4. Výjimky (zůstávají jen člověku i při plné autonomii)

- přepínač plné autonomie sám;
- přístup a vzdálený přístup (`/api/access/*`, tokeny, `ui-session`);
- připojení / odpojení repozitáře a složky projektu;
- klíče a tajemství (`/api/assistant/jev-key`, paměť – provisioning root klíčem).

## 5. Skill

Skill `opora-control-center` popisuje každou routu, kterou může agent volat (včetně dříve lidských akcí
s poznámkou „při plné autonomii“), přepínač a jak agent pozná, že ho má (`autonomy.full`). Test skill docs
hlídá, že žádná routa backendu kromě §4 a čistě UI rout v skillu nechybí.

## 6. Upřesnění z implementace (2026-10-28)

Jen upřesnění, pravidla §2–§5 platí beze změny.

- **Úložiště přepínače.** Tabulka `project_settings` má pevné sloupce, proto stav leží v `project.json` složky
  projektu pod `settings.agentAutonomy` (`{full, since, by}`), vedle zrcadla ostatních nastavení. Schéma žádné
  tabulky se nemění. Chybějící nebo poškozená hodnota = vypnuto.
- **API přepínače.** `GET /api/project-settings?project=` vrací `agentAutonomy: {full, since?, by?}`.
  Zápis je samostatná routa `POST /api/project-settings/agent-autonomy` s tělem přesně `{project, full: bool}`
  (vrací totéž co GET); jen člověk (`require_human`: agent 403, neznámý 428). Uložení ostatních nastavení
  (`POST /api/project-settings`) se nemění a přepínač nenese.
- **Jak se pozná projekt požadavku.** Middleware vezme `project` z query, jinak z těla JSON. Požadavek bez
  projektu nebo s neznámým projektem dostane `authority = agent` (bez autonomie). Autonomie platí jen pro
  projekt požadavku, nikdy napříč projekty.
- **Jak služby dostanou rozhodnutí.** `backend/canvas/authority.py`: middleware uloží oprávnění do kontextu
  požadavku (`ContextVar`); brány volají `require_authority(actor, zpráva)` (`backend/canvas/activity_log.py`)
  nebo `acts_as_human(actor)`; příznaky `canAccept`/`canConfigure`/`canCancel` čtou `can_act(actor)`.
  `require_human` zůstává jen pro výjimky §4. Mimo HTTP požadavek (smyčky na pozadí) agent autonomii nemá.
- **Atribuce v datech.** Co agent zapíše díky autonomii, nese jeho druh a jméno: `by: {kind: "agent", name}`
  v OporaHubu (commity, přijetí, politiky, rozpočty, sledování), `done.by: "agent"` u potvrzeného uzavření,
  `grantedBy: "agent <jméno> (plná autonomie)"` u svěření autonomie sektoru. Validace uložených záznamů proto
  u lidských akcí přijímá `human` i `agent`; kdo smí zápis provést, hlídá brána při zápisu. Sektor je ověřený
  i s bránou potvrzenou agentem (`done.by` `human` nebo `agent`). Schválení návrhu pravidla agentem zapisuje
  server (`system`), aby se pravidlo znovu neoznačilo jako návrh; původce zůstává agent v záznamu činnosti.
- **Záznam činnosti.** Tabulka `activity_log` nemá JSON detail, proto se akce díky autonomii značí tokenem
  `autonomy=full` na konci `summary` (bez změny schématu); `GET /api/activity-log` z něj vrací
  `autonomy: "full"` (jinak `null`). Značí se jen požadavek, kterému brána „jen člověk“ prošla díky autonomii,
  ne každý zápis agenta v projektu se zapnutou autonomií. Shodný konec `summary` od klienta server rozbije (` ~`).
- **agent-state a node-brief.** agent-state nese `autonomy: {full}`. node-brief už pole `autonomy` měl
  (svěřená autonomie sektoru); `full` se přidává do téhož objektu: `autonomy: {full, sectorId, grant, policy}`.
- **Výjimky §4 v kódu.** Jen člověk i při plné autonomii: `POST /api/project-settings/agent-autonomy`,
  `/api/access/*`, `/api/oporahub/repository` a `/unbind`, smazání celého projektu (`/api/remove` s `kind:
  project` = odpojení složky projektu), `POST /api/assistant/jev-key` a `POST /api/memory/provision` (tyto dvě
  dřív neměly bránu vůbec; teď `require_human`). Dál jen člověk zůstává i **identita reviewera**
  (`/api/oporahub/review-identities*`): je to tvrzení „tento GitHub účet je člověk“, tedy atribuce, ne oprávnění,
  a strana `human` v duelu schránky (mluví za člověka).
- **Převzetí (lease).** Je to koordinace agentů, ne oprávnění: běžný zápis agenta s autonomií cizí platné
  převzetí neobchází; výslovné uvolnění bez tokenu (`op: release`) smí jako člověk.

## 7. Cesta bez slepých pokusů (2026-10-28)

Upřesnění z ověřovacího běhu headless agenta (mapa → karty → přijetí grafu → claim → kroky → `local-merge` →
kontroly → cesta → `close_card`). Pravidla §2–§4 se nemění; mění se jen to, co agent dostane zpátky.

- **422 vs. 409.** Neplatný tvar těla (`site`, `subject`, pole přijetí návrhu grafu, změny a obsahu) vrací
  422 `{error, code: "invalid_payload", field, expected, example}` (`backend/canvas/payload_errors.py`,
  `InvalidPayload`). 409 zůstává jen pro konflikt stavu (revize, hlava, duplicita). Krok, který chybí před
  jiným, vrací 409 s `code` a `hint` (`NextStep`), např. claim bez přijatého grafu plánu
  `graph_acceptance_required`.
- **agent-state nabízí první krok.** Bez přijatého manifestu grafu nabídne akci `propose_graph` (prázdný
  graf nad hlavou) a po ní `accept`; preconditions `accept` nesou přesné tělo včetně `adoptBase*Digest`,
  `accept_baseline` nese `subject`. Při `autonomy.full` jsou lidské akce `ready`.
- **Skripty skillu.** `opora_hub.py act --action-id ID` provede akci z agent-state podle `method/path/
  preconditions` (i `close_card`), `local-merge` a `close-card` mají vlastní příkaz; `opora_api.py METHOD PATH`
  volá jinou cestu s identitou agenta a výjimky §4 i cesty s tokenem odmítne předem. Výstup je vždy JSON
  s `ok`, `status`, `error`, `hint`; kód 6 = 422. Postup je recept „stavba stránky“ v `SKILL.md`, ověřený
  testem `.claude/skills/opora-control-center/scripts/test_opora_recipe.py`.

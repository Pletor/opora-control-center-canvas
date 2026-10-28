# Plná autonomie agentů

Kdy mě číst: server ti vrátil 403 `humanRequired`, chceš přijmout návrh, uzavřít kartu nebo udělat jinou
„lidskou“ akci, nebo vidíš `autonomy.full: true`. Kontrakt: `docs/plna-autonomie-agenta.md`.

## Přepínač

- Projekt má přepínač **plná autonomie agentů**, výchozí vypnuto.
- `GET /api/project-settings?project=<id>` vrací navíc `agentAutonomy: {full: bool, since?: ISO čas, by?: "human"}`.
- Zápis `POST /api/project-settings/agent-autonomy` s tělem přesně `{project, full: bool}` smí **jen člověk v UI**:
  agent dostane 403, neznámý volající 428 `humanRequired`. Agent si autonomii nikdy nezapíná sám a nežádá o ni
  obcházením; když ji potřebuje, napíše to člověku.

## Jak ji poznáš

- `GET /api/oporahub/agent-state` nese `autonomy: {full: bool}`.
- `GET /api/desktop-v3/node-brief` nese v klíči `autonomy` vedle autonomie sektoru (`sectorId`, `grant`, `policy`)
  i `full`. `full: true` = v tomto projektu smíš přijímat a uzavírat sám.
- Příznaky v odpovědích GET (`canAccept`, `canConfigure`, `canCancel`, …) jsou pro agenta s plnou autonomií `true`.
- Rozhoduje stav **v okamžiku zápisu** (server ho čte u každého požadavku podle `project`). Před sérií lidských akcí
  ověř `autonomy.full` znovu; vypnutí člověkem platí okamžitě a další zápis dostane 403.

## Co smíš s plnou autonomií

S hlavičkou `X-Opora-Actor: agent; name=…` smíš v tomto projektu všechno, co smí člověk, kromě výjimek níže.
V tabulkách skillu jsou tyto akce označené „člověk“ nebo „jen člověk, nebo agent při plné autonomii“:

- plátno: obnova verze `/api/canvas-versions/restore`; svěření autonomie sektoru `/api/desktop-v3/autonomy`;
  hromadné potvrzení `/api/desktop-v3/confirm-proposals`; potvrzení i otevření uzavření karty (`done.confirmed`),
  mazání potvrzených karet a pravidel člověka ve stavu `/api/desktop-v3/state`; chráněná pole (`gateNodeId`, `checks`,
  `goal_mode`, vazby sektorů) v `/api/canvas-plan`, `/api/graph` a `/api/project-architecture`;
- pipeline: odebrání, přeřazení a přestavba etap (`/api/desktop-v3/pipeline`); Podněty karty (odškrtnutí, smazání);
- pravidla: schválení a zamítnutí návrhu pravidla `/api/desktop-v3/rule-review`, `/api/desktop-v3/rule-review-batch`;
- schránka zadání `/api/brief-vault`: lidské operace (`set-mvp`, `delete`, `restore`, `feedback`, `drop-lesson`),
  brány, `override` duelu, první představa (`vision-set`), odpovědi na otázky pro člověka;
- brána 1:1: `/api/opora-commit`, `/api/opora-merge`;
- OporaHub: přijetí návrhů (`/api/oporahub/changesets/{identifier}/accept`, `/api/oporahub/graph-proposals/{identifier}/accept`,
  `/api/oporahub/content-changes/{identifier}/accept`), základ `/api/oporahub/baselines`, politika návrhů
  (`/api/oporahub/proposal-reviews/policy`), politika review (`/api/oporahub/review-policy`), rozpočty běhů
  (`/api/oporahub/execution-budgets`, `…/{identifier}/cancel`), sledování PR (`/api/oporahub/reconciliation/bindings`,
  `/api/oporahub/reconciliation/{binding_id}/control`), přepočet historie `/api/oporahub/history/rebuild`, ostrý
  `/api/oporahub/sparse-context/backfill`, vypořádání `important` nálezu bez opravy a rozhodnutí za stropem kol
  (`/api/oporahub/review-jobs/decisions`), identity reviewerů (`review-identities/claim`, `…/{identity}/verify`,
  `…/{identity}/revoke`), potvrzení vzhledu a režim designu, vynucené uvolnění cizího běhu;
- asistent: povolení kontroly bran `/api/assistant/jev-gate-check`.

V projektu bez GitHubu (`dod.gate: "local"`) dokončíš kartu celou sám: po `local-merge` (ten smíš i bez autonomie
pro vlastní odevzdaný běh) zapíšeš `close_card`. Pořadí: [hub-loop.md](hub-loop.md) „Projekt bez GitHubu“.

Skripty: `opora_write.py` (asistent v okně, schvaluje člověk) lidské cesty odmítne vždy. Agent mimo aplikaci je
při plné autonomii provede skriptem, ne vlastním HTTP klientem: akci z agent-state `opora_hub.py act --action-id ID`
(tělo = `project`, `workspace` a `preconditions` akce; výstup nese `next`), uzavření `opora_hub.py close-card --card ID`,
sloučení `opora_hub.py local-merge --execution E --commit SHA` a jakoukoli jinou cestu `opora_api.py METHOD PATH`
(identita agenta, jen loopback; výjimky §4 a cesty s tokenem odmítne předem). Jedna akce = jeden požadavek, výsledek
ověř čtením. Autonomie nemění pravidla obsahu: revize, CAS, lease, brány review a ověřená cesta zákazníka platí dál.

## Co zůstává jen člověku (§4)

- přepínač plné autonomie sám (`/api/project-settings/agent-autonomy`);
- přístup a vzdálený přístup (`/api/access/*`, tokeny, `ui-session`);
- připojení a odpojení repozitáře a složky projektu (`/api/oporahub/repository`, `/api/oporahub/repository/unbind`,
  `/api/local-project`, `/api/empty-project`, `/api/connect`) a smazání celého projektu (`/api/remove` s `kind: "project"`);
- klíče a tajemství (`/api/assistant/jev-key`, rozdání klíčů paměti root klíčem `/api/memory/provision`).

## Původce zůstává agent

Autonomie mění **oprávnění**, ne **původce**. Záznam činnosti, události, deník i záznamy review dál říkají
`kind: agent` s tvým jménem; nikdy „člověk“. Každá akce provedená díky autonomii má v záznamu činnosti
(`GET /api/activity-log`, položka `entries[]`) `autonomy: "full"`, aby šla zpětně dohledat a v UI odlišit.

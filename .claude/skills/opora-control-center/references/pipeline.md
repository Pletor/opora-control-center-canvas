# Pipeline karty: router, etapy, kritici

Kdy mě číst: jsi ROUTER (určuješ proces karet), děláš etapu pipeline (práce, test, review, oprava,
kritik), nebo karta v `node-brief.pipeline` něco čeká. Server pravidla hlídá sám
(`backend/editor/agent_memory/card_pipeline.py`); kontrakt `docs/karta-pro-agenty.md` → Pipeline karty.

## Model

Pipeline = sled etap `{id, kind, lens, title, brief, status, note, by, doneBy, at, retryOf?}`.
`kind`: `work` | `test` | `review` | `fix` | `critic`; kritik má `lens`: `user` (hodný uživatel),
`sly` (vyčuraný: nedodělky, obcházení), `hacker` (útok). `status`: `todo` | `doing` | `passed` | `failed` | `skipped`.
Každou etapu dělá **nová relace** (karta + jedna etapa); kontext mezi relacemi nese `note` etap.

## Router

1. `opora_read.py frontier --project P --workspace W` (bez `--node` = kořen; u sektorů `--node SEKTOR`).
   `needsRouting` = otevřené karty bez pipeline.
2. Pro každou: `node-brief --node ID` a vyber profil podle povahy práce (`pipeline-profiles` vrátí šablony):

   | Karta | Profil |
   |---|---|
   | `goal_mode: until_checks_pass` | `goal` |
   | UI, obrazovky podle návrhu | `design` |
   | autentizace, oprávnění, vstupy zvenku, data uživatelů | `security` |
   | chyba, regrese | `testing` |
   | `[research]` | `research` |
   | ostatní kód | `code` |

   Kombinace → přísnější profil a chybějící etapy přes `stages` (např. kritik hacker do design karty s přihlášením).
3. Zapiš (`expectedRevision` = `revision` ze `state`):

<!-- example: /api/desktop-v3/pipeline -->
```json
{"nodeId": "NODE_ID", "expectedRevision": 4, "op": "route", "profile": "security",
 "reason": "[task] s přihlášením a checks na API; vstup zvenku.",
 "stages": [{"kind": "critic", "lens": "user", "title": "Kritik: průchod přihlášením", "brief": "Projdi login jako uživatel."}]}
```

   `op: "add"` + `stages` přidá etapy za rozpracovanou část (kdykoli, platí hned).
4. Pak naplánuj relace: pro každou kartu s `pipeline.current` jednu relaci. Review a kritiky přiděl
   **jiné relaci** (jiné `OPORA_AGENT_NAME`) než práci; kde to jde, jinému modelu.
5. Výstup kola: tabulka karta | profil | etapa na řadě | doporučený agent | blokace; zvlášť karty v `waiting`.

Podlaha (server odmítne 409 s výčtem): pipeline od agenta má `review` a kritika `hacker`;
`[task]` karta a karta s `checks` i `test`. Profil `custom` ani `research` k obejití nepoužívej.
Přestavět profil smí agent jen, dokud je vše `todo` a pipeline nesestavil člověk (jinak 403).

## Relace na etapě

1. `frontier` → karta s `pipeline.current` pro tvůj druh etapy → `lease claim`.
2. `node-brief --raw` → `pipeline.current` (co dělat: `brief`), `pipeline.stages[].note` (předávky).
3. Udělej jen tuto etapu. Hlášení v `agent-output.output.stages`:
   `[{id, status: "doing"|"passed"|"failed", note}]`; `passed` / `failed` musí mít neprázdnou `note`
   (co jsi udělal, co našel, co má další relace udělat).
4. Server hlídá:
   - pořadí: etapu nahlásíš, až když předchozí nejsou `todo` / `doing`; kritici jdoucí po sobě tvoří **kolo**
     a odevzdávají se v libovolném pořadí (paralelně), jakmile jsou uzavřené etapy před kolem (`pipeline.parallel`);
   - nezávislost: `review` a `critic` neuzavře relace, která uzavřela `work` / `fix` na téže kartě;
   - GOAL: `test` na GOAL kartě projde jen se zelenými `evidence.checksRun` všech kontrol (pošli je ve stejném výstupu);
   - smyčku oprav: `failed` u `test` / `review` / `critic` sám vloží `fix` a opakování (`retryOf`); selže-li v kole
     víc kritiků, je za kolem **jedna** společná oprava a opakování každého z nich; po 2 smyčkách
     karta čeká na člověka (`pipeline.stuck`, `loop.waitingOnHuman`, frontier `waiting`).
   - zaseknutou etapu (selhaná bez opakování, např. starší review) znovu zařadí
     `{"op": "retry", "stageId": ID, "reason": …}` (oprava + opakování); to dělá i `opora_closure.py --apply`.
5. Kartu nelze uzavřít, dokud každá etapa není `passed`, člověkem `skipped`, nebo ji nenahradilo úspěšné opakování.

## Kritici

Hodnotíš cizí práci, ne svou. Zadání v `brief` etapy:

- `user`: projdi hlavní cestu jako běžný uživatel / agent. Funguje bez překvapení?
- `sly`: hledej nedodělky, část místo celku, obcházení místo práce, N/A bez důvodu, testy, které nic neověřují.
- `hacker`: napadni vstupy, oprávnění, identitu, souběh, mazání.

**Blokátor vs. podnět** (proces se nesmí cyklit na okrajových případech; ne-blokující nález nezastaví MVP):

| Nález | Stav etapy | Kam |
|---|---|---|
| **blokátor**: rozbije MVP nebo proces aplikace, ztráta či únik dat, bezpečnost, regrese běžného vstupu proti předchozímu chování | `failed` | `note`: `@soubor:řádek`, kroky k reprodukci, dopad |
| vše ostatní (okrajový případ, hezčí řešení, chybějící detail, další test) | `passed` | `output.ideas [{text, source: "critic:sly"}]` = podnět k dalšímu vývoji |

Bez nálezu `passed` s tím, co jsi ověřil. Opravu nedělej sám; vloží ji server jako etapu `fix` pro další relaci.
Kritici kola běží souběžně, lease je ale na kartu jeden: kritik čte a zkoumá bez lease a kartu převezme
až krátce na odevzdání. To dělá skript jedním příkazem (čeká na předchozí etapy, lease s opakováním, důkazy,
release, ověření čtením):

```
python "<SKILL_DIR>/scripts/opora_stage.py" --project P --workspace W --node N --stage STAGE_ID --agent kritik-sly-2 --passed --note-file note.txt --idea "Dlouhý název zalomit." --check "unit=uv run pytest backend=0" --wait-prior
```

## Co smí kdo

| Akce | Agent / router | Člověk |
|---|---|---|
| sestavit pipeline (`route`) | ano, s podlahou; přestavět jen nerozjetou od agenta | vždy (i `custom`) |
| přidat etapy (`add`) | ano, za rozpracovanou část | ano |
| znovu zařadit zaseknutou etapu (`retry`) | ano, do vyčerpání smyček | ano |
| hlásit stav etapy | jen přes `agent-output.stages` | v UI přeskočit / vrátit |
| odebrat, přeskládat, upravit, přeskočit | ne (403) | ano |
| přidat podnět k dalšímu vývoji | jen přes `agent-output.ideas` | ano |
| odškrtnout / smazat podnět | ne (403) | ano (detail karty, záložka Podněty) |

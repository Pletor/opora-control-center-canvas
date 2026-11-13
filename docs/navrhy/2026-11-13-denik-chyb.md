# Deník chyb OPORY: jedno místo pro všechno, co se pokazí, zasekne nebo cyklí

Stav: návrh (13. 11. 2026). Kontrakt pro stavbu. Inventura zdrojů je v §8.

## §0 Proč

Dnešní noc ukázala, že OPORA se zastaví a nikdo neví proč:

- srdce čekalo minuty na zápis do OPORY a vypršelo (timeout 60 s), příčina jen v profileru;
- karty 2.13b a 2.16b Ample nešly převzít dvakrát po sobě z různých důvodů (pin SQL kontextu, chybějící obsah nové karty);
- důvod byl vidět jen po ručním dotazu do SQLite nebo v textu odpovědi jednoho HTTP volání.

Inventura (§8) potvrdila, že většina chyb končí v `LOGGER` bez konfigurace logování
(stderr procesu, INFO se zahodí). Chyby srdce v paměti zmizí restartem. Odmítnutí 409/428/503
a neošetřená 500 se nikam nezapíšou. Chyba tahu Pletora se uloží jako běžná odpověď.
Frontend neodesílá nic.

Cíl: **jeden souhrnný deník chyb**, který čte člověk ve Velínu i agent jedním příkazem. U každé
chyby je vidět, co se stalo, kde, komu, proč a čím to uvolnit. Opakování se nesčítá do záplavy
řádků, ale do počtu u jednoho záznamu. Takže je vidět i cyklení.

## §1 Co je chyba (druhy)

| Druh | Příklad z dneška | Jak vzniká |
|---|---|---|
| `exception` | výjimka plánovače, uzlu toku, hlídače gitu | zachycená výjimka / log WARNING+ |
| `refusal` | 409 „A human must reopen confirmed cards“, 428, 403 brány | odpověď API ≥ 400 kromě 404 čtení |
| `timeout` | `opora_heart.py brief` → `server_unreachable` po 60 s | selhání v deníku dávky srdce |
| `slow` | agent-state 65 s pod zámkem projektu | pomalý požadavek > 30 s |
| `blocked` | karta nejde převzít (`unavailableReason`), pin SQL kontextu | detektor nad stavem karet / integritou |
| `stall` | karta vydaná a nikdo ji nepřevzal, uzel toku bez heartbeatu, dávka 3× delší než obvykle | detektor času |
| `loop` | srdce opakuje stejný neplatný příkaz (`escalate`), stejná chyba 5× za hodinu | detektor opakování (počet u otisku) |
| `integrity` | pin 302 vs 303, zmrazené pokrytí | checkpoint pinu |
| `ui` | pád komponenty, neošetřený promise ve Velínu | frontend hlášení |

## §2 Záznam

Jedna tabulka `opora_errors` v `registry.sqlite` (přežije restart, je napříč projekty):

```
id, fingerprint, first_at, last_at, count, resolved_at,
severity (warn|error|critical), kind (§1), source (heart|pletor|flow|gate|card|linie|preview|server|integrity|ui|agent),
project, workspace, subject (card/ticket/run/batch/request id),
actor_kind, actor_name, session,
message   – česká věta: co se stalo a proč (pro člověka i agenta),
cause     – technický text ≤ 2000 znaků, přes steps.redact,
lever     – čím to uvolnit (příkaz, místo ve Velínu, kdo musí jednat),
data      – JSON s odkazy (soubor:řádek, endpoint, kód, trvání)
```

- `fingerprint` = source + kind + subject + normalizovaná zpráva (bez čísel a ID). Stejná chyba zvedne
  `count` a `last_at`, nevznikne nový řádek. **Cyklení = rostoucí count.**
- `resolved_at` nastaví detektor, když podmínka zmizí (karta jde převzít, pin prochází). Nová výskyt téhož
  otisku záznam znovu otevře.
- Retence: vyřešené 30 dní, otevřené drží vždy. Strop 100 000 řádků.
- Nic z těla požadavků, žádné tajemství: jen cesta, kód, krátký redigovaný text.

## §3 Zápis: jedna funkce, mnoho zdrojů

`backend/app/errors.py`: `record(source, kind, message, *, project, subject, actor, cause, lever, data, severity)`.
Nikdy nevyhodí výjimku (deník nesmí shodit to, co hlídá). Zápis mimo zámek projektu, vlastní spojení.

Napojení (podle §8):

1. **Logování procesu.** Handler na kořenový logger: každé `LOGGER.warning/exception` → `exception`.
   Zavírá největší díru (plánovač, wakes, hlídač gitu, smyčky PR/rebase/review/reconciliation, Pletor monitor).
2. **Server.** Obecný `exception_handler(Exception)` → 500 + záznam. Odmítnutí 409/428/403/503
   z `factory.py` → `refusal` (warn), deduplikované.
3. **Srdce a tok.** Dávka se stavem ≠ ok a každé `failures` z `batches.jsonl` → `timeout`/`exception`/`refusal`.
   `heart.errors`, `gitError`, spánek po limitu. `flow_log_events node.failed` a obnova uzlu bez heartbeatu.
4. **Pletor a Linie.** Chyba tahu (dnes uložená jako běžná odpověď) a neúspěšné akce (`ok:false`).
   `linie.block`, odmítnuté merge/accept, selhání buildu náhledu, náhled, který spadl.
5. **Karty.** `unavailableReason` při claimu, `blockReason`, selhání zápisu PR (`enrollment_error`),
   reconciliation, auto-rebase konflikty, review sync.
6. **Integrita.** Checkpoint pinu, který neprojde (už dnes s čitelnou zprávou a příkazem).
7. **UI.** `window.onerror`, `unhandledrejection` a `WorkspaceBoundary` → `POST /api/errors/ui`
   (jen loopback nebo token, strop velikosti).
8. **Agenti a relace.** Dělníci brány a relace agent-office hlásí přes `/api/flow/log` kind `*.failed`
   (už vede do `opora_events`), deník to převezme.

## §4 Detektory (problémy, které nevyhodí výjimku)

Jeden tik (stávající plánovač toku, každou minutu, levné dotazy):

- **Karta se dlouho nevydá / nepřevezme:** karta `ready` bez claimu > 30 min; claim `blocked` se stejným důvodem
  > 15 min → `stall` / `blocked` s důvodem a pákou.
- **Zaseknutý běh:** uzel toku bez heartbeatu > 5 min; dávka srdce > 3× typická doba; lease po termínu.
- **Cyklení:** otisk s count ≥ 5 za hodinu → `loop` (severity error). Srdce volá stejný neúspěšný příkaz
  v ≥ 2 dávkách. Ticket střídá stavy tam a zpět.
- **Čekání na člověka:** krok `human_only` nebo eskalace bez odpovědi > 2 h → `blocked` (warn).
- **Pomalost:** požadavek > 30 s (`slow_requests`), dávka s podílem zápisu ≥ 50 %.

Detektor zapisuje i vyřešení (`resolved_at`), takže deník ukazuje, co platí **teď**.

## §5 Čtení

- `GET /api/pletor/errors?project=&open=1&since=&kind=&format=text` čte agent i člověk. Text: nejdřív otevřené
  podle závažnosti a počtu, každá řádka „co · kde · kolikrát · od kdy · páka“.
- Velín → **Chyby**: tabulka otevřených, filtr zdroj/projekt, rozbalení na `cause` a `data`, odkaz na kartu/ticket/dávku.
- Průhled srdce (`/api/pletor/heart/explain`) a stav agentů odkazují na deník.
- Srdce a Pletor dostanou v podkladech „otevřené chyby projektu“ (jen počet a top 5), aby nestavěly na rozbitém.

## §6 Milníky

| Milník | Hotovo, když | Důkaz |
|---|---|---|
| M1 Jádro | tabulka, `record`, handler logování, 500 handler, odmítnutí 409/428/503, `GET …/errors` + text | testy záznamu, deduplikace, redakce; živě výjimka plánovače je v deníku |
| M2 Srdce, tok, Pletor, Linie | §3 body 3–4 | dnešní timeout `brief` a chyba tahu Pletora se objeví v deníku |
| M3 Karty a integrita | §3 body 5–6 | karta 2.13b s nedostupným claimem by byla v deníku s důvodem |
| M4 Detektory | §4 | test: karta ready 30 min → stall; 5× stejná chyba → loop; vyřešení zavře |
| M5 Velín a UI | panel Chyby, frontend hlášení | `npm test`, náhled, pád komponenty je v deníku |

Každý milník je vlastní úkol Linie, vlak PR (M2 z M1 atd.).

## §7 Dnešní problémy a co by deník ukázal

| Problém | Záznam |
|---|---|
| Srdce čeká na zápis, `brief` timeout 60 s | `timeout` heart, subject dávka, páka „pomalé požadavky serveru“ |
| agent-state 65 s pod zámkem | `slow` server, cesta a trvání |
| Pin SQL kontextu 302 vs 303 | `integrity`, zpráva s příkazem `schema_adopt.py` |
| Nová karta z plánu srdce nejde převzít | `blocked` card, důvod „content differs…“, po 15 min |
| Srdce volá `escalate`, který nástroj nemá | `refusal` → po opakování `loop` |
| 409 „A human must reopen confirmed cards“ | `refusal` card, páka „Velín → Autonomie“ |
| Strop 6 dávek za hodinu, spánek po limitu | `blocked` heart (warn), do kdy |
| Náhled 8810 neodpovídá | `stall` preview |
| Restart zahodí běžící dávku | `exception` heart + obnova uzlu |
| Logování bez konfigurace (INFO mizí) | odstraní M1 |
| Plná backendová sada přes 90 min (timeout bez výsledku) | mimo deník: patří do CI/testů, zmíněno jako dluh |

## §8 Inventura zdrojů (13. 11.)

Souhrn průzkumu kódu: srdce (`batches.jsonl` ano, `heart.errors`/`gitError` jen paměť), tok
(`flow_log_events node.failed`), plánovač/wakes/git hlídač/smyčky jen `LOGGER`, Pletor (chyba tahu
jako běžná odpověď, akce nikam, `linie.*` v `opora_events`), brána (odmítnutí nikam), karty
(`unavailableReason`/`blockReason` jen výpočet, `enrollment_error`, reconciliation, auto-rebase v tabulkách),
server (žádná konfigurace logování, žádný handler 500, `slow_requests` jen paměť), frontend (nic).
Nejbližší existující záznam je `opora_events` (čas, projekt, aktér, druh, data, retence 14 dní):
deník ho nenahrazuje. Události procesu zůstávají tam, chyby a jejich stav (otevřené/vyřešené, počet) jsou v deníku,
`*.failed` z `opora_events` se do deníku zrcadlí.

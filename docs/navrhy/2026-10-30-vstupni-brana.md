# Vstupní brána požadavků – jedna věta, jedno stanovisko

Stav: návrh k rozhodnutí (2026-10-30).

Podklady:
- zadání člověka z 30. 10. (požadavek, magnet, milník, „nelepit funkci na funkci“);
- průzkum kódu: `gate_tickets`, `heart/inputs.py`, `decision/sources.py`, `brief_vault_check.py`, `plan_lens_membership.py`, `project_schema.py`;
- zkušenost z Ample. Workflow změny embeddingu se málem rozvětvil (sektor S, obrazovka 3) dřív, než byl dokončený a ověřený.

## 1. Proč

Dnes každá věta člověka (panel srdce, lístek `change`/`ask`, fragment Schránky) probudí srdce a srdce ji zpracuje celým během Haiku.
To má tři následky:
- žádná věta se neposoudí vůči tomu, co se právě dokončuje;
- pět upřesnění jedné věci může vyrobit pět karet;
- nápad typu „přidej hybridní vyhledávání“ může vytlačit rozdělanou práci.

Chybí brána, která *před plánováním* rozhodne, zda vůbec vznikne nová práce.

Princip: **základy se dokončí a ověří dřív, než se staví další patro.** Rozšíření počká na splnění milníku. Oprava nutná pro milník a změna záměru jdou hned.

## 2. Model

| Úroveň | V OPOŘE | Nové? |
|---|---|---|
| Cíl aplikace | `project.json settings.goal` (snímek srdce `ZÁMĚR`) | ne |
| Magnet = schopnost aplikace přes FE/BE/DB | uzel plátna `kind: area`, „oblast je jedna schopnost“ (`docs/plan-lens.md`); příslušnost karet se řeší přes `plan_lens_membership` (`memberOf`) | ne |
| **Aktivní milník** | jeden na oblast: název a ověřitelná kritéria; každé kritérium ukazuje na karty, které ho dokládají | **ano** (`intake_milestones`) |
| **Požadavek** | změna chování s kritérii přijetí, patří k oblasti a případně k milníku; víc vstupů → jeden požadavek | **ano** (`intake_requirements`) |
| Realizační úkoly | karty plátna (`spec.steps`, `dod`, PR) | ne |
| **Vstup** | doslovný otisk věty: čas, zdroj, autor; je neměnný | **ano** (`intake_entries`) |
| Zadání pro LLM | `assignment` / `node-brief` se generuje až při převzetí a je připnuté na `acceptedRevision` (`opora_executions.pinned_digest`) | ne, už platí |

Strom říká, kam práce patří (oblast → milník → požadavek → karty). Vazby `next` říkají, co na čem závisí. Příslušnost se ukládá výslovně (`area_id`), ne pozicí na plátně.

## 3. Brána: stanovisko k jednomu vstupu

| Stanovisko (`verdict`) | Kdy | Co se stane |
|---|---|---|
| `duplicate` | otisk věty se shoduje s dřívějším vstupem | připojí se k jeho požadavku, **srdce se nebudí** |
| `done` | požadavek už je splněný | připojí se doklad (karta nebo PR), nevznikne práce |
| `extends_in_progress` | upřesňuje rozpracovaný požadavek | připojí se k němu; srdce vyhodnotí změnu rozsahu té karty (lístek `change`) |
| `fix_for_milestone` | chyba, bez jejíž opravy milník neprojde | srdce zařadí opravu do aktivního milníku |
| `changes_intent` | mění schválený záměr nebo předpoklad | srdce pozastaví dotčené karty, ukáže dopady a navrhne novou verzi plánu (`prune` / `unlink` / změna zadání). **Historie zůstává.** |
| `later_extension` | rozšíření nad aktivní milník | uloží se odložený požadavek s důvodem a podmínkou otevření („po splnění milníku X“). **Žádné karty, žádný detailní plán.** |
| `needs_info` | nejde zařadit | srdce položí jednu konkrétní otázku (eskalace) |

`duplicate` srdce nebudí jen u vět člověka (panel srdce, Schránka). Lístek `change`/`ask` od dělníka nebo prostředníka může být oprávněné opakování, třeba po selhání, proto srdce budí dál, jen se značkou duplicity v řádku vstupu.

Rozšíření se stane opravou jen tehdy, když se doloží, že bez něj kritérium milníku nesplníš. Pak ho člověk nebo srdce překlasifikuje novým vstupem.

## 4. Pipeline (levné vrstvy první, každá končí, jakmile rozhodne)

1. **determinism** (`backend/brain_opora/determinism/intake.py`) proběhne bez modelu:
   - normalizace: malá písmena, bez diakritiky a interpunkce, zúžené mezery;
   - `fingerprint` = sha256 normalizovaného textu;
   - shoda s dřívějším vstupem → `duplicate` a konec;
   - kandidáti z FTS5 (`intake_entries_fts`, bm25): nejbližší 3 požadavky a aktivní milníky oblastí.
2. **decision / Jev** (`backend/brain_opora/decision/intake.py`), dvě otázky v jednom volání `evaluate`:
   - `choice` oblasti nad ids oblastí s jejich názvy (vzor `sources.rank`);
   - `choice` stanoviska nad sedmi hodnotami z §3, kritéria jsou pevný text. Vstup člověka jde jen jako `state`, nikdy do instrukcí (vzor `brief_vault_check`).
   - Při `confidence < 0.6`, nedostupném Jevu nebo vypnutém povolení zůstane stanovisko `pending` a rozhodne srdce. Jev je zrychlení, ne podmínka.
3. **heart** se budí jen tehdy, když stanovisko není `duplicate`. Řádek vstupu v dávce nese stanovisko, oblast, milník a kandidáty, srdce je tedy nedohledává. Srdce:
   - potvrdí nebo opraví stanovisko (`opora_heart.py intake --entry --verdict --requirement …`);
   - jedná podle §3;
   - u `later_extension` nesmí plánovat karty. Pravidlo je v promptu srdce a ve snímku (sekce `VSTUPY`).
4. **Zápis:** stanovisko, vrstva (`determinism | jev | heart`), zdůvodnění na jednu větu a cena (USD Haiku z dávky, počet volání Jevu).

Odhad ceny: duplicita 0 USD. Jev je jedno volání. Srdce běží jako dosud, jen s hotovým zařazením, a nemusí hledat.

## 5. Úložiště (aditivní tabulky v `project.sqlite`, schéma `database/schema/intake_schema.py`)

- `intake_entries(id ie_…, workspace_id, source heart_message|gate_change|gate_ask|brief_fragment, source_ref, text, fingerprint, created_at, verdict, layer, area_id, milestone_id, requirement_id, confidence, reason, cost_usd, jev_calls)`. Index je na `fingerprint`.
- `intake_entries_fts`: FTS5 nad `text` (ověřeno, sqlite v projektu FTS5 má).
- `intake_requirements(id rq_…, workspace_id, area_id, milestone_id, title, status open|deferred|done|superseded, open_condition, supersedes, created_at)`.
- `intake_milestones(id ms_…, workspace_id, area_id, title, criteria JSON [{id, text, cards[]}], status active|done|superseded, created_at)`. Právě jeden `active` na oblast. Kritérium je splněné, když jsou všechny jeho karty `done.confirmed`. Splnění se počítá, neukládá.

Žádná existující tabulka se nemění.

Vektory se zatím neukládají. FTS5 a Jev stačí a e5 worker zůstane na vyžádání. Vektory přibudou až při doložené díře (nejasné duplicity, které FTS5 nechytí).

OpenViking je jen volitelné zrcadlo, zdrojem pravdy zůstává SQLite.

## 6. Rozhraní

- Zápis vstupu probíhá uvnitř serveru, bez nového veřejného zápisu:
  - `supervisor.message` (panel srdce);
  - `gate.record` pro `change`/`ask` od člověka nebo dělníka;
  - uložení fragmentu Schránky (`brief_vault`) s `kind ∈ brief|question`.
- `GET /api/intake?project=&workspace=` vrací pohled „Požadavky a plán“: oblasti, u každé aktivní milník, kritéria (hotovo/nehotovo), otevřené požadavky, nové vstupy a odložené požadavky s podmínkou.
- `POST /api/intake/milestone` (aktivace nebo změna milníku): smí jen člověk nebo srdce (`428 humanRequired` pro ostatní). Změnu aktivního milníku srdce jen navrhne eskalací a potvrdí ji člověk.
- `opora_heart.py intake …` slouží srdci k potvrzení nebo opravě stanoviska. `opora_heart.py milestone …` slouží k návrhu milníku.

## 7. Povolení a strop

- Volání Jevu posílá text člověka mimo stroj. Proto je ve výchozím stavu **vypnuté** a zapíná se per projekt v nastavení `brain.intake.jev` (člověk, UI nastavení projektu).
- Strop: `brain.intake.jevPerDay` (výchozí 200). Po jeho vyčerpání zůstane stanovisko `pending` a rozhodne srdce.
- Pipeline bez Jevu (jen determinismus a srdce) funguje vždy.

## 8. Co se nemění

- Srdce zůstává jediný zapisovatel plátna. Brána karty nevytváří.
- Brána uzavření karty, lidská brána a zeď se nemění.
- Žádný automatický „rewind“. U změny záměru se nahrazené části označí (`supersedes`), historie i doklady zůstávají a dělník dostane nový čistý kontext z nové verze plánu.

## 9. Řezy

1. **Řez 1 (backend):** tabulky, determinismus (otisk, duplicita, FTS5), zápis vstupu ze tří zdrojů, stanovisko `duplicate` nebo `pending`, řádek vstupu pro srdce se stanoviskem a sekce `VSTUPY` ve snímku, `GET /api/intake`.
   Proti §4 se liší dvě věci: kandidáti jsou zatím 3 nejbližší dřívější *vstupy* téhož prostoru (požadavky a milníky ještě nevznikají), a FTS5 drží vlastní kopii textu s `entry_id`, ne vnější obsah (rowid tabulky s textovým klíčem se smí po VACUUM přečíslovat). Eskalace srdce (`ask` od srdce pro člověka) vstupem není.
2. **Řez 2:** Jev (`decision/intake.py`), povolení a strop, `opora_heart.py intake`, pravidlo `later_extension` v promptu srdce.
3. **Řez 3:** milníky (`intake_milestones`, kritéria z karet), `opora_heart.py milestone`, potvrzení člověkem.
4. **Řez 4 (frontend):** pohled „Požadavky a plán“ ve Velínu, jeden dílek na oblast.

## 10. Ověření (scénář Ample, magnet „Vyhledání správných podkladů“)

- „přidej hybridní vyhledávání“ → `later_extension`, podmínka „po splnění milníku Spolehlivé vyhledávání“, žádná karta;
- tatáž věta podruhé → `duplicate`, srdce se nebudí;
- „vyhledávání vrací dokument cizí organizace“ → `fix_for_milestone`;
- „embedding chceme zpátky na Cohere“ → `changes_intent`, karty milníku jsou pozastavené a návrh nové verze je v rozhodnutích.

Testy vedle modulů. Celá backend sada se nespouští, jen cílené testy.

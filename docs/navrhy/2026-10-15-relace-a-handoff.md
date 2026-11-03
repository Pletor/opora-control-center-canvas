# Relace A – handoff (2026-10-15)

Zadání HERMES-A-20261015: pipeline a skutečná tvorba buněk/sítě podle originálů 00–09
(`I:/1. Projekty/08_AGI/neuron-brain`). Nejmenší spustitelný řez: buňka s cílem, vstupem, výstupem,
pamětí a vazbou na další krok; jeden průchod zadání → rozhodnutí → výkon/artefakt → skutečné ověření → poučení.

## Stav na konci směny (17:40) – HOTOVO vs. OTEVŘENO

Pokyn člověka (17:40): „Pokračuj dále v úkolech, vylepšuj procesy, které se vytváří, nevytvářej nic nového.“
Všechno níže je **necommitnuté a nestageované**. K16 jako celek **není akceptovaný**.

**HOTOVO (ověřeno testy, kritikem a izolovanou ukázkou):**
- **K15 buňka:** commit `3116d4f`. Následná oprava A3 (`checks-mismatch`) je necommitnutá.
- **K16 duel:**
  - konverzace;
  - síla argumentů (nekalibrovaná, přejmenovaná z P);
  - deduplikace přesných argumentů;
  - vazba představy na verzi a odmítnutý replay;
  - uplatnění vítězného směru: fragment, projekt; karta a keep se neuplatní;
  - fail closed na smazaném předmětu nebo předkovi;
  - no-op při totožném textu;
  - neoživení starých bran;
  - pravdivé texty v UI („uplatněno: zadání má nový text“, „neuplatnil se: <důvod>“, ukazatel „rozhodnuto: …“);
  - bezpodmínečný e2e důkaz fronty i se způsobilým konkurentem.
- **README duelu** srovnané se skutečným chováním (17:38): `duel/README.md:27` už neslibuje „agenti pokračují“.
- **Poslední plné ověření** (K16-FINAL, 17:34):

  | Příkaz | Výsledek | Exit |
  |---|---|---|
  | `uv run pytest backend` | 2 219 passed / 4 skipped / **2 failed** (známé testy graphify `test_generate_uses_official_graphify_and_persists_output` a `test_real_graphify_refresh_publishes_only_selected_project`) | **1** |
  | skripty | 134 passed | 0 |
  | `npm test` | 1 270 passed | 0 |
  | build | v pořádku | 0 |

  Oprava README je jen dokumentace, sada se kvůli ní znovu nespouštěla.
- **Izolovaná ukázka 8745** (vlastní PID 14800, dočasná data `…\scratchpad\demo-duel-accept`, `--no-build`): servíruje `/assets/index-BvxPgYi4.js` (build 17:25:36), ve kterém je nový text 1× a starý příslib 0×. Ověřeno čtením přes HTTP, 17:40.

**OTEVŘENO (konkrétní nedotažení stávajícího procesu, ne zámysl stavět nové):**
1. **Ztracená čekající `learned`:** uplatnění duelu vypne bránu `learned` neúspěšného kola, takže poučení z neúspěšné realizace nevznikne. Historie a už zapsané poučení zůstávají (K16-PROOF, sonda E/F).
2. **Limit kol:** adopt po 3. neúspěchu přepne fragment do vyčerpání, opakované duely limit neobejdou. Text o uplatnění je už pravdivý, pokračování určuje fronta (K16-PROOF, sondy C/D/D2).
3. **Ověření v prohlížeči (BLOCKED, 17:39):** Chrome DevTools MCP se po restartu relace nepřipojí, profil `C:\Users\Admin\.cache\chrome-devtools-mcp\chrome-profile` drží Chrome z předchozí relace („The browser is already running…“). Pokus 1 selhal, pokus 2 nahrazen čtecí kontrolou bundle přes HTTP. Vykreslený text v DOM tedy není doložen, jen to, že servírovaný build text obsahuje. Odblokování = zavřít ten Chrome z předchozí relace (vlastník relace A), nový server ne.
4. **BLOCKED k rozhodnutí:** atestace běhu a identita aktéra (K15 §5), kalibrace síly argumentů, sémantické duplicity, `details_summary` počítá všechny body představy.
5. **Commit:** čeká na pokyn (Hermes rezervoval index pro relaci B).

**Nejmenší navazující oprava stávajícího procesu (nic nového):**
- U bodu 1 bez nového pravidla a bez automatického poučení: v `opora_cycle.py` / `cycle.md` doplnit krok POTVRZOVATELE „před `duel-decide` zapiš `learned` neúspěšného kola“, tedy stávající brána ve stávajícím postupu.
- U bodu 2: jen text ve stávající nápovědě `/next` u vyčerpaného fragmentu „směr změněn duelem – čeká na člověka“, pokud o to člověk stojí.

## Checkpoint 1 (start)

- HEAD `416fc2f`. Necommitnuté cizí: `docs/navrhy/2026-10-14-vyvoj-tajemstvi-opory-v-platne.md`, `docs/navrhy/2026-10-15-relace-b-handoff.md` (nesahat).
- Vlastněné cesty: `backend/editor/brief_vault/`, `backend/api/editor/` jen router Schránky, `frontend/editor/brief-vault-dock/`,
  `frontend/editor/node-detail/brief-vault/`, `backend/brain/seed/opora-control-center/skills/opora-control-center/` (cycle nástroje), `docs/schranka-*`, tento handoff.
- Nesahám: node-card, board, control-tower, area, project/maps, `App.tsx`, `CLAUDE.md`, shared types, `database/schema`, cizí návrhy.
- První ověřitelný krok: mapa princip → implementace → mezera (subagent čte 00–09 a kód Schránky), pak kontrakt řezu v `docs/schranka-bunka.md`.

## Mapa originál → OPORA (výtah)

- Hotovo: impulz a rozsah (`scoped`), polarity (`weighed`), navrhovatel ≠ potvrzovatel (`propose`/`yes`), rozhodnutí ano/jinak/ne, mez smyčky (3 kola).
- Částečně: buňka (disciplína je jen štítek), typovaný mikrokrok (chybí KDE a spustitelné OVĚŘENÍ), paměť (poučení se jen čte, `kind` nevázaný na výsledek).
- **Chybí, jádro mezery:** mezi `placed` a `verified` se nic nevykoná a `verified.actual` jen tvrdí navrhovatel. Karta vzniká bez `checks` a `goal_mode`, proto pipeline karty nemá co spustit.
- Chybí, mimo řez: DNA projektu, baseline, kontroly podle typu mikrokroku, podmínka platnosti poučení.
- Rozpory originálu s OPORA (originál volá LLM z aplikace přes placené API a má druhé úložiště paměti) jsou vyřešené tím, že orchestrátor je vnější agent. Nejde o BLOCKED.

## Kontrakt řezu: `docs/schranka-bunka.md` (K15)

`synthesized.checks` → karta `checks` + GOAL → vykonavatel vytvoří artefakt → ověřovatel `opora_cycle.py run-checks` skutečně spustí kontroly → `verified.actual.run`, server hlídá shodu kontrol a `tests` s exit kódy, vykonavatel ≠ ověřovatel → `learned.kind` podle výsledku.

## Checkpoint 2 (dávka 1)

- Hotovo (necommitnuto, čeká na opravy po kritikovi):
  - backend `synthesized.checks`, `verified.actual.run`, pravidla buňky, karta s `checks` + GOAL;
  - CLI `run-checks`;
  - `cycle.md`;
  - e2e `test_opora_cell.py`: skutečný uvicorn nad `tmp_path` a skutečný běh pytest. Kolo 1 skončí `fail` → antipattern → nové kolo, kolo 2 `pass` → pattern. Vykonavatel nesmí ověřit sám sebe ani zapnout `verified`.
- Testy: backend 2 105 passed, 2 povolené graphify failed; skripty 106 passed; e2e 1 passed.
- Nezávislý kritik (ChatGPT/Codex) našel:
  - 2 vysoké: podvržený `run`; vykonavatel ovládá obsah testů;
  - 3 střední: `extend` bez `checks`; Windows cesty v `shlex`; rozdílná pravidla serveru a CLI.
  - Opravy zadány, viz kontrakt §3 a §5.
- **BLOCKED → Hermes:** atestace výsledku běhu. Server příkazy nespouští a identita aktéra je deklarovaná, takže `run` je přiřazený, ne atestovaný doklad (`docs/schranka-bunka.md` §5). Rozhodnout je potřeba ověřenou identitu aktéra, nebo běh kontrol mimo vliv navrhovatele.

## Checkpoint 3 (dokončení K15)

- **Opravy kritika (1 korekční kolo):**
  - podvržený `run`: návrh podává jen `run.verifier` a vykonavatel bránu nezapne;
  - testy pod kontrolou vykonavatele: `--tests` překryje kopii pracovní složky a smaže `conftest.py` a podobné;
  - jedna syntaxe příkazu na serveru i v CLI: 13 společných `CHECK_VECTORS`;
  - kontroly jsou měřítko napříč koly: změnu nebo přidání v kole ≥ 2 smí jen člověk;
  - logika buňky v `brief_vault_cell.py`.
- **Untrusted:** server razítkuje `runTrust: "reported"` a klient ho poslat nesmí. UI ukazuje „běh nahlášen – neatestováno“.
  Na `verified` se neváže uzavření ani schválení karty; ověřeno grepem, `verified` čtou jen kola, poučení a Zrcadlo.
- **Vlastní nález:** `brief_vault_proposals._without_error` ignoroval jen `predictionError`, takže použitý návrh s `runTrust` zůstával `pending`.
  Opraveno přes `SERVER_FIELDS` a pokryto e2e testem.
- **Skutečný průchod (e2e `test_opora_cell.py`, uvicorn nad `tmp_path`, skutečný pytest):**
  1. Kolo 1: vykonavatel podstrčí `assert True` bez `slug.py` → `--tests` → `fail`.
  2. Poučení antipattern.
  3. Nové kolo, vykonavatel dodá `slug.py` → `pass`, `runTrust: reported`.
  4. Poučení pattern, viditelné v `lessons` disciplíny.
- **Návrh odděleného ověřovatele** (`docs/schranka-overovatel-navrh.md`, jen k review): zapsán rozpor z review Hermese.
  Jiný účet sám nestačí; je potřeba sandbox bez klíče oddělený od podepisovače a manifest s příkazy, závislostmi a vazbou proti replay.
  Žádný runtime, auth ani konfigurace.
- **Zbývá:** karta založená v kole 1 bez `checks` je přes `extend` nedostane. Kola ≥ 2 ale `checks` přidat nesmí, takže nesoulad nevznikne.

## Dávka A3 (10:52–): shoda měřítek karta ↔ synthesized

Reprodukce (`backend/editor/brief_vault/test_brief_vault_cell_card.py`, `tmp_path`, před opravou):

| Případ | `synthesized.checks` kola 2 (člověk) | `planned` / `placed` | karta po `placed` |
|---|---|---|---|
| A→B | B | 200 / 200 | A + `until_checks_pass` |
| žádné→B | B | 200 / 200 | bez `checks`, bez GOAL |

**Tichý nesoulad měřítek.** Ověřovatel měří proti B, pipeline karty proti A (nebo proti ničemu). Tvrzení
`docs/schranka-bunka.md:35–39` „zůstávají shodné“ neplatí pro bypass člověka. Ochrana, která by nesoulad zablokovala,
neexistovala.

- **Bod blokace:** `build_plan`, existující karta za F (`brief_vault_plan.py:215–223`).
- **Nejmenší oprava (fail-closed, zadána):** při nesouladu `checks`/GOAL karty se `synthesized` vrátí `planned` 409 `checks-mismatch` pro každého aktéra. Kontroly karty upraví člověk ručně (chráněná pole), pak se plánuje znovu.
- **Co oprava nedělá:** nevytváří žádnou novou cestu zápisu chráněných polí.
- **BLOCKED (politika, neimplementováno):** má `extend` od člověka přenášet `checks`/`goal_mode` na kartu? To je nová politika chráněných polí. Rozhodne Hermes nebo člověk.

### Výsledek A3 (stav k ~11:35, NEcommitnuto, nestageováno)

Změny (vlastník relace A, vše v `backend/editor/brief_vault/` + `docs/schranka-bunka.md`):
- `brief_vault_plan_update.py`:
  - `checks_mismatch(node, synthesized)` porovnává fail-closed;
  - za neplatnou strukturu `checks` karty považuje: není seznam, nebo položka není přesně `{id: str, command: str}`;
  - nesoulad je i to, když `goal_mode == "until_checks_pass"` neplatí právě tehdy, když `synthesized` nese kontroly;
  - legacy `{}`, `(None, None)` a `{"checks": []}` nejsou nesoulad.
- `brief_vault_plan.py`: `build_plan` u existující karty za F (`lead`) při nesouladu → `blocked`, reason `checks-mismatch` (409). Platí pro každého aktéra a nic se nezapisuje.
- `test_brief_vault_cell_card.py` (nový, asertivní):
  - A→B i žádné→B: `planned` 409, karta i revize beze změny. Člověk ručně upraví kartu (`POST /api/graph`) → `planned`/`placed` 200 a karta = B;
  - shodné kontroly projdou;
  - legacy bez `checks` projde, karta zůstane `(None, None)`;
  - změna karty po `planned` a před `placed` → `placed` 409 `checks-mismatch`;
  - změna karty uvnitř `placed`, po přestavbě plánu a před zápisem (monkeypatch `checkpoint`) → 409 „Plátno se změnilo“, karta zůstane C, bez revize. Ochrana: zámek grafu `brief_vault.py:324` + digest v `canvas_plan.py:115–118`;
  - jednotkové testy predikátu.
- `test_brief_vault_plan.py`: existující karta K v testu, který ověřuje, že `extend` nepřenáší kontroly, teď nese shodné `checks`. Karta bez `checks` = `checks-mismatch`.
- `docs/schranka-bunka.md` §3 bod 2: nepravdivá věta „zůstávají shodné“ je nahrazená pravidlem 409 `checks-mismatch`.

Moje běhy po stabilizaci (skutečné exit kódy, bez maskování):
- `uv run pytest backend/editor/brief_vault/test_brief_vault_cell_card.py backend/editor/brief_vault/test_brief_vault_plan.py -q` → 26 passed, **exit 0**.
  Hermesův snapshot z 11:19 (24 passed / 1 failed `test_checks_mismatch`) vznikl uprostřed editace: starý test čekal tolerování klíče navíc. Finální test čeká nesoulad.
- `uv run pytest backend/editor/brief_vault -q` → 255 passed, **exit 0**.
- `npm test` → 179 souborů / 1 237 testů, **exit 0**; `npm run build` → **exit 0**. Frontend se v A3 neměnil.
- `uv run pytest backend -q`: 2 119 passed, 4 skipped, 2 failed, **exit 1**. Selhaly jen 2 známé testy graphify (`test_graphify_routes.py::test_generate_uses_official_graphify_and_persists_output`, `test_map_refresh.py::test_real_graphify_refresh_publishes_only_selected_project`, `assert 'failed' == 'succeeded'`). Jiné selhání není.

Nezávislý kritik (Codex) nad diffem, 1 korekční kolo:
- **Doložené a opravené:**
  - predikát tiše zahazoval neplatné položky;
  - GOAL bez kontrol neprošel jako nesoulad;
  - souběh uvnitř `placed` doložen řízeným testem.
- **Hypotézy bez důkazu, mimo scope, žádná nová politika:**
  - dětské karty: kontroly patří jen kartě za F (`card_of` `lead`), záměr;
  - karta v jiné vrstvě: `existing_card` hledá jen ve vrstvě plánu, beze změny, existující chování.

Zbývající BLOCKED:
1. Přenos `checks` přes `extend` (nová politika chráněných polí).
2. Atestace běhu (`docs/schranka-bunka.md` §5, `docs/schranka-overovatel-navrh.md`): sandbox bez klíče oddělený od podepisovače, manifest a ochrana proti replay.

Co běží: nic. Subagenti relace A jsou hotoví. Cesty relace B (`frontend/editor/node-detail/*`, `sector-detail/*`, `relace-b-handoff.md`) A nemění.

## K16 Duel (přímé zadání člověka, ~11:45)

Člověk: Laboratoř je „klikačka“. Chce do výstupu agentů vstoupit živě, slovem, a každou změnu směru, ať od agenta,
nebo od něj, rozhodnout **duelem**: argumenty, grill, syntéza. Pravděpodobnost přiblížení k představě se má počítat
matematicky a staré lepší zadání se nesmí zahodit jen proto, že LLM přišlo s novým.

- **Kontrakt:** `docs/schranka-duel.md`.
  - Duel je fragment `kind: duel` s detaily v JSON, bez nové tabulky.
  - `P(B > A) = σ(logit 0.35 + Σ sign·s/10·w)`, důkazní břemeno nese změna.
  - Rozhodnutí počítá server (`adopt ≥ 0.75`, `keep ≤ 0.40`, jinak syntéza); override jen člověk s důvodem.
  - Trend představy počítá bayesovská regrese, `P(β > 0)` přes Studentovo t.
- **Běží (vlastník relace A, 4 subagenti):** matematika `brief_vault_duel_math.py`, backend ops a `/next`, CLI `duel`, frontend sekce Duel (konverzační vstup, živý poll).
- **Změna §11 neurony:** UI už nejen zobrazuje. Člověk píše do konverzace duelu, ale stále bez tlačítek.

### K16 review (Hermes 13:05): duplicity a degenerovaný trend, jen čtecí prověrka

Stav při převzetí:
- K16 je hotová a necommitnutá. Subagenti neběží.
- Ukázková instance běží na 8745 s dočasnými daty (scratchpad `demo-duel-data`).
- Nabídka člověku (krátká id výměn, falešný banner „Změna mimo toto okno“) čeká na jeho odpověď.

**Reprodukce** (`scratchpad/probe_duel_dup.py`, izolovaný `TestClient` nad dočasnou složkou, HEAD `f44f326`, `brief_vault_duel_math.py` sha256 `3dc20f36…71f25a9`):

| Pokus | Výsledek |
|---|---|
| matematika, 1× claim B (síla 8, `evidenceOk`, stejný text a doklad) | p = 0.6412884544908589, n = 1, `synthesis` |
| matematika, 3 totožné kopie (jiné id) | p = 0.9517065495778346, n = 3, `adopt` |
| **API:** 4× totožný claim | 1.–3. 200, 4. 400 (`MAX_CLAIMS`). Skóre 3× 8: GET p = 0.9517, n = 3, `canDecide` true; `duel-decide` → **200 `adopt`** |
| `vision_trend` [1,2,3] / [1,2,3,4] | p = 1.0, se = 0.0, `approaching` (degenerované, ne empirická jistota) |

Exit kód sondy 1 způsobil až úklid dočasné složky (WinError 32, zamčený `hooks.sqlite`), výsledky se vypsaly předtím.

**Nejmenší návrh opravy (neimplementováno, ke schválení):**

1. **Přesné duplikáty (deterministicky, server).** Otisk výměny = sha256 normalizovaného textu (malá písmena, sjednocené mezery, bez diakritiky) + seřazené `source|quote`. Stejný otisk jako dřívější výměna duelu (kterékoli strany) → 409 „stejný argument už v duelu je (#id)“. Tím zmizí případ z reprodukce.
2. **Významové duplikáty: oracle = soudci.**
   - `duel-score` dostane volitelné `duplicateOf: turnId`, starší výměnu téže strany. Většina soudců výměny ho označí → váha 0, výměna se nepočítá do n.
   - Pojistka bez soudců: klesající výnos v rámci strany, k-tý nejsilnější příspěvek ×1/k.
   - **Samotné 1/k nestačí:** 3 kopie → σ(logit 0.35 + 1.2·(1 + ½ + ⅓)) = 0.829, tj. stále `adopt`.
3. **Kalibrační omezení rozhodnutí `adopt`:**
   - n nezávislých (neduplicitních) argumentů ≥ 3;
   - **≥ 2 různí soudci**;
   - strop součtu příspěvků jedné strany 2.5 logitu, takže jedna strana sama dosáhne nejvýš σ(−0.619 + 2.5) = 0.868;
   - strana A byla slyšet: má hodnocenou výměnu, nebo nezodpovězenou `grill` B;
   - jinak `synthesis`.
   - Strop 1.5 by `adopt` bez slabé A znemožnil úplně (σ = 0.707 < 0.75), proto 2.5.
4. **Trend představy.**
   - Prior šumu skóre soudce σ0 = 1 bod, ν0 = 2: `s² = (SSE + ν0·σ0²)/(n − 2 + ν0)`, df = n − 2 + ν0.
   - [1,2,3] → se = 0.577, t = 1.732, df 3 → **p = 0.909**. [1,2,3,4] → se = 0.316, df 4 → **p = 0.983**. Spočítáno existující `student_t_cdf`.
   - Stav „přibližujeme se“ až od n ≥ 4.
5. **Pojmenování:** P zobrazovat jako „nekalibrovaná síla argumentů“, ne pravděpodobnost, dokud není kalibrace (bod níže).

**BLOCKED (chybí oracle nebo politika):**
- Kalibrace P na skutečné výsledky. Potřebuje výstupní oracle, např. zda přijatý směr později prošel `verified` s testy `pass`, a politiku, kdy se hodnotí (Brier, křivka spolehlivosti). Bez něj nejsou prahy 0.75/0.40 ani `p0 = 0.35` empiricky podložené.
- σ0 = 1 je provizorní. Odhad z rozptylu mezi soudci jde, až budou ≥ 2 soudci na výměnu.
- Odolnost proti sockpuppetům (vymyšlená jména soudců) závisí na ověřené identitě aktéra, stejný blocker jako atestace K15.

Nezávislá kritika finální opravy je nutná, až se bude implementovat.

### K16-DEDUP (Hermes 13:32, převzato 13:30, NEcommitnuto, nestageováno)

Nejmenší oprava přesných duplicit argumentu `claim`, nic víc. Nová pole, váhy, prahy ani priory nepřibyly.

- **Otisk:** `(side, " ".join(str(text or "").split()), frozenset((source, quote)))`.
  - Mezery sjednocuje `str.split`, včetně NBSP. U+200B a další zero-width znaky se nenormalizují.
  - Velikost písmen a diakritika se zachovají; pořadí a opakování položek evidence nerozhodují.
  - Chybějící nebo null evidence = prázdná množina. Ne-dict a nehashovatelné položky se přeskočí. `quote` None ≡ "".
  - Autor, id, čas a refs do otisku nepatří. Různé strany = různé výměny.
  - Není to sémantická deduplikace ani doklad nezávislosti.
- **Zápis (`brief_vault_duel.py`):** totožný claim strany vrací 409 s id původní výměny a revize se nemění. Totožnost se kontroluje před mezí kol i mezí claimů. Mez `MAX_CLAIMS` počítá unikátní otisky.
- **Čtení (`brief_vault_duel_math.py`):** platí první výskyt. Kopie má `delta` 0 s důvodem „opakovaný totožný argument“, nepočítá se do n a její skóre se nepoužije nikde, ani jako vyvrácení. `refs`, `rebuttedBy` a `concede` na kopii míří na první výskyt.
- **RED → GREEN, 3 kola:**

  | Kolo | RED (cílené duel + math) | GREEN |
  |---|---|---|
  | 1 | 4 failed / 59 passed, exit 1 | 63 passed, exit 0 |
  | korekce 1 | 8 failed / 70 passed | 78 passed |
  | korekce 2 | 2 failed / 78 passed | 80 passed, exit 0 |

  - Po korekci 2 dále: e2e `test_opora_duel.py` 1 passed, exit 0; `brief_vault` + `api/editor` + skripty 534 passed, exit 0. Hlásí subagent.
- **Sonda** `scratchpad/probe_duel_dup2.py` nad finálním kódem (math sha256 `fed63cbe…5561251`), **exit 0**:
  - matematika: 1 i 3 kopie → p = 0.6412884544908589, n = 1, `synthesis`;
  - API: kopie 2–4 → 409; GET p = 0.6413, n = 1; `duel-decide` → 409 (neobhájená syntéza, žádný `adopt`).
- **Nezávislý kritik (Codex):**
  - 1. kolo: 2 vysoké a 4 střední nálezy, vše opraveno v korekci 1.
  - Ověřovací kolo: body 1–3 a 6 opraveno. Bod 4 a nová vada (počítání kopií v mezi) opraveny v korekci 2.
  - Bod 5 (souběh, CAS) kritik z výřezu ověřit nemohl. Doloženo testem souběhu: jeden 200, jeden 409, revize +1 jednou. Test prošel už na starém kódu.
- **Plné ověření nad finálním kódem** (můj běh po korekci 2):

  | Příkaz | Výsledek | Exit |
  |---|---|---|
  | `uv run pytest backend` | 2 199 passed, 4 skipped, 2 failed (jen známé testy graphify, `assert 'failed' == 'succeeded'`) | **1** |
  | skripty | 134 passed | **0** |
  | `npm test` | 184 souborů / 1 265 testů | **0** |
  | `npm run build` | v pořádku | **0** |
- **Nález nezávislého revieweru Codex (13:55), potvrzený čtením kódu, NEopraveno (mimo scope a limit dávky K16-DEDUP):**
  1. **Replay představy:** `vision_set` (`brief_vault_duel.py:380–389`) ověří jen to, že `fromDuel` je rozhodnutý projektový duel s `adopt`/`synthesis` a že se text liší. Chybí vazba na revizi představy, proti které se duel vedl, i značka „použito“.
     - Scénář: V0 → D1 adopt → V1 → D2 adopt → V2 → `vision-set fromDuel D1` vrátí V1 bez nového duelu.
  2. **Trend přes různé cíle:** `vision_align` (`:392–409`) ukládá body bez revize představy a změna představy je nevynuluje. `vision_trend` tak míchá hodnocení proti různým cílům.
  - **Nejmenší návrh opravy:**
    - `duel-open` se `subject: project` uloží `incumbent.ref = {fragmentId: představa, revision: aktuální}`. `vision-set fromDuel` projde jen při `ref.revision == aktuální revize představy`, jinak 409 „duel byl veden proti starší představě“. Tím zmizí replay i zastaralé duely, bez nové tabulky.
    - Bod trajektorie nese `visionRevision`. `vision_trend` počítá jen body aktuální revize, starší zůstanou v historii. Po změně představy se ukáže „nová představa, málo dat“.
    - Regresní testy: scénář V0 → V1 → V2 → replay D1 = 409 a trend po změně představy začíná od nuly. Legacy body bez `visionRevision` patří k revizi, při které byly zapsány, podle pořadí revizí.
- **Zůstává BLOCKED k review:** sémantické duplicity a jejich oracle (soudci), kalibrace P, ≥ 2 nezávislí soudci, prior trendu a ověřená identita aktéra. Viz návrh v sekci K16 review výše.

### K16-APPLY a jednodušší duel (přímé zadání člověka 14:10, NEcommitnuto)

Člověk:
- „Pokud v duelu vyhraje nový směr, jde se tím směrem.“
- „Důležité je jednoduché používání.“
- „Kde vidím výsledek sítě vůči 00–09?“ Odpověď: `docs/schranka-mapa-originalu.md`.

- **Uplatnění vítězného směru** (`brief_vault_duel_apply.py`, ve stejné transakci jako `duel-decide`):
  - fragment + adopt/synthesis → nová revize textu, brány zneplatněné, `/next` od `scoped`;
  - projekt → představa, jen když sedí `visionRef`;
  - karta → `applied: false` (plátno je cizí cesta);
  - keep → beze změny;
  - když se předmět mezitím změnil → `applied: false` s důvodem, cizí změna zůstane;
  - ruční `revise`/`split`/`restore`/`set-discipline` představy → 409.
- **Souběh s Codexem (nezávislý reviewer, jiná relace):**
  - Ve 14:13 zapsal svou opravu replay a trendu do `brief_vault_duel*.py`, přestože jsem žádal, ať nezapisuje.
  - Můj subagent se zastavil, nic nepřepsal. Rozhodnutí koordinátora: převzít Codexovu vazbu (`visionRef`, `directionRevision`, body podle verze, starší body vynechat podle jeho §8) a postavit na ní uplatnění.
  - Codex pak předání potvrdil a dál nezapisoval.
- **Souběh s relací B:** upravila soubory v `brief-vault-dock` (`DisciplineSwitch.tsx`, `BriefVaultDock.tsx` `waiting/onWaiting`, `discipline-groups`, css, README). Frontendový agent je nepřepsal. Relace B je požádaná, aby úpravy v docku předem hlásila.
- **Jednodušší duel (frontend):**
  - krátká čísla výměn #1… (parser bere číslo i plné id);
  - nápověda na jeden řádek, další příkazy v rozbalení;
  - „Na tahu B: odpověz na #3 – napiš: odpověď #3: …“;
  - po rozhodnutí „Vyhrál nový směr (B) – platí od teď…“ a „uplatněno / neuplatněno: důvod“.
- **Falešný banner „Změna mimo toto okno“:** příčina byla, že `vaultOp` a zápis plánu se nehlásily přes `trackSaveWrite`. Opraveno v naší cestě.
  - Zbytkové riziko (proběhnutí během `refresh`) leží v `canvas/save-versions/logic/use-canvas-versions.ts`, ne v naší cestě. Návrh: porovnat vlastní revizi i po fetchi.
- **Ověření:**
  - subagenti: backend výběr 549 passed, exit 0; `npm test` 1 266, exit 0; build exit 0;
  - Codex nezávisle: 37 passed (duel, apply, vision, e2e), exit 0; `npm test` 1 266, exit 0; build exit 0;
  - moje plné ověření nad ustáleným kódem (stabilní bod):

    | Příkaz | Výsledek | Exit |
    |---|---|---|
    | `uv run pytest backend` | 2 214 passed, 4 skipped, 2 failed (jen známé testy graphify) | **1** |
    | skripty | 134 passed | **0** |
    | `npm test` | 1 266 passed | **0** |
    | `npm run build` | v pořádku | **0** |

    Codexův dřívější plný běh (11 failed) odstartoval uprostřed úprav a není finální.
- **Drobnost mimo dávku:** souhrn stromu `details_summary` (`brief_vault_details.py`) počítá všechny body představy, ne jen aktuální verzi. Kreslení trendu z toho nečte, bere ho z GET.

### K16-ACCEPT (Hermes 14:43): finální kritika + izolovaná akceptace v prohlížeči, bez implementace

**Převzetí 14:43:**
- HEAD `f44f326`.
- Žádný zapisovatel neběží: subagenti A skončili, Codex potvrdil, že dál nezapisuje, relace B do `duel/` nesahá.
- Novější lidský pokyn nepřišel. Otázka „restartovat a commitnout?“ je bez odpovědi, commit proto nebyl.

**Otisky vstupů (sha256, prvních 16 znaků):**

| Otisk | Soubor |
|---|---|
| `9c5773540d67ba25` | `brief_vault_duel.py` |
| `1951061ca3d7bd96` | `brief_vault_duel_apply.py` |
| `7a4428514ba9afda` | `brief_vault_duel_shape.py` |
| `fed63cbee6645cb9` | `brief_vault_duel_math.py` |
| `9676bf67bc36ccfe` | `test_brief_vault_duel_apply.py` |
| `5b37ba2a53d228e3` | `test_brief_vault_vision_revision.py` |
| `a147f8a9d45e0a1d` | `duel/logic/duel-view.ts` |
| `a897a6275415646a` | `duel/components/DuelTrail.tsx` |
| `5bbd6ed1b7ba8313` | `logic/vault-actions.ts` |
| `a7442228100d20d9` | `docs/schranka-duel.md` |

**Restart ukázkové instance 8745** (jen vlastní instance, 8740 ani `P:/opora-data` se nedotkly):
- Starý strom: PID 55588 → 54304 → 48232, vznik 13:01:09–10. Příkaz `opora --port 8745 --data …\scratchpad\demo-duel-data --no-open --no-build`, identita ověřena.
- Zastaven: port volný, všechny 3 PID neexistují.
- Nový: PID 41060, vznik 14:45:55, data `…\scratchpad\demo-duel-accept` (čistá dočasná složka). Odpověď na HTTP potvrzena.

**Pokus 1 – scénáře přes CLI/API** (`scratchpad/accept_apply.py`, výstup `scratchpad/accept_apply_out.json`, **exit 0**):

| Scénář | Výsledek |
|---|---|
| S1 adopt fragmentu | `applied` true, `appliedRevision` 3, předmět má nový text, `gateStep` 0, všechny brány false, `/next` vrací předmět s `gate: scoped`, `gatesStale: true` |
| S2 adopt projektu | `applied` true, představa = „V1: …“; replay `vision-set fromDuel` → **409** |
| S3 předmět změněn během duelu (cizí `revise` 200) | `applied` false „předmět se mezitím změnil“, předmět drží cizí text |
| S4 karta | `applied` false „kartu upraví člověk nebo agent podle decision.text“ |
| S5 keep | `applied` false „keep: …“, předmět zůstává na revizi 1 |
| S6 otevřený duel | připraven pro poll |

**Pokus 2 – prohlížeč** (Chrome DevTools, `http://127.0.0.1:8745/?…&layer=s1` → Schránka → Duel):
- Seznam: 1 otevřený a 5 rozhodnutých duelů s P. Snímek `scratchpad/accept-list.png`.
- **Nález Hermese reprodukovaný** v S3 (`scratchpad/snap3.txt`): „Vyhrál nový směr (B) – platí od teď: Platby kredity.“ a pod tím „neuplatněno: předmět se mezitím změnil“. UI si odporuje.
  - Snímek obrazovky S3 dvakrát vypršel (`Page.captureScreenshot timed out`). Doklad je textový snapshot stránky.
- **Obnova bez reloadu:** v otevřeném S6 zapsal agent přes CLI tah B (exit 0). Do 10 s se v okně objevil jako #1 (`wait_for` našel text).
  - Banner „Změna mimo toto okno“ se objevil správně, zápis přišel z jiného procesu.
- Krátká čísla #N, „Na tahu kdokoli – napiš: …“, „Lze rozhodnout – napiš: rozhodni“ a nápověda na jeden řádek se zobrazují.

**Nejmenší oprava `outcomeLine`** (`duel-view.ts:172–183`, neimplementováno). Tvrzení „platí od teď“ jen při `decision.applied === true`. Při `false`:

| Případ | Text |
|---|---|
| fragment nebo projekt | „Vyhrál nový směr (B), ale neuplatnil se – platí dál A: <reason>“ |
| karta | „Vyhrál nový směr (B) – kartu je potřeba upravit podle: <text>“ |
| legacy bez `applied` | „Vyhrál nový směr (B) – stav uplatnění neznámý“ |

Totéž pro syntézu. Upravit i `duel-view.test.ts:72`, který dnešní chování vyžaduje.

**P vs. atestace:** P(B > A) je heuristická, nekalibrovaná síla argumentů od soudců. Nedokládá, že vítězný směr je správný ani že něco prošlo. UI ho ukazuje jako „P(B > A) 35 %“ bez kvalifikace (`DuelOdds.tsx:16`, `DuelList.tsx:13`). Návrh: popisek „síla argumentů (nekalibrovaná)“ a tooltip „není ověření výsledku“. Atestace výsledku zůstává BLOCKED (K15 §5).

**Finální nezávislá kritika (Codex nad kontraktem, `apply.py`, `duel_open`/`duel_decide`, testy a `duel-view.ts`):**
- **Doložené, vysoké:**
  1. **Návrat ke starému textu oživí staré brány** (`brief_vault_duel_apply.py:39`, `brief_vault_gate_rules.py:223`). `w.revise` přenese `gates` a shodný hash je znovu zplatní, takže smyčka nezačne od `scoped`. Oprava: při uplatnění explicitně zneplatnit brány v nové revizi.
  2. **Smazaný předek** (`apply.py:33`): kontroluje se smazání předmětu, ne jeho předků, takže uplatnění na skrytý fragment ohlásí úspěch. Oprava: ověřit členství v `live_ids`, jinak `applied` false.
  3. **UI zaměňuje vítězství za uplatnění** (`duel-view.ts:173`, `:188`). Je to totéž co nález Hermese, oprava viz výše.
- **Doložené, střední:**
  - Shodný text vykáže `applied` true bez nové revize a bez restartu bran (`apply.py:37`).
  - P bez označení heuristiky (`DuelOdds.tsx:16`, `DuelList.tsx:13`).
- **Hypotézy:** pokrytí předkem s platným `placed` (`apply.py:30` vs `brief_vault_next.py:129`); chybí test rollbacku po selhání zápisu rozhodnutí a test skutečného souběhu `revise`/`decide`.
- **Nepotvrzeno:** TOCTOU kryje `BEGIN IMMEDIATE` (`brief_vault.py:349`) a CAS duelu, override jde společným uplatněním, replay se kontroluje (`:418`, `:421`).

**Zbylé nejistoty:**
- U otevřeného duelu bez jediného argumentu je `canDecide` true a výsledek by byl `keep` (P = p0 = 0.35 ≤ 0.40). Odpovídá to pravidlu „břemeno nese změna“, ale „Lze rozhodnout“ bez argumentů může mást.
- Snímky obrazovky v prohlížeči selhávají na časový limit. Doklady jsou textové snapshoty.
- Testy jsem v této dávce nespouštěl, poslední plné ověření je stabilní bod výše (`bat3szyut`).

### K16-FIX (Hermes 15:01, převzato 15:01)

- **Oprava počtu:** doslovný kritik K16-ACCEPT dal **3 vysoké** (návrat ke starému textu, smazaný předek, UI vítězství ≠ uplatnění) a **2 střední** (shodný text, popisek P). V chatu jsem omylem napsal „4 vysoké“, správně jsou 3.
- **Vlastnictví:** cesty volné, žádný konkurenční zapisovatel. Codex a relace B jen čtou.
  - Backend má jednoho zapisovatele (subagent K16-FIX backend): `brief_vault_duel_apply.py`, `brief_vault_duel.py`, minimálně `brief_vault_gate_rules.py` (sdílené pravidlo zneplatnění bran, cesta A) a sousední testy, `docs/schranka-duel.md`.
  - Frontend má jednoho zapisovatele (subagent K16-FIX frontend): jen `frontend/editor/brief-vault-dock/duel/**`.

#### K16-FIX výsledek (NEcommitnuto, nestageováno)

Zapisovatelé:
- **Backend** (jeden subagent) změnil `brief_vault_duel_apply.py` a `test_brief_vault_duel_apply.py` (+5 testů), v `docs/schranka-duel.md` §3.2 přidal 3 odrážky a v `test_opora_duel.py` nahradil jedno tvrzení.
  - `brief_vault_duel.py` (9c5773540d67ba25) a `brief_vault_gate_rules.py` (4b0f627557c19dc3) beze změny.
- **Frontend** (jeden subagent) měnil jen `duel/**` (`duel-view.ts` + test, `DuelTrail`, `DuelOdds`, `DuelList`, `DuelSection` + test, css, README).
- Oba subagenty přerušil limit použití (HTTP 429) po zaznamenaném RED. Po obnovení pokračovali, soubory se mezitím neměnily.

RED → GREEN:

| Část | RED | GREEN |
|---|---|---|
| backend `test_brief_vault_duel_apply.py` | 5 failed / 10 passed, exit 1 (V0→V1→V0: `gateStep 2 == 0`) | 15 passed, exit 0; výběr `brief_vault` + `api/editor` + skripty 554 passed, exit 0 |
| frontend `duel/` | 5 failed / 21 passed, exit 1 | 26 passed; `npm test` 1 268, exit 0; build exit 0 |

**Tvrzení e2e (`test_opora_duel.py:184`):** padalo, protože opravené vynulování bran dává `gatesStale` false. Je to záměr, ne regrese.
- Staré: `assert node['gatesStale'] is True`.
- Nové: `gateStep == 0 and gatesStale is False`, žádná zapnutá brána, detail fragmentu bez platné brány a `/next` → `scoped`, pokud je předmět hlavou fronty.
- Bezpodmínečnou kontrolu `/next` dokládá samostatný test `test_return_to_older_text_does_not_revive_its_gates`: V0 `gateStep` 2 → V1 0 → adopt V0 → 0, `/next` vrací `scoped`.

Nové `decision.reason` doslova:
- „předmět nebo jeho předek je smazaný“
- „předmět už má tento text (beze změny)“
- „předmět neexistuje“

**Prohlížeč (izolovaná 8745 restartovaná na nový kód):**
- Starý strom PID 55520 (uv), 54664, 54360, 41060, vznik 14:45:55, data `demo-duel-accept`, identita ověřena a strom zastaven. Nový PID 14800, vznik 15:43:00, stejná dočasná data.
- Seznam: „síla B 87 %“ místo P.
- S3 (předmět změněn): „Vyhrál nový směr (B), ale neuplatnil se: předmět se mezitím změnil“ + „Rozhodnuto: vyhrál B při síle B 87 %“. Ukazatel: „Síla argumentů pro B (nekalibrovaná)“ (`scratchpad/fix-snap-s3.txt`).
- S4 (karta): „Vyhrál nový směr (B) – karta se automaticky nemění; uprav ji podle: …“ (`scratchpad/fix-snap-s4.txt`).
- **Zbytek:** ukazatel síly u rozhodnutého duelu dál píše „směřuje k: **platí B**“ (`OUTCOME_LABEL`, `duel-view.ts`). U neuplatněného výsledku to odporuje hlavní větě.

**Nezávislý kritik (Codex) nad diffem, kontraktem a testy:**
- Opraveno: 1 (neoživení bran), 3 (UI), 4 (no-op shodného textu), 5 (přejmenování; matematiku proti základu neověřil, soubory jsou v gitu nesledované).
- Bod 2: předmět je chráněn, ale rozhodnutí a poučení se zapíšou. Kontrakt má říkat „bez zápisu do **předmětu**“.
- Oracle e2e je přesnější, podmíněné `/next` samo zařazení předmětu do fronty nedokazuje. Kryje to samostatný test.

**BLOCKED – nutná další implementace, nové kolo nezakládám (pokyn Hermese 15:34):**
1. **Uplatnění po vyčerpaných kolech** (nová doložená vada, kritik zreprodukoval přes `round_of`): `_gates_off` (`brief_vault_duel_apply.py:45`) zapíše i `synthesized: false`. `round_of` (`brief_vault_gate_rules.py:260–267`) to po neúspěšném `verified` počítá jako nové kolo, takže po 3. neúspěšném kole a adopt je round 4 a `/next` předmět vyřadí jako vyčerpaný (`brief_vault_next.py:134`). Adopt přitom hlásí uplatnění.
   - Nejmenší návrh: značky vypnutí z duelu označit (`"by": "duel"` nebo `"cause": "duel-apply"`) a `round_of` je nepočítá. Alternativa je politika „nový směr = nové počítání kol“, o té ale musí rozhodnout člověk. Regresní test: 3 neúspěšná kola + adopt → `exhausted` false, `/next` vrací `scoped`.
2. **Ukazatel „platí B“ u rozhodnutého duelu:** u rozhodnutého duelu místo „směřuje k: platí B“ zobrazit „rozhodnuto: vyhrál B“ (nebo text skrýt). Jeden řádek v `duel-view.ts` + test.
3. **Kontrakt §3.2:** „bez zápisu do předmětu“ místo „bez zápisu“ (dokumentace).
4. **Test e2e:** bezpodmínečně ověřit zařazení předmětu do fronty, např. `next` s filtrem nebo jediným kandidátem.

Plné ověření nad konečným kódem K16-FIX:

| Příkaz | Výsledek | Exit |
|---|---|---|
| `uv run pytest backend` | 2 219 passed, 4 skipped, 2 failed (jen známé testy graphify, `assert 'failed' == 'succeeded'`) | **1** |
| skripty | 134 passed | **0** |
| `npm test` | 1 268 passed | **0** |
| `npm run build` | v pořádku | **0** |

### K16-TRUTH (Hermes 16:04, převzato 16:05, NEcommitnuto)

- **Převzetí:**
  - Novější lidské zadání nepřišlo (poslední ze 14:10). Žádný zapisovatel neběží (poslední zápis do `duel/` v 15:31 od dokončeného agenta K16-FIX). Kolize žádná.
  - Snapshot povolených souborů před dávkou: `scratchpad/truth-pre/`.

  | Otisk | Soubor |
  |---|---|
  | `11a81b049a39950c` | `DuelOdds.tsx` |
  | `3e9cabb6c5c4c26a` | `duel-view.ts` |
  | `e52326c1d85e22d9` | `duel-view.test.ts` |
  | `8877912c61a4ec1a` | `DuelSection.test.ts` |
  | `bd2a6cda7b34f40f` | `test_opora_duel.py` |
  | `f516c1054fada9e9` | `docs/schranka-duel.md` |

- **Jediný zapisovatel:** subagent K16-TRUTH (body 1–3 zadání).
- **Čtecí reprodukce limitu kol** (`scratchpad/probe_rounds.py`, dočasná fixture `vault_client`, 1 pokus, **exit 0**, backend beze změny):

  | Případ | Před duelem | Rozhodnutí | Po duelu |
  |---|---|---|---|
  | A: adopt po 2. neúspěšném kole | round 2, exhausted false, gateStep 7, `/next` = předmět / `learned` | adopt, applied true, rev 15 | round **3**, exhausted false, gateStep 0, `/next` = předmět / `scoped` |
  | B: adopt po 3. neúspěšném kole | round 3, **exhausted false**, gateStep 7, `/next` = předmět / `learned` | adopt, applied true, rev 21 | round **4**, **exhausted true**, předmět mimo `/next`, `blockedBy.exhausted` 1 |

  - **Stav „po 3. neúspěchu“ ještě není vyčerpaný.** Vyčerpaný je až po zahájení 4. kola (`round > MAX_ROUNDS`). Duel tedy v B fragment sám přepne do vyčerpání. Pojistka `MAX_ROUNDS` drží: adopt nedá 4. pokus.
  - **Nepravda je v hlášení:** `applied: true` a UI „agenti pokračují tímto směrem“, přitom fragment čeká na člověka.
  - **Druhý dopad (nový):** v A i B čekala na fragment brána `learned` neúspěšného kola (antipattern). Uplatnění vypne všechny brány, takže **poučení neúspěšného kola se nezapíše**. Ztrácí se paměť „co nefungovalo“.
- **Nejmenší návrh, který zachová pojistku i při opakovaných duelech (neschváleno, neimplementováno):**
  1. Počítání kol neměnit (žádný reset, `cause`/`by` výjimka ne). Duel nový směr započte jako kolo, takže opakované duely limit nikdy neobejdou.
  2. Pravdivý výsledek: když uplatnění vede k `exhausted`, `decision` nese `applied: true` + `exhausted: true` a důvod „uplatněno, ale fragment vyčerpal kola – čeká na člověka“. UI pak neříká „agenti pokračují“.
  3. Paměť neúspěchu: `duel-decide` s uplatněním počká, dokud fragment po neúspěšném `verified` nemá zapsané `learned`. Jinak `applied: false`, důvod „nejdřív zapiš poučení neúspěšného kola“, rozhodnutí se uloží a uplatní se později ručně nebo dalším rozhodnutím. Varianta: uplatnění zapíše poučení samo z výsledku kola. O tom musí rozhodnout člověk.
  4. Regresní testy: případ A a B výše + dva duely po sobě nepřekročí `MAX_ROUNDS`.

#### K16-TRUTH výsledek (NEcommitnuto, nestageováno; K16 jako celek zatím neakceptováno)

**Zapisovatel:** jediný subagent, 1 korekční kolo. Backend beze změny.

| Snapshot před → po | Soubor |
|---|---|
| `11a81b049a39950c` → `dd1d2c7ffa2e4a43` | `DuelOdds.tsx` |
| `3e9cabb6c5c4c26a` → `3239849c304996e7` | `duel-view.ts` |
| `e52326c1d85e22d9` → `ec0c0b072e49f006` | `duel-view.test.ts` |
| `8877912c61a4ec1a` → `0b83345ce3d627fd` | `DuelSection.test.ts` |
| `bd2a6cda7b34f40f` → `aa27e89292f2786b` → po korekci **`c5c1448c0665d69c`** | `test_opora_duel.py` |
| `f516c1054fada9e9` → `bde029403ff58fad` | `docs/schranka-duel.md` |

Diff před/po: `scratchpad/truth-diff.txt`, bez korekce testu.

**1. Ukazatel u rozhodnutého duelu.** Nová čistá funkce `oddsVerdict(duel, zone)` bere výsledek jen z `decision`, pásmo P nečte.

| Stav | Text |
|---|---|
| adopt, uplatněno | „rozhodnuto: vyhrál B, uplatněno“ |
| adopt, neuplatněno | „rozhodnuto: vyhrál B, neuplatněno“ |
| adopt, stav neznámý | „rozhodnuto: vyhrál B, stav uplatnění neznámý“ |
| adopt, karta | „rozhodnuto: vyhrál B, karta se automaticky nemění“ |
| syntéza | obdobně |
| keep | „rozhodnuto: zůstává A“ |
| přebití člověkem | připojí „ (přebito člověkem)“ |

- Otevřený duel dál „směřuje k: …“. Vzhled, matematika a prahy beze změny.
- Testy: případy, kdy pásmo P říká opak (keep override při p 0,9).
- **Prohlížeč (izolovaná 8745, PID 14800):** S3 ukazuje „…neuplatnil se: předmět se mezitím změnil“ a v ukazateli „n 3 hodnocených · rozhodnuto: vyhrál B, neuplatněno“. „platí B“ zmizelo (`scratchpad/truth-snap-s3.txt`).

**2. E2E:** `if head.id == f1` nahrazeno bezpodmínečným `head.id == f1 and gate == 'scoped'`.
- **RED:** s bezpodmínečnou kontrolou byla hlavou jiný fragment, stará kontrola tedy nic nedokazovala.
- **Izolace bez změny runtime:** f2/f3 se zakládají až po kontrole.
- **Korekce 1 (kritik):** obnovena konkurence pro prioritu prvního duelu. Fragment `rival` (be, čeká na `scoped`) existuje při kontrole `needs: duel` (+ `assert id != rival`) a před izolovaným důkazem ho člověk smaže přes `op: delete` (+ `assert removed 200`).
- **Aserce 54 → 56**, žádná nezmizela, žádný skip ani xfail.

**3. Kontrakt §3.2:**
- „bez zápisu do předmětu; rozhodnutí a poučení se zapíšou“;
- „Známý rozpor (otevřeno, bez nového pravidla)…“: synthesized značka, `round_of`, `MAX_ROUNDS` se neobchází.

**RED → GREEN:**
- vitest `duel/`: 2 failed / 26 passed, exit 1 → 28 passed, exit 0;
- `test_opora_duel.py`: 1 failed, exit 1 → 1 passed, exit 0.

**Nezávislý kritik** (Codex nad přesným diffem snapshotů): body 1–3 splněny. Nová vada (oslabená konkurence u ř. 126) opravena v korekci 1.

**Plné ověření:**

| Příkaz | Výsledek | Exit |
|---|---|---|
| `uv run pytest backend` | 2 219 passed, 4 skipped, 2 failed (jen známé testy graphify) | **1** |
| skripty (před korekcí) | 134 passed | 0 |
| **skripty po korekci** (můj běh) | 134 passed | **0** |
| `npm test` | 1 270 passed | **0** |
| `npm run build` | v pořádku | **0** |

Korekce změnila jen test skriptu, backend ani frontend běh neovlivní.

**Otevřené (BLOCKED, rozhodnutí člověka nebo Hermese):**
1. Adopt po 3. neúspěšném kole označí fragment jako vyčerpaný při `applied: true`.
2. Uplatnění zahodí čekající `learned` neúspěšného kola.

Reprodukce a návrh výše (K16-TRUTH, `probe_rounds.py`).

### K16-PROOF (Hermes 16:32, převzato 16:32): jen čtení, žádný zapisovatel, kód beze změny

- **Převzetí:** novější lidské zadání nepřišlo, žádný zapisovatel neběží, kolize ani otázka nejsou.
- **Sonda 2** (`scratchpad/probe_rounds2.py`, dočasné fixture `vault_client`):
  - pokus 1 selhal na chybě sondy (`StopIteration` – došly ukázkové texty), ne na aplikaci;
  - **pokus 2 exit 0**, výstup `scratchpad/probe_rounds2_out.json`.
  - Sloupce v tabulce: r = kolo, ex = exhausted, step = gateStep, rev = počet revizí, failRev = revize nesoucí neúspěšné `verified`.

| Případ | Před duelem | Rozhodnutí | Po duelu |
|---|---|---|---|
| **C** exhausted už před duelem (3 neúspěchy + zahájené 4. kolo) | r4, ex true, step 2, rev 21, failRev 3, mimo `/next` | duel jde otevřít; adopt, `applied` true, rev 22 | r4, ex true, step 0, rev 22, mimo `/next` |
| **D** dva duely po 2. neúspěchu | r2, ex false, step 7, `/next` = `learned` | duel 1: adopt, applied, rev 15 | r3, ex false, `/next` = `scoped` |
| | | duel 2: adopt, applied, rev 16 | **r3** (bez změny), ex false, `/next` = `scoped` |
| **D2** dva duely po 3. neúspěchu | r3, ex false, step 7 | duel 1: adopt, applied | r4, **ex true**, mimo `/next` |
| | | duel 2: adopt, applied | r4, ex true, mimo `/next` |
| **E** `learned` zapsané před duelem | r2, step 8, poučení: antipattern (předmět) | adopt, applied | r3, `/next` = `scoped`; poučení: **antipattern zůstává** + pattern duelu |
| **F** `learned` chybí | r2, step 7, `/next` = `learned`, poučení: žádné | adopt, applied | r3, `/next` = `scoped`; poučení: jen pattern duelu |

**Fakta:**

1. **`MAX_ROUNDS` drží ve všech případech.**
   - Opakované duely bez nového neúspěšného `verified` kolo nezvyšují (D: r3 → r3).
   - Vyčerpání nikdy nezmizí (C, D2 zůstávají r4 a exhausted).
   - Duel nedá 4. pokus.
2. **Duel smí měnit text vyčerpaného fragmentu** (C, D2: `applied` true na fragmentu, který čeká na člověka). Text zadání se změní, agenti ale nepokračují, protože fragment je mimo `/next`. Hlášení „agenti pokračují tímto směrem“ je tu nepravdivé. Text o změně zadání pravdivý je.
3. **„Ztráta poučení“ přesně:**
   - Historie neúspěchu **nezmizí**: revize jsou append-only a záznamy neúspěšného `verified` zůstávají (F: failRev 2 před i po).
   - Zapsané poučení **nezmizí** (E: antipattern předmětu zůstává).
   - Zmizí jen **čekající brána `learned` z fronty** (F: `/next` před = `learned`, po = `scoped`). Poučení z neúspěšné realizace tak vůbec nevznikne.
   - Poučení duelu (pattern „změna … obstála“, náleží fragmentu duelu, ne předmětu) **není** poučením z neúspěšné realizace. Říká, proč obstál nový směr, ne co v kódu selhalo.
   - Zdroje: `stored()` = `brief_fragment_revisions.gates` (historie), `GET /api/brief-vault/lessons` (paměť), `GET /api/brief-vault/next` (fronta).

**Nejmenší návrh (neimplementováno, beze změny kontraktu a runtime):**

1. **Pravdivý text bez nových polí.** UI oddělí „zadání změněno“ (z `decision.applied`) od pokračování agentů (ze stávajícího `exhausted` předmětu ve stromu nebo detailu):
   - `applied` true a předmět nevyčerpaný → „zadání změněno; agenti pokračují od scoped“;
   - `applied` true a `exhausted` → „zadání změněno; fragment vyčerpal kola – čeká na člověka“.
   - Bez nového pole v `decision`, bez resetu a bez výjimky z rozpočtu.
2. **Fail-closed guard pro chybějící `learned`** (volitelný, k rozhodnutí): `duel-decide` vrátí **409 bez zápisu rozhodnutí**, když poslední `verified` předmětu je neúspěšný a `learned` toho kola není zapnuté („nejdřív zapiš poučení neúspěšného kola“).
   - **Zotavení / retry:** duel zůstává otevřený, takže po zapsání `learned` stačí `duel-decide` znovu. Nevznikne konečné „decided + applied false“, které by pokračování skrytě zablokovalo.
   - **Replay:** `decide` jde stejně jen jednou (rozhodnutý duel = 409), takže guard nic neotevírá. Žádné automatické poučení, žádné nové pole.
   - Alternativa bez guardu: jen text v UI „pozor: poučení neúspěšného kola nebylo zapsáno“ (ze stávající historie).
3. **Regresní testy pro budoucí implementaci:** případy C, D, D2, E, F jako tvrzení. Hlavně: opakované duely nezvýší kolo a nezruší vyčerpání.

**Finální nezávislé čtení korekce e2e** (Codex nad `git diff --no-index` snapshot → finál, `test_opora_duel.py` `bd2a6cda7b34f40f` → `c5c1448c0665d69c`):
- (a) bezpodmínečná kontrola f1 + `scoped`: **splněno**, ř. 196;
- (c) žádná aserce nezmizela ani nebyla oslabena, žádný skip ani xfail, runtime beze změny: **splněno**;
- (b) a (d): **nelze ověřit z diffu.** Test neověřuje, že konkurent je skutečně způsobilý do stejné fronty (bez duelu by byl hlavou). Smazání následuje až po kontrole priority, takže ji neovlivní.
- **Doložená mezera (bez opravy, dávka je jen ke čtení):** doplnit aserci způsobilosti konkurenta, např. `next` před otevřením duelu vrací `rival`, nebo jeho detail má `gateStep` 0 bez blokace.

Plný backend se v této dávce znovu nespouštěl. Poslední platný běh je `bxoc2c7p9`: 2 219 passed / 4 skipped / 2 graphify failed, exit 1.

### K16-FINAL (Hermes 17:23, převzato 17:23:15; NEcommitnuto, K16 jako celek neakceptováno)

- **Provozní kontrakt:**
  - relace A, HEAD `f44f326`;
  - novější lidský pokyn ani otevřená otázka nejsou;
  - aktivní zapisovatel ani kolize nejsou (poslední zápis v rozsahu 16:09 od dokončeného agenta).
  - Scratchpad relace už není dostupný, snapshoty jsou v `%TEMP%\opora-a-final\pre`.
- **Jediný zapisovatel:** subagent K16-FINAL, korekce žádná.

| Otisk před → po | Soubor |
|---|---|
| `3239849c304996e7` → `8e349570667114fa` | `duel-view.ts` |
| `ec0c0b072e49f006` → `17a6a9d19d3e97cd` | `duel-view.test.ts` |
| `0b83345ce3d627fd` → `c23b97fcdaa48439` | `DuelSection.test.ts` |
| `c5c1448c0665d69c` → `9923b94186827977` | `test_opora_duel.py` |

Diff: `%TEMP%\opora-a-final\diff.txt`.

1. **`appliedLine`** (`duel-view.ts:193`): „uplatněno: zadání má nový text, agenti pokračují tímto směrem“ → **„uplatněno: zadání má nový text“**.
   - Nic se neodvozuje z `exhausted`, žádné nové pole ani politika. Grep „agent/pokrač“ v `duel-view.ts` už jiný příslib nenajde.
   - Testy: negativní aserce „neobsahuje pokračují/agenti“.
   - **RED** 2 failed / 26, exit 1 → **GREEN** 28/28, exit 0.
2. **E2E způsobilost konkurenta:** před `open_duel` vrací `next --discipline be` (stejná fronta i aktér jako pozdější kontrola priority) bezpodmínečně `rival` s `gate: scoped` a bez blokace duelem (`test_opora_duel.py:126–128`).
   - `f1 + scoped` zůstává bezpodmínečné (ř. 200). Aserce 56 → 58, žádná neodstraněna, žádný skip, xfail ani změna runtime.
   - RED tu není, nová aserce jen dokládá existující chování a prošla napoprvé.
- **Nezávislý kritik** (Codex, celý `test_opora_duel.py` včetně pomocných funkcí, celý `duel-view.ts` a diff s otisky): cíl 1 splněn, cíl 2 splněn staticky, **doložené vady žádné**. Běh testů z kódu sám neověřoval, doklad běhu je níže.
- **Ověření (moje běhy, skutečné exit kódy):**

  | Příkaz | Výsledek | Exit |
  |---|---|---|
  | `npx vitest run …/duel` | 28 passed (4 soubory) | **0** |
  | `uv run pytest backend/brain/seed/opora-control-center/skills/opora-control-center/scripts` | 134 passed | **0** |
  | `npm test` | 184 souborů / 1 270 testů | **0** |
  | `npm run build` | v pořádku | **0** |
  | `uv run pytest backend` | 2 219 passed, 4 skipped, 2 failed (jen známé testy graphify: `test_generate_uses_official_graphify_and_persists_output`, `test_real_graphify_refresh_publishes_only_selected_project`, `assert 'failed' == 'succeeded'`), dokončeno 17:34 | **1** |

- **Neověřeno nebo zbývá:**
  - `frontend/editor/brief-vault-dock/duel/README.md:27` dál uvádí starý příslib „…, agenti pokračují tímto směrem“. Je mimo povolený rozsah dávky, sladit ho musí další dávka.
  - Prohlížeč v této dávce neběžel, změna je jen textová a pokrývají ji testy. Izolovaná 8745 (PID 14800) stále běží s dočasnými daty.
  - Návrh pojistky pro `learned` zůstává neschválený. Rozpor s limitem kol je otevřený (K16-TRUTH/PROOF).

## Originály a sektory (pro koordinaci, žádný redesign)

Zdroje 00–09 nepředepisují sektory ani kontejnery podle disciplín:
- 00:5–7 oddělují uzel a kontrakt;
- 04:83–91 popisují mikrokrok s ověřením;
- 06:15–24 roli a acceptance;
- 07:103–116 artefakt, eval a paměť.

Rozpor `docs/schranka-neurony.md:89–91` (sektor podle disciplíny) vs. `docs/pyramida.md:26–27` (sektor = dodavatelný celek)
je tedy lokální mapování OPORA, ne autorita originálu k migraci. K15 ho neřeší. Případný additive návrh přijde až po ověřeném řezu.

## Koordinace s relací B

- Rozpor k rozhodnutí: **sektor = disciplína** (Schránka: 17 disciplín jako neurony, `brief_vault_disciplines.py`)
  vs. **sektor = dodavatelný celek** (pyramida oblast → sektor → karta, `docs/pyramida.md`). Relace A pyramidu nepřepisuje;
  buňka řezu nese disciplínu jako atribut, ne jako sektor.

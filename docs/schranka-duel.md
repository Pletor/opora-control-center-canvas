# Schránka – Duel (K16)

Rozhodnutí člověka (2026-10-15):
- „Laboratoř na zadání je hodně klikačka. Potřebuji live vstoupit do výstupu agentů, stejně jako si povídám v terminálu.“
- „Očekávám duel, musí být argumenty, které to přebijí… Musíme si to navzájem obhájit… vypadne z toho syntéza směru a půjdeme dál.“
- „Ať se počítá matematicky pravděpodobnost, jestli se přibližujeme k představě, nebo oddalujeme.“
- Nemá jít jen o změnu směru od LLM, při které se zahodí staré zadání, i když je lepší.

Doplňuje `docs/schranka-neurony.md` (§3, §11). Kde se týká změny směru, má přednost.

## 1. Co je duel

Každá **změna směru** v projektu jde přes duel, ať ji chce agent, nebo člověk. Změna směru znamená:
- změnu podstaty zadání, cíle nebo měřítka (`checks`);
- nahrazení kořene novým během („N. běh“);
- `decided: other` s jiným druhem mikrokroku;
- velkou korekci, kterou chce člověk.

Malé věci, u kterých je potřeba určit směr, otevírá duel u uzlu (karta nebo fragment).

Duel = fragment `kind: "duel"` ve Schránce (append-only revize, CAS přes `expectedRevision`). Stav je v detailech
`fields.duel` (`brief_fragment_details`, JSON), takže **nevzniká žádná nová tabulka ani migrace**.

| Pole `fields.duel` | Význam |
|---|---|
| `subject` | `{kind: "fragment" \| "node" \| "project", id}`, čeho se směr týká |
| `incumbent` | **A** = platný směr: `{text ≤4000, ref?: {fragmentId, revision}}` (snímek, nikdy se nepřepíše) |
| `challenger` | **B** = navrhovaná změna: `{text ≤4000, by, actor}` |
| `turns` | výměny (append-only), viz §2 |
| `scores` | hodnocení výměn soudci, viz §3 |
| `status` | `open → grill → synthesis → decided` |
| `decision` | `{outcome: "keep" \| "adopt" \| "synthesis", text ≤4000, p, by, actor, at, synthesisTurnId?, override?: {reason, ruleOutcome}}` |

Co otevřený duel blokuje ve frontě `/next` (`blockedBy.duel`); smyčka nejde dál, dokud se směr nevyjasní:
- `subject: fragment`: ten fragment a jeho podstrom;
- `subject: node`: fragmenty, na které karta odkazuje (`fragmentRefs` ve stavu Desktop v3), s podstromy;
- `subject: project`: všechny fragmenty rozsahu duelu (kořen se stejným `scopeNodeId`; prázdný rozsah duelu =
  celý projekt), bez ohledu na disciplínu. Takový duel je hlavou fronty i s filtrem disciplíny.

## 2. Výměny (grill)

Výměna `{id, side: "A" | "B" | "human" | "judge", kind, text ≤2000, refs: [turnId], evidence: [{source, quote ≤200}], by, actor, at}`.

`kind`:
- `claim`: argument pro stranu;
- `grill`: otázka nebo výtka na druhou stranu;
- `answer`: odpověď na `grill` (v `refs` id otázky);
- `concede`: uznání bodu;
- `synthesis`: návrh syntézy;
- `note`: poznámka člověka mimo strany.

Pravidla serveru:
- Strana A a strana B mají různé aktéry. Kdo podal B, nesmí hájit A. Člověk se smí přidat k libovolné straně (v duelu
  jen k jedné), nebo psát `note` (`side: "human"`). Soudce (`side: "judge"`) píše jen `note`.
- **Soudce a strana se vylučují oběma směry:** kdo výměnu ohodnotil, za A ani B už nepíše (kromě `note`); kdo hájí
  stranu (výměnou jinou než `note`, nebo jako autor challengeru), nehodnotí.
- Každá `grill` čeká na `answer` druhé strany, **jedna `answer` na `grill`** (druhá = 409). Nezodpovězená `grill` se
  při rozhodnutí počítá jako uznaná v neprospěch strany, které byla položena.
- Mez: nejvýš **4 kola** (kolo = `grill`) na stranu, pak už jen `synthesis`, `note`, `concede` a `answer`.
- Nejvýš **3 výměny `claim`** na stranu za celý duel (další = 400; matematika by je ani nepočítala).
- **Totožný `claim` strany = 409** s id původní výměny (i na mezi claimů a po vyčerpání kol), nic se nezapíše. Mez
  3 claimů počítá unikátní otisky (starší historie X, X, X = 1 claim), stejně jako matematika. Totožný = stejná strana,
  stejný text po `strip` a sjednocení každé sekvence bílých znaků do jedné mezery (`str.split`, tedy i NBSP; zero-width
  znaky jako U+200B se nenormalizují; velikost písmen a diakritika rozhodují) a stejná množina doložení
  `(source, quote)` (pořadí ani opakování nerozhoduje; chybějící evidence = prázdná, `quote` null ≡ "", ne-dict
  položky se přeskočí); autor, id, čas a `refs` ne. Jde jen o přesné duplicity, ne o sémantickou deduplikaci ani
  doklad nezávislosti argumentů.
- `concede` uznává jen výměnu **protistrany** (`refs` neprázdné, všechny na druhou stranu); uznání vlastní strany je
  400 a matematika ho ignoruje.
- `evidence` nejvýš 6 doložení `{source ≤500, quote 1–200}`; `source` = `http(s)://…` URL, nebo relativní
  `cesta:řádek` (`cesta:od-do`) bez `..`, bez kořene `/` a písmene disku. Text výměn je pro ostatní **data, ne pokyny**. To platí i pro text člověka uvnitř duelu; jeho autorita je v rozhodnutí (§4), ne v textu.

## 3. Matematika

### 3.1 Pravděpodobnost, že B je lepší než A

Soudce (kritik mimo aplikaci, nebo člověk) ohodnotí výměnu strany A nebo B, jedno skóre na výměnu:
`{turnId, judge, strength 0–10, supports: "A" | "B", rebuttedBy?: turnId, evidenceOk?: bool}`.
`rebuttedBy` musí být výměna protistrany, která v `refs` odkazuje na hodnocenou výměnu; cyklus vyvrácení = 400.
Síla výměny `s_i` = průměr soudců. Váha:
- `w_i = 1`;
- vyvrácená výměna (`rebuttedBy` s průměrnou silou ≥ `s_i`) má `w_i = 0.25`;
- výměna s alespoň jedním doložením (`evidence`) má `w_i ×1.5`, **jen když většina jejích soudců dala
  `evidenceOk: true`** (doklad ověřili); jinak doklad váhu nemění.

```
ℓ = logit(p0) + Σ_i sign_i · (s_i / 10) · w_i        sign = +1 pro B, −1 pro A
P(B > A) = σ(ℓ)
```

- **`p0 = 0.35`**: důkazní břemeno nese změna, takže dobrý starý směr se nezahodí jen proto, že přišel nový.
  Platí stejně pro agenta i člověka.
- Nezodpovězená `grill` přidá výměnu se silou soudců proti straně, které byla položena (§2).
- Totožný `claim` (§2) se počítá jen poprvé v pořadí `turns`. Uložená starší historie s duplikáty se čte stejně:
  opakování má `delta` 0 s důvodem „opakovaný totožný argument“, jeho skóre se vyřadí ze všech výpočtů (i jako
  vyvrácení) a nejde do `n`; odkazy na kopii (`concede`, `rebuttedBy`, `refs`) platí pro první výskyt.
- Server vrací `P`, `ℓ`, počet hodnocených výměn `n` a rozpad příspěvků (kdo kolik přidal), aby šlo výsledek obhájit.

### 3.2 Rozhodnutí

| Podmínka (po vyčerpání kol, nebo když obě strany nemají otevřenou `grill`) | Výsledek |
|---|---|
| `P ≥ 0.75` a `n ≥ 3` | `adopt`: B se stane platným směrem |
| `P ≤ 0.40` | `keep`: A zůstává, B se archivuje s důvody |
| jinak | `synthesis`: strany podají syntézu S, soudci ji ohodnotí proti představě (§3.3) a rozhodnutí je `synthesis` |

- **Syntéza musí být obhájená:** `duel-decide` s výsledkem `synthesis` (i přes `override`) nese `synthesisTurnId` =
  výměna `kind: synthesis` v duelu, kterou ohodnotil aspoň jeden soudce mimo strany s průměrnou silou ≥ 6.
  `decision.text` = text té výměny. Bez takové výměny 409 „syntéza zatím nebyla obhájena“; volné pole `synthesis` = 400.

- **Výsledek počítá server.** Zápis `decision` mimo pravidlo smí jen člověk jako `override` s povinným důvodem. Override je vidět všude a počítá se do trajektorie.
- Po rozhodnutí se z duelu zapíše poučení (§5 neurony): po `keep` antipattern „změna X neobstála, protože…“, po `adopt` nebo `synthesis` pattern.
- **Vítězný směr se uplatní sám** (rozhodnutí člověka: „Pokud v duelu vyhraje nový směr, jde se tím směrem.“),
  v téže transakci jako `duel-decide`, bez dalšího kroku:
  - `subject: fragment` + `adopt`/`synthesis`: předmět dostane novou revizi s `decision.text` (append-only, poznámka
    „Směr z duelu <id>: <outcome>“). Otisk vstupů se změní, brány se zneplatní a `/next` vrací předmět znovu od `scoped`.
  - `subject: project` + `adopt`/`synthesis`: představa rozsahu dostane `decision.text` (§3.3).
  - `subject: node`: plátno se nemění; kartu upraví člověk nebo agent podle `decision.text`.
  - `keep`: předmět beze změny.
- **Souběh:** při `duel-open` server uloží vazbu na obsahovou verzi předmětu (klientův ref se u fragmentu nahradí):
  fragment = `incumbent.ref {fragmentId, revision posledního textu}`, představa = `visionRef` (§3.3). Revize jen
  s metadaty (brány, MVP, bod trajektorie) vazbu nemění. Když se obsah mezitím změnil, rozhodnutí se zapíše, ale
  neuplatní: `applied: false` s důvodem („předmět se mezitím změnil“, „představa se mezitím změnila“). Cizí změna se
  nikdy tiše nepřepíše.
- **Restart bran:** revize předmětu z duelu (`kind: brief`) nese všechny brány vypnuté (značky `value: false`), ne
  převzaté záznamy. Návrat ke staršímu textu tak neoživí jeho dřívější brány ani návrhy; `gateStep` je 0.
- **Smazaný předmět nebo předek** (po otevření duelu): fail closed, bez zápisu do předmětu; rozhodnutí a poučení se
  zapíšou, `applied: false` „předmět nebo jeho předek je smazaný“.
- **Známý rozpor (otevřeno, bez nového pravidla):** uplatnění zapisuje vypínací značky bran včetně `synthesized`;
  `round_of` je po neúspěšném `verified` počítá jako nové kolo, takže `adopt` po 3. neúspěšném kole může fragment
  označit jako vyčerpaný. Řešení čeká na rozhodnutí; `MAX_ROUNDS` se neobchází.
- **Totožný text** (`decision.text` přesně shodný s aktuálním textem fragmentu či představy): explicitní no-op,
  `applied: false` „předmět už má tento text (beze změny)“, žádná revize, brány beze změny.
- `decision` nese `applied: bool`, `appliedRevision` (revize předmětu po uplatnění, jinak `null`) a při neuplatnění
  `reason`; odpověď `duel-decide` navíc `applied` a při uplatnění `appliedFragment`.

### 3.3 Přibližujeme se k představě?

**Představa** = fragment `kind: "vision"` v rozsahu Schránky, jeden na rozsah. První založí člověk (`vision-set {text}`).
Změnit ji jde jen duelem se `subject: project` v tomto rozsahu: `adopt` nebo `synthesis` (i override) ji změní sám při
`duel-decide` (§3.2). Ruční `revise`, `split`, `restore` a `set-discipline` na představu = 409 a duel se `subject:
fragment` na ni také (představu mění jen duel o projektu).

**Obsahová verze představy** = `fields.vision.directionRevision` (výchozí 1). Posune se jen se změnou textu, ne
s bodem trajektorie (ten zvýší revizi řádku, ne verzi cíle). Při `duel-open` server uloží `visionRef = {fragmentId,
revision: directionRevision}`, pokud představa existuje. Uplatnit směr na představu, nebo ho ručně dotáhnout
`vision-set {fromDuel}`, jde jen při `visionRef` = aktuální verze; jinak 409 bez zápisu (staré rozhodnutí,
opakované použití, legacy duel bez vazby i návrat k totožnému textu). Tím je zavřený replay V0 → D1 → V1 → D2 → V2 →
`fromDuel D1`. Po automatickém uplatnění je `fromDuel` téhož duelu 409.
Po každém rozhodnutém duelu ohodnotí soudce **shodu platného směru s představou** `a_t ∈ [0, 10]`
(`vision-align {duelId}`): duel musí být rozhodnutý a ve stejném rozsahu, jeden bod na duel (druhý = 409) a hodnotitel
nesmí být strana duelu ani autor challengeru. Body bez duelu (po `verified`) zatím nejdou; přijdou později.
Bod nese `visionRevision` (obsahová verze představy v okamžiku hodnocení). Trend i body vracené čtecím API patří jen
k aktuální verzi; starší body zůstávají uložené. Po změně představy je trend „málo dat“. Legacy body bez
`visionRevision` se do trendu nepočítají: jejich cíl nejde doložit.

Trend z posledních `N = 8` bodů se počítá bayesovskou lineární regresí s neinformativním priorem: odhad sklonu `β̂`
a jeho chyba `se`.

```
P(přibližujeme se) = P(β > 0) = T_{n−2}(β̂ / se)      T = distribuční funkce Studentova t s n−2 stupni volnosti
```

Posterior sklonu při neinformativním prioru (Jeffreys) a neznámém rozptylu je Studentovo t. `T` se počítá bez nové
závislosti, numericky (Simpson přes hustotu t, chyba < 1e−6). Při `se = 0`: sklon > 0 → 1, < 0 → 0, = 0 → 0.5.

- Méně než 3 body = „málo dat“.
- Výstup: `P`, `β̂`, `se`, `n`, poslední `a_t`, slovní stav:
  - `≥ 0.7` přibližujeme se;
  - `≤ 0.3` oddalujeme se;
  - jinak nejasné.

Výpočet je čistá funkce v `backend/editor/brief_vault/brief_vault_duel_math.py` s testem. UI ji jen zobrazuje.

## 4. Kdo co dělá

- **Agenti smyčky** (`opora_cycle.py duel …`):
  - otevírají duel místo tiché změny směru;
  - hájí stranu a odpovídají na `grill`;
  - soudci hodnotí.
  - `/next` vrací otevřený duel disciplíny jako `needs: "duel"` s tím, co je na tahu.
- **Člověk** píše v sekci **Duel** přímo do konverzace, jako v terminálu. Výměna se vybírá slovem v textu, ne tlačítkem: `A:`/`B:` (strana), `?` (grill), jinak `note`. Hned vidí:
  - tahy agentů;
  - `P(B > A)` s rozpadem;
  - trend představy.
- **Asistent v aplikaci** (spouští ho jen zpráva člověka) dostane na požádání kontext duelu a odpoví hned. Tato část přijde ve 2. dávce, viz §6.
- **Aplikace** žádný model nespouští: duel jen ukládá, hlídá pravidla a počítá matematiku.

## 5. API

- `POST /api/brief-vault`:
  - `op: "duel-open"` `{subject, incumbent, challenger, scopeNodeId, discipline?}`;
  - `op: "duel-turn"` `{fragmentId, expectedRevision, side, kind, text, refs?, evidence?}`;
  - `op: "duel-score"` `{fragmentId, expectedRevision, turnId, strength, supports, rebuttedBy?, evidenceOk?}`;
  - `op: "duel-decide"` `{fragmentId, expectedRevision, synthesisTurnId?, override?}` → `{…, decision, applied,
    appliedFragment?}` (vítězný směr se uplatní sám, §3.2);
  - `op: "vision-set"` `{scopeNodeId, note, text | fromDuel}` = první představa rozsahu (jen člověk, `text`), nebo ruční
    dotažení rozhodnutého duelu o projektu vedeného proti aktuální verzi (`fromDuel`, §3.3);
  - `op: "vision-align"` `{score, note, scopeNodeId, duelId}` = bod trajektorie k rozhodnutému duelu (§3.3).
- `GET /api/brief-vault/duel?project&workspace&id` → `{duel, probability: {p, logit, n, contributions}, onTurn, rounds: {A, B}, canDecide, trajectory}`.
- `GET /api/brief-vault/vision?project&workspace&scopeNodeId` → `{vision: {…revize fragmentu s textem, points} | null, trajectory}`.
- **Chyby:**
  - 400: tvar, mez kol a claimů, stejný aktér na obou stranách, soudce píše za stranu (mimo `note`), strana hodnotí,
    `concede` vlastní strany, chybný `rebuttedBy` nebo doklad, `synthesis` bez `synthesisTurnId` nebo s volným `synthesis`;
  - 403: `override` nebo založení představy od agenta (428 neznámý původce);
  - 409: CAS, rozhodnutý duel, druhé skóre téhož soudce na výměnu, druhá `answer` na tutéž `grill`, druhý otevřený duel
    téhož předmětu, duel, který pravidlo ještě nerozhodne („duel ještě nejde rozhodnout: …“), neobhájená syntéza,
    změna představy bez platného `fromDuel` (i zastaralý `visionRef`), ruční op na představě, druhý bod trajektorie
    k témuž duelu.

## 6. Dávky

1. **Teď:**
   - backend `duel` a matematika;
   - `/next`;
   - CLI `duel`;
   - sekce Duel (konverzace, psaní, `P`, trend);
   - e2e průchod open → grill → answer → score → decide → poučení v `tmp_path`.
2. **Potom:**
   - asistent v aplikaci jako okamžitý partner duelu;
   - automatické otevření duelu při `decided: other` nebo nahrazení kořene;
   - náhrada tlačítek Schránky zprávou do konverzace, až se duel osvědčí.

## 7. Teď nestavět

Model v aplikaci, placené API, hodnocení bran modelem bez žádosti, nové tabulky.

Sekce **Duel** Schránky (vnitřní menu → Směr → Duel, s počtem otevřených duelů). Kontrakt: `docs/schranka-duel.md` (§1 duel, §2 výměny, §3 matematika, §4 kdo co dělá, §5 API). Kód ho provádí, nemění. Matematiku (P, trend představy) počítá server; UI ji jen zobrazuje. P se v UI jmenuje **„Síla argumentů pro B (nekalibrovaná)“** (v seznamu „síla B 35 %“, v rozhodnutí „při síle B …“), title „Heuristika ze skóre soudců – není pravděpodobnost ani ověření výsledku.“: dokud není kalibrace na skutečné výsledky, není to pravděpodobnost. Matematika a prahy se tím nemění.

**Proč tady.** Duel je fragment `kind: "duel"` (a představa `kind: "vision"`) ve stromu Schránky, takže patří docku Schránky; vlastní feature složka proto, že je to samostatný viditelný celek s vlastní logikou příkazů.

**Kdo to skládá.** `BriefVaultDock` rozdělí strom rozsahu jednou (`splitVault`): ostatní sekce dostanou strom bez duelů a představ, sekce Duel jejich seznam ze stromového výtahu `duel: {status, subject, turns, scores, p, outcome}` (`duelItemOf`); GET duel jen pro otevřený detail. Představu (`vision: {points, last}`) načte `GET /vision` při změně její revize. Fokus Schránky (fragment z karty nebo „Otevřít fragment“) předá jako `focus`, je to subject nového duelu.

**Ovládání = konverzace jako v terminálu.** Jediný vstup dole, Enter odešle, Shift+Enter nový řádek, žádná tlačítka výměn. Rozepsaný text hlásí dock nahoru (`onDirty`, `vault-drafts.ts`) jako ostatní pole. Výměny mají krátké číslo **#1, #2, …** (pořadí v `duel.turns`, server jen přidává, takže číslo je stabilní); stopa, odkazy „na #N“, „Na tahu“ i rozpad P ukazují #N, plné id je jen v title. Příkazy berou #N i plné id (přesná shoda id má přednost), parser číslo převede na plné id; číslo mimo rozsah = chyba „Výměna #9 tu není (výměny jsou #1–#3)“. Příkazy (`logic/duel-command.ts`, diakritika a velikost písmen nevadí):

| V detailu duelu | Odejde |
|---|---|
| `A: …` / `B: …` | `duel-turn` side A/B, kind `claim` (server: nejvýš 3 tvrzení na stranu, chybu ukáže vstup) |
| `? …` | `grill` za stranu, za kterou člověk už mluví (jinak chyba s příkladem „Napiš třeba: A: <tvůj argument>“) |
| `odpověď #<N\|id>: …` | `answer` s `refs: [id]`, strana opačná k odkázané výměně |
| `uznávám #<N\|id>` | `concede` s `refs: [id]` |
| `syntéza: …` | `synthesis` za stranu, za kterou člověk mluví (strana human píše jen note) |
| `skóre #<N\|id> <0–10> A\|B [doloženo]` | `duel-score` (`doloženo` → `evidenceOk: true`) |
| `rozhodni` / `rozhodni #<N syntézy>` | `duel-decide` (s `synthesisTurnId` u výsledku syntézou) |
| `rozhodni keep\|adopt\|synthesis [#<id syntézy>]: důvod` | `duel-decide` s `override: {outcome, reason}` (synthesis vyžaduje #id) |
| `sladění <0–10> #<id duelu>: poznámka` | `vision-align {score, note, duelId, scopeNodeId}` (i mimo duel) |
| cokoli jiného | `note` (side `human`) |

Mimo detail: `duel: <změna>` → `duel-open` (subject = fragment fokusu, incumbent = jeho text a revize; bez fokusu subject `project` a incumbent = text představy), `představa: <text>` → `vision-set` (s `note`, jen když představa ještě není; jinak chyba „představu mění jen rozhodnutý duel o projektu“), `představa z duelu #<id>` → `vision-set {fromDuel}`. Neplatný příkaz = česká chyba pod vstupem, nic se neodešle. Zápis jde přes `vaultOp` (`../logic/vault-actions.ts`, CAS `expectedRevision`); odpověď zápisu (`duel`, `probability`, `onTurn`, `rounds`, `canDecide`) se promítne hned (`applyWrite`), po rozhodnutí se ukáže poučení, nebo „poučení přeskočeno (duel bez disciplíny)“. Výsledek rozhodnutí je jedna věta nahoře ve stopě (`outcomeLine(decision, challenger, subject.kind)`); „platí od teď“ jen při `decision.applied === true`:

| Stav | Věta |
|---|---|
| keep | „Zůstává A“ |
| adopt, `applied: true` | „Vyhrál nový směr (B) – platí od teď: <text>“ + řádek „uplatněno: zadání má nový text“ (nic víc: zda agenti pokračují, nerozhoduje duel, ale fronta – vyčerpaný fragment čeká na člověka) |
| adopt, `applied: false` | „Vyhrál nový směr (B), ale neuplatnil se: <reason>“ (důvod serveru doslova, jednou, červeně; žádné „platí dál A“, předmět mohl změnit někdo jiný) |
| adopt, `applied` chybí (starší data) | „Vyhrál nový směr (B) – stav uplatnění neznámý“ |
| předmět je karta (`subject.kind: node`) | „Vyhrál nový směr (B) – karta se automaticky nemění; uprav ji podle: <decision.text>“ |
| syntéza | obdobně: „Syntéza – platí od teď: …“ / „Syntéza vyhrála, ale neuplatnila se: <reason>“ / „Syntéza: … – stav uplatnění neznámý“ / „Syntéza vyhrála – karta se automaticky nemění; uprav ji podle: …“ |

Detail pod tím (`decisionLine`): „Rozhodnuto: vyhrál B při síle B 80 % · přebito člověkem: …“. `decision` z odpovědi decide se sloučí do stavu duelu (`applyWrite`).

Nápověda pod vstupem je jeden řádek nejčastějších příkazů (v duelu `A: / B: argument · ? otázka · odpověď #N: … · rozhodni`, v seznamu `duel: … · představa: …`), zbytek v rozbalení „další příkazy“ (`details`, ne tlačítko). „Na tahu“ říká, co napsat: „Na tahu B: odpověz na #3 – napiš: odpověď #3: …“, a když lze rozhodnout, „Lze rozhodnout – napiš: rozhodni“ (`onTurnLines`).

Zápis Schránky (`vaultOp`) jde přes `trackSaveWrite`: Schránka je v otisku uložené verze, takže neohlášený vlastní zápis by lišta verzí ukázala jako „Změna mimo toto okno · načíst“. 409 = duel se mezitím změnil, načte se znovu.

**Dílky** (`components/`)

- `DuelSection.tsx` — rodič sekce: seznam nebo detail, představa s trendem, fokus, vstup; živý duel přes `useDuel`.
- `DuelList.tsx` — duely rozsahu (otevřené nahoře): název, stav, „síla B 35 %“.
- `DuelTrail.tsx` — A a B jako dvě karty, rozhodnutí (u override „přebito člověkem: důvod (pravidlo: …)“), výměny v čase (strana, druh, autor, text, odkazy, doklady jen http(s) jako odkaz, skóre soudců).
- `DuelOdds.tsx` — síla argumentů pro B (nekalibrovaná) s pruhem a prahy 40 % / 75 %, n hodnocených, „Na tahu“, kola A/B z 4, rozpad příspěvků s důvodem, trend představy.
- `DuelInput.tsx` — textarea s výzvou ›, chyba, jednořádková nápověda a rozbalení „další příkazy“.

**Logika** (`logic/`, testy vedle)

- `duel-command.ts` — text + kontext → tělo `POST /api/brief-vault`, nebo chyba; `resolveTurn` (#N → plné id).
- `duel-view.ts` — `applyWrite`, `decisionLine`, `outcomeLine`, `appliedLine`, `lessonNotice`, `turnNumbers` / `turnRef` (#N), tvary odpovědí `GET /api/brief-vault/duel` a `/vision`, procenta, prahy (`zoneOf`), slovní stav trendu, řazení výměn, „Na tahu“, kola, skóre, rozpad, `humanSide`.
- `duel-tree.ts` — `splitVault` (druhy z `NOT_BRIEF_KINDS` sdíleného modelu) (duel/vision pryč ze stromu ostatních sekcí, aby se kořen představy nestal cílem Podnětu ani uzlem zadání), řádek seznamu, počet otevřených.
- `use-duel.ts` — vazba na React: `useDuel` (sdílený `createPoller`, 3 s; `apply` z odpovědi zápisu, starší revize z pollu ji nepřepíše), `useVision`.

**Styl**

`styles/duel.css`, blok `duel` s příběhovým komentářem.

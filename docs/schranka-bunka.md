# Schránka – spustitelná buňka (K15)

Doplněk `docs/schranka-neurony.md` (§3, §11, §13). Má přednost tam, kde se týká `synthesized.checks`, `verified.actual.run` a `learned.kind`.

## 1. Proč

Mapa originálů `neuron-brain` 00–09 → OPORA (relace A, 2026-10-15) ukázala: buňka originálu je uzel s cílem, vstupem,
výstupem, pamětí a vazbou dál a její výkon se ověřuje proti acceptance („žádné domněnky bez benchmarků“, 07).
Schránka dnes mezi `placed` a `verified` nic nevykoná a `verified.actual` je jen tvrzení navrhovatele. Poučení tak
vzniká z hodnocení plánu, ne z výkonu. Infrastruktura výkonu už existuje (karta: `checks`, `goal_mode`,
`evidence.checksRun`, pipeline karty), jen na ni cyklus nenavazuje.

## 2. Buňka (bez nového úložiště a bez modelu v aplikaci)

Buňka = fragment s bránou `synthesized`, která nese `checks`, a jeho karta po `placed`.

| Část | Kde |
|---|---|
| cíl | `synthesized.done` → `spec.goal` karty |
| vstup | text fragmentu + doklady + živá poučení disciplíny (`/next.lessons`, `node-brief`) |
| výstup (artefakt) | soubory, které vykonavatel vytvoří v pracovní složce; doloží je běh kontrol |
| ověření | `synthesized.checks` → `card.checks` + `goal_mode: until_checks_pass` |
| paměť | `learned` (poučení s vyhasínáním, §5) |
| vazba dál | vazby `next` karty (§4) a poučení ve frontě dalšího fragmentu disciplíny |

Vykonavatel je vnější agent (relace Claude Code pod předplatným, existující pipeline karty). Aplikace model nespouští
ani příkazy neprovádí (§10 a „model jen na 4 místech“ platí beze změny).

## 3. Kontrakt

1. **`synthesized.checks?`**: `[{id: [A-Za-z0-9_-]{1,80}, command: text ≤300}]`, 1–4 položky, jedinečná `id`.
   Jedna syntaxe pro server i CLI: `shlex.split(posix=True)` musí projít, program (první slovo) je jen
   `python | py | uv | pytest | npm | npx | node`, žádné `| & ; > < `` ` `` `$(` ani `\` (cesty jen s `/`), žádný token
   (ani jeho část za `=` či `,`) nezačíná `/` nebo `X:` a neobsahuje `..`. Kontroly se pevně určí PŘED výkonem a jsou
   **měřítkem napříč koly**: další kolo fragmentu musí mít stejné `checks` (včetně přidání checks v dalším kole, když předchozí
   `synthesized` žádné neměl), změnu dělá člověk.
2. **Karta:** `card_of` z `checks` zapíše `checks` (stejná id a příkazy) a `goal_mode: "until_checks_pass"`; bez
   `checks` beze změny. `extend` je na existující kartu nepřenáší (`checks`/`goal_mode` jsou chráněná pole, zápis
   agentem = 403); díky bodu 1 zůstávají kontroly karty z kola 1 shodné s fragmentem.
3. **`verified.actual.run?`**: `{executor ≤80, verifier ≤80, checks: [{checkId, command, exitCode: int, durationMs: int ≥0,
   outputSha256: 64 hex}], at: ISO 8601 se zónou}`. Pravidla serveru (400 při porušení):
   - má-li `synthesized` `checks` a `tests` je `pass`/`fail`, je `run` povinný a jeho `checks` přesně odpovídají
     `synthesized.checks` (id i příkaz, totéž pořadí);
   - `tests == "pass"` ⇔ všechny `exitCode == 0`; jinak `"fail"`;
   - `executor ≠ verifier`; návrh s `run` podává jen `verifier` a aktér, který bránu `verified` zapíná, není
     `executor` (oddělení vykonavatele a ověřovatele);
   - bez `run` se při `checks` smí jen `tests: "untested"` (plán schválen ≠ testy, §13 beze změny).
   - s `run` server do uloženého payloadu brány přidá `runTrust: "reported"` (vedle `predictionError`; klient ho
     poslat nesmí): běh je nahlášený, ne nezávisle atestovaný (viz §5 a docs/schranka-overovatel-navrh.md). Nic dalšího
     se na něj neváže (uzavření ani schválení karty, kvalita §11 beze změny).
4. **`learned`:** po neúspěšném `verified` (§13 `verified_outcome`) musí být `kind: "antipattern"`, po úspěšném s `tests == "pass"` `kind: "pattern"`; jinak 400.
5. **Ověřovatel (`opora_cycle.py run-checks F --root DIR --tests T --executor A`)**: načte `synthesized.checks`
   fragmentu, zkopíruje `DIR` do dočasné složky, odstraní z ní konfiguraci, kterou by vykonavatel mohl kontrolu
   ohnout (`conftest.py`, `pytest.ini`, `tox.ini`, `setup.cfg`, `sitecustomize.py`, `usercustomize.py`), překryje ji
   zdroji kontrol z `T` (dané před výkonem, mimo složku vykonavatele) a spustí
   každý příkaz bez shellu (`shlex`, `shell=False`, timeout 600 s), změří čas, otisk výstupu a podá
   `propose verified` s `run` (verifier = vlastní aktér; odmítne `executor == actor`). Volitelně `--plan-score N`
   doplní `planApproved`/`planScore`. Výstup do konzole jen poslední 2 000 znaků každé kontroly.

## 4. Jeden průchod (důkaz řezu)

zadání (fragment) → `synthesized` s `checks` → `decided yes` → `placed` (karta s `checks`, GOAL) → vykonavatel vytvoří
artefakt v pracovní složce → ověřovatel `run-checks` (skutečný běh) → potvrzovatel `yes verified` → `learned` podle
výsledku. Neúspěch: `tests: fail` → nové kolo (§12), mez 3 kola a CAS beze změny.

Demonstrace běží v izolovaném dočasném fixture (pytest `tmp_path`), nikdy nad `P:\opora-data`.

## 5. Hranice důvěry (BLOCKED pro Hermese)

`run` je **přiřazený, ne atestovaný** doklad: server nespouští příkazy (§10) a identita aktéra je deklarovaná
(`X-Opora-Actor`, `identityVerified: false`). Lhář v roli ověřovatele může podat smyšlený běh pod svým jménem.
Server zaručí jen konzistenci (shoda s `checks`, `tests` ⇔ exit kódy, různí aktéři, podává `verifier`) a dohledatelnost
(kdo co tvrdil). Skutečná atestace = ověřená identita aktéra nebo běh kontrol mimo vliv navrhovatele; obojí je
architektonické rozhodnutí, ne součást řezu.

## 6. Teď nestavět

Spouštění kontrol serverem, automatický vykonavatel na `/next`, nové tabulky, podmínka platnosti poučení (`when`),
DNA projektu, baseline. Rozpor „sektor = disciplína vs. sektor = dodavatelný celek“ řeší koordinace (handoff relace A).

# Zefektivnění OPORY pro agenty – méně volání, žádné zbytečné pokusy

Stav: kontrakt E1–E4, rozhodnutí v §8 (2026-10-28). Podklad: eval v2 `opora-vs-bare` (5 případů × 2 opakování),
průzkum kódu a vnější zdroje (§7).

## 1. Co jsme naměřili

| | S OPOROU | Terminál |
|---|---|---|
| Kvalita výstupu | **0,92** | 0,83 |
| Volání nástrojů na běh | ~160 | ~14 |
| Vstupní tokeny na běh | 7,9 M | 0,19 M |
| Zbytečné pokusy | ~13 | ~1 |
| Čas / cena | 13,6 min / 4,16 USD | 1,3 min / 0,30 USD |

**OPORA sama je rychlá.** Volání trvá 0,3–1 s a dohromady dělá ~15 % času nástrojů. Čas i cena vznikají v kolech modelu:
každé volání je nové kolo, ve kterém model znovu čte celý kontext. **Páka je tedy počet volání, ne rychlost serveru.**

Kam jdou volání (průměr na běh s OPOROU):

| Položka | Volání |
|---|---|
| Obřad karty | ~50 |
| Zápisy kódu | ~42 |
| Build a test po každé kartě | ~19 |
| Zápis JSON payloadů | ~11 |
| Shell a čtení | ~25 |

Obřad karty je: kontext, claim, assignment, krok po kroku, results, commit a sha, local-merge, check-run a close.
Jedna karta tak stojí 8–12 volání a agent plánuje 6–16 karet na stránku.

Zbytečné pokusy:
- **Zamítnutá oprávnění, ~6–7 na běh.** Skill posílá koncepty do `~/.opora/drafts` (`SKILL.md:47`), do `export …` (`cycle.md:155`)
  a tokeny do `~/.opora/hub` (`opora_hub.py:53`), tedy mimo pracovní složku.
- **409 „evidence kroku vyžaduje notes“.** Klient `notes` nevyžaduje, server ano (`opora_step_results.py:48`).
- **422 neznámá role sekce.** Role jsou jen v `references/api.md:297`, v receptu ne.
- **409 „Execution is no longer authoritative“ / „SQL context live scope changed during replay“.** Agent upraví
  `canvas-plan` (přidá stránku do aplikace) a tím změní rozsah kontextu karty, kterou drží
  (`specification_scope.py:77-89`). Nebo lease vyprší, protože TTL je 900 s bez heartbeatu.

## 2. Zásady

1. **Jedno volání na záměr.** Agent říká, *co* chce (vezmi kartu, odevzdej kartu), ne *jak* projít stavy.
2. **Co jde odvodit bez modelu, odvodí server.** Jde o sha z gitu, commity karty, poznámky kroků z commitů, check-run z výsledku
   buildu a uzavření při splněné bráně. Brána se nemění, jen ji volá server místo agenta.
3. **Chyba = oprava.** Každá 4xx říká pole, očekávaný tvar a příklad, nebo další krok (#139 platí dál).
4. **Nic mimo pracovní složku.** Payloady jdou přes stdin nebo inline, stav klienta leží v `<workspace>/.opora/` (gitignore).
5. **Karta = ověřitelný přírůstek.** Karta je stránka nebo sekce, ne komponenta. Build a test jedou jednou na kartu uvnitř odevzdání.

## 3. E1 – Složené akce karty (backend + klient)

### 3.1 `POST /api/oporahub/executions/start`
Tělo: `{project, workspace, nodeId, ttlSeconds?}`.

Server v jednom volání:
1. připne kontext (`/context`),
2. spočítá `expectedAcceptedHead`, `expectedContextVersion` a budget hlavy z čerstvého stavu,
3. provede claim s deterministickým `requestId`,
4. vrátí assignment.

Odpověď: `{executionId, token, epoch, assignment, steps:[{id,title,dod}], next}`.

Pravidla:
- Chyby nesou `code` a `hint` jako dnes, například `graph_acceptance_required`.
- Idempotence: opakované `start` téhož aktéra na téže kartě s živým lease vrátí stávající execution.

### 3.2 `POST /api/oporahub/executions/{id}/deliver`
Hlavička: `X-Opora-Execution-Token`.

Tělo:
```json
{"summary": "…", "steps": [{"stepId": "s1", "status": "done", "notes": "…"}],
 "commit": "<sha>|null", "checks": [{"name": "npm test", "status": "green|red", "output": "…"}],
 "decisions": [], "close": true}
```

Server v jednom volání a v jedné transakci tam, kde to jde:
1. **Kroky.** Krok bez `notes` dostane poznámku z předmětů commitů s trailerem `Opora-Node` nebo s cestami karty
   (`commit_pairs.py`). Když žádný commit není, platí `"notes": summary`. Kroky nezmíněné v těle zůstanou otevřené.
2. **Results.** Server zapíše `stepResults` a `selfChecks` s `headSha`.
3. **Local-merge.** Platí jen pro projekt bez GitHubu. `commit` výchozí = `git rev-parse HEAD` pracovní kopie a ověří se jako dnes.
4. **Check-run.** Za každou položku `checks` zapíše check-run na `scope=nodeId` a sha. Červená položka zastaví krok 5.
5. **Close.** Když `close` platí, autonomie je `full` a `closable` je pravda, server zavře kartu stejnou bránou
   (`opora_card_done.py`). Jinak vrátí `missing` a `next`.

Odpověď: `{delivered: {...}, merged: sha|null, checks: n, closed: bool, missing: [...], next: {verb,targetId,command}}`.

Lease:
- `deliver` přijme i vypršelý lease, pokud kartu mezitím nepřevzal nikdo jiný (epoch beze změny). Odpadá tím 409 po dlouhém
  buildu.
- Server totéž zapíše do záznamu činnosti jako `lease_renewed_on_deliver`.

### 3.3 Kontext karty a změny plánu
Když `canvas-plan` od **téhož aktéra** změní rozsah kontextu karty, kterou drží:
- server po dávce kontext karty přepne na novou hlavu (re-pin) místo pozdějšího 409;
- v odpovědi dávky vrátí `rePinned:[executionId]`.

Cizí změna dál vrací 409 s `hint` „spusť `start` znovu“.

### 3.4 Klient
`opora_hub.py start --node N` a `opora_hub.py deliver --execution E --summary T [--step s1:"pozn."] [--check "npm test=green"]
[--no-close]`.

Tělo smí přijít i přes `--json -`, tedy stdin. Totéž umí `opora_api.py` a `opora_write.py` (`--json -`).

Stav klienta a tokeny:
- leží v `$OPORA_HOME`, jinak v `<cwd>/.opora/`, jinak v `~/.opora`;
- při prvním zápisu se do `.gitignore` pracovní kopie doplní `.opora/`.

**Cíl:** obřad karty z 8–12 volání na **2** (`start`, `deliver`).

## 4. E2 – Skill a recept (bez kódu serveru)
- Recept „stavba stránky“ přepsat na E1:
  1. `state`,
  2. jedna dávka `canvas-plan` přes stdin, nejdřív celý plán a pak teprve práce,
  3. `act propose`/`accept`,
  4. pro každou kartu `start` → kód + commit s `Opora-Node: <id>` → `npm run build && npm test` jednou → `deliver`,
  5. cesta.
- Role sekcí, povinné `notes` a příklad těla přímo v receptu.
- **Pravidlo velikosti:** karta = stránka nebo sekce s vlastním ověřením. Malá stránka = 1–3 karty. Komponentu rozepiš do `spec.steps`,
  ne do karet.
- Odstranit `~/.opora/drafts`, `export` a payload soubory ze všech referencí (`api.md`, `canvas-plan.md`, `rozklad.md`,
  `workflow.md`, `storyboard.md`, `cycle.md`, `hub-loop.md`).
- Agent-state `actions` dostane pole `command`: hotový řádek `opora_hub.py …` pro danou akci (§6, E3).

## 5. E3 – Procesy na pozadí bez modelu (strážci, kteří práci dělají, ne jen hlásí)

| Proces | Co dělá | Ušetří |
|---|---|---|
| **Zapisovač kroků** (`guard_prace` rozšířený) | commity s `Opora-Node` průběžně páruje ke kroku a zapisuje `evidence.commits`; heartbeat lease, dokud do worktree karty přibývají commity | `step`, `heartbeat`, 409 z vypršení |
| **Spouštěč kontrol** (jen projekt s `agentAutonomy.full` a jen příkazy z `card.checks` uložené člověkem nebo schváleným plánem) | po commitu karty pustí deklarované kontroly v izolované kopii (`harness_verifier_runner`) a zapíše check-run | build/test volání agenta, ruční check-run |
| **Připravené příkazy** | agent-state u každé `ready` akce vrátí `command`, `next` po každé akci také | čtení skillu, hádání tvaru |
| **Předehřátý kontext** | po přijetí grafu připraví sparse kontext a hlavy pro `start` | čas `start` |
| **Strážce mapy po dávce** (už existuje, N3) | díry vrací v odpovědi `canvas-plan` | zvláštní `map-check` |

Spouštěč kontrol spouští příkazy. Platí pro něj:
- jen na loopbacku;
- jen v pracovní kopii projektu;
- jen příkazy z `card.checks`;
- s limitem času;
- **před zapnutím rozhodne člověk** (§8).

## 6. E4 – Rozhraní MCP (měřit, ne hádat)
OPORA vystaví stejné složené akce jako MCP server (`state`, `plan`, `start`, `deliver`, `journey`), tedy typované argumenty
bez payload souborů a shellu.

Headless agent dostane `--mcp-config` a jedno povolení `mcp__opora__*`. Podle vnějších zdrojů to odstraní zamítání shellových
vzorů, ale přímé srovnání neexistuje.

Postup:
1. Nejdřív E1 + E2, změřit.
2. Pak A/B „skripty vs. MCP“ v evalu (jen rameno A, 1 opakování).

## 7. Zdroje
- Anthropic, *Writing effective tools for agents*: méně a účelových nástrojů, stručné odpovědi, chyby s příkladem,
  měřit volání na úlohu.
- Anthropic, *Building effective agents*: poka-yoke nástrojů, „ground truth“ od prostředí po každém kroku.
- SWE-agent (arXiv 2405.15793):
  - kompaktní sdružené akce a kontrola uvnitř akce;
  - lint při editaci: +3 body;
  - bez editačního příkazu: 18,0 → 10,3 %.
- Claude Code docs: hooks = deterministická kontrola; headless `--allowedTools`, `--permission-prompts none`,
  `permission_denials` ve výstupu.
- Měřitelný doklad o ceně příliš jemného rozkladu pro kódování jsme nenašli. Pravidlo velikosti karty (§2.5) je odvozené
  z vlastního evalu.

## 8. Rozhodnutí člověka (2026-10-28)
1. **Uzavření v `deliver` (§3.2 krok 5): ano, při plné autonomii.** Brána se nemění, jen ji volá server v rámci odevzdání.
2. **Spouštěč kontrol (§5): ano, s omezeními.** Platí jen při plné autonomii, jen na loopbacku, jen příkazy z `card.checks`
   a s limitem času.

## 9. Pořadí a ověření
- **E1:** backend `start`/`deliver`/re-pin + klient + testy vedle modulů.
- **E2:** skill.
- **E3:** připravené příkazy a zapisovač kroků. Spouštěč kontrol až po rozhodnutí §8.2.
- **E4:** MCP jako A/B.

Ověření: rameno A evalu v2 (5 případů × 1 opakování).

Cíle:
- ≤ 70 volání na běh;
- ≤ 3 zbytečné pokusy;
- kvalita ≥ 0,90 (beze ztráty proti 0,92).

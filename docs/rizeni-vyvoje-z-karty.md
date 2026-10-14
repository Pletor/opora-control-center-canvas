# Řízení vývoje z karty: kde data žijí, kudy tečou a odkud se řídí

Karta na plátně je jediné zadání pro agenta a jediné místo, kde člověk vidí, jak práce dopadá. Tento dokument
říká tři věci: **kam se co ukládá** (aby nikdo nehledal pravdu na dvou místech), **jak data procházejí jednou
kartou** od zadání po uzavření, a **odkud se vývoj řídí** – kdy z Opory a kdy z terminálu. Kontrakt dat je
v [karta-pro-agenty.md](karta-pro-agenty.md); tady je mapa a postup.

## 1. Kde co žije

Každý projekt má jednu složku `P:\opora-data\projects\<id>\` (kořen dat nastavuje `opora.local.toml`) a v ní
jednu databázi `project.sqlite`. Nic z toho není v gitu cílového projektu: **kód je v repu, zadání a práce
jsou v Opoře, nic není na obou místech.**

| Co | Kde | Kdo zapisuje | Poznámka |
|---|---|---|---|
| Graf plátna (uzly, sektory, oblasti, komentáře, vazby, pozice) | git projekt: `canvas/workspaces/<wid>/graph.json`; lokální projekt: tabulka `drafts` | člověk na plátně, agent přes `canvas-plan` a `/api/graph` | strop 2000 uzlů / 4000 vazeb; plátno varuje od 80 % |
| Stav karty Desktop v3 (fáze, bloky s porty, pipeline etap `stages`, důkazy, podněty `ideas`, kolo `round`, `done`, pravidla, rozhodnutí, zprávy na vazbách `edges`) | tabulka `desktop_v3_state` (jeden revizovaný dokument per workspace) | člověk z inspektoru, agent přes `agent-output` a `block` | každý zápis je CAS na `expectedRevision` |
| Text karty, zadání (`goal / non_goals / acceptance`), deník, odkazy | `node_text_revisions`, `node_spec_revisions`, `node_journal_revisions`, `workspace_documents` | člověk, agent přes `node-text` / `node-spec` | revize se nemažou |
| Prostor agenta (`frame / log / failures / fixes / handoff`) | `agent_workspace_revisions` | agent; člověk smí číst i psát | paměť karty, ne zadání |
| Snímek zadání při převzetí, lease, výsledky agentů, kola karty | `assignment_snapshots`, `card_leases`, `agent_result_records`, `card_rounds` | server při `lease claim`, `agent-output`, `card-round` | append-only evidence; `contextVersion` váže výsledek na verzi zadání |
| Adresované zprávy mezi kartami a potvrzení | `agent_messages`, `agent_message_receipts` | agenti | `identityVerified: false` je záměrné |
| Podklady (obrázky, soubory ke kartě), kresby vrstvy | `nodes/<id>/`, `drawing_revisions`, `drawing_files` | člověk | kresba je per vrstva, obrázky s ní |
| Procesy (návrh → běh → hotovo ⇄ oprava) a odpovědi agentů | `processes/<prc-id>/*.json` | člověk, agent | `shared/process.schema.json` |
| Verze plátna (uložené snímky) | `canvas_versions` | člověk (Uložit) | obnova vrací graf i stav |
| OporaHub (commit specu, párování commitů, verdikt) | `oporahub/<id>.json`, `oporahub/main.log`, index `opora_commits` | člověk, orchestrátor | pravda je v souborech, index se přestaví |
| Mapy projektu (Graphify, Archify) | **v kořeni hlavního worktree projektu**: `graphify-out/`, `archify-out/` | automatika po mergi do `main` | git-ignorované přes `.git/info/exclude`; jediná sada, bez verzí |
| Paměť role agenta (co se role naučila napříč projekty) | **mimo Oporu**: OpenViking `http://127.0.0.1:1933`, adresa `viking://user/<role>/peers/<projekt>/resources/cards/<nodeId>/` | Opora po uzavření karty a při `remember` | klíče rolí v `app_settings`; viz [pamet-agentu.md](pamet-agentu.md) |
| Schránka zadání (fragmenty, brány) | `brief_fragment_*`, `brief_gate_proposals`, `brief_lessons` | člověk a agenti cyklu | [schranka-neurony.md](schranka-neurony.md) |

Pravidlo pro nový druh dat: **má-li být vidět na plátně nebo v briefu, patří do stavu karty nebo do vlastní
append-only tabulky v `project.sqlite`; nikdy do cílového repa a nikdy do souboru, který čte jen jeden
agent.** Soubor v repu (např. `docs/…`) je podklad, karta na něj odkazuje `sourceRef` nebo podkladem.

## 2. Jak data tečou jednou kartou

```
zadání (člověk)        převzetí (agent)          práce               výstup                 uzavření
spec + bloky + pravidla → lease + snímek zadání → prostor agenta → agent-output ─┬→ stav bloků   → done navrhne agent,
+ sourceRef + checks       contextVersion          (frame/log/…)     (CAS revize) ├→ zprávy na vazbách   potvrdí člověk
                           node-brief (1 JSON)     role memory recall              ├→ etapy pipeline      → kolo se zamrazí
                                                                                   ├→ důkazy, podněty      → paměť role (commit)
                                                                                   └→ záznam výsledku      → mapa se obnoví po mergi
```

1. **Zadání** vzniká v inspektoru (nebo `canvas-plan` z terminálu): cíl, mimo rozsah, akceptace, bloky
   splnění, pravidla, `sourceRef`, kontroly (`checks`). Kontrolní pás na kartě (10 polí) říká, co chybí.
2. **Router** (agent v roli router) určí profil pipeline: `goal`, `code`, `design`, `security`, `testing`,
   `research`. Od té chvíle má karta **řadu kuliček procesu** (viz §3).
3. **Relace na etapě**: `frontier` → `lease claim` → `node-brief` → práce → `agent-output` se `stages` →
   `lease release`. Každá etapa je nová relace; předávka je `note` etapy a zpráva na odchozí vazbě.
4. **Kritici** (`review`, `critic` s pohledy hodný uživatel / vyčuraný / hacker) dají `failed` jen pro
   blokátor; jinak `passed` + podnět do `ideas`. Selhání samo vloží `fix` a opakování; po dvou smyčkách
   karta čeká na člověka (jantar na plátně).
5. **Uzavření**: agent `done` jen navrhne, člověk potvrdí. Kolo se zamrazí do `card_rounds`, prostor agenta
   se zrcadlí do paměti role, mapy se po mergi přepíší.

Nic z toho se nepředává chatem. Když si agent potřebuje něco poznamenat pro dalšího, jde to do prostoru
agenta (`handoff`), do zprávy na vazbě nebo do adresované zprávy; všechno trojí je v `node-brief` dalšího.

## 3. Kuličky procesu na kartě

Pod hlavou karty uzlu je řádek procesu: čip profilu, řada kuliček a počet hotových etap. Mnemotechnika:

| Prvek | Význam |
|---|---|
| **barva kuličky** = kdo pracuje | práce (akcent), test (zelená), review (modrá), oprava (jantar), kritik podle pohledu: hodný uživatel (teal), vyčuraný (fialová), **hacker = security (červená)** |
| **výplň** = jak dopadla | obrys = čeká, plná = prošla, plná s křížkem = selhala, čárkovaná = přeskočil člověk, pulsující = běží |
| **kroužek** = kde proces stojí | akcentový kroužek = etapa na řadě; jantarový kroužek = uvízlo, čeká na člověka (čip „👤 čeká“) |
| **čip profilu** | `Security` je zvýrazněný: karta má bezpečnostní pipeline (review + hacker kritik + test) |
| **„čeká na router“** | karta bez pipeline; router ji ještě nenasměroval |

V oddálení zůstanou jen tečky, takže z dálky je vidět, kde proces běží, kde selhal a kde čeká na člověka,
aniž by se karta otevírala. Detail etap (zadání, poznámky, přeskočení) je v bloku Pipeline vedle karty.

## 4. Jak tvořit detail karty

Detail karty je **inspektor vpravo** (záložky Zadání, Texty, Agenti, Podněty, Historie kol) a **bloky na
kartě**. Dvě cesty, jeden výsledek:

| Krok | Z Opory | Z terminálu (skill `opora-control-center`) |
|---|---|---|
| založit sektor a karty | `+` na plátně, dvojklik na prázdné plátno | `opora_write.py canvas-plan --dry-run` → ostře (dávka: oblast → sektor → karty, vazby `next`) |
| napsat zadání | inspektor → Zadání (cíl, mimo rozsah, akceptace) | `opora_write.py node-spec` |
| bloky splnění a porty | přímo na kartě (`+ Blok`, `+ port`, textarea) | `POST /api/desktop-v3/block` (`add / update / remove / todo`) |
| pravidla a rozhodnutí | inspektor → Agenti → Paměť projektu | `agent-output.decisions`; pravidlo od agenta je jen návrh |
| kontroly a `sourceRef` | inspektor → Zadání | `canvas-plan` (`checks`, `sourceRef`) |
| ověřit, že karta je úplná | kontrolní pás na kartě (10 polí zelených) | `opora_read.py node-brief` → `checklist` |

Laťka hotové karty: cíl + akceptace + aspoň jeden blok s podmínkou + pravidla must/must_not + `sourceRef`
u karty na existující kód + `checks` u karty s testy. Dokud pás není zelený, router kartu nesměruje.

## 5. Z terminálu, nebo z Opory?

| Situace | Řídit z | Proč |
|---|---|---|
| plánování oblasti / sektoru, přeskupení plátna, kresba | **Opora** | geometrie, oblasti a vazby se dělají okem; terminál na to nemá nástroj |
| psaní zadání jedné karty, bloky, pravidla | Opora (inspektor) nebo asistent v okně | asistent zapisuje po schválení člověkem; výsledek je hned vidět |
| vykonání karty / etapy pipeline | **terminál v kořeni projektu** (`claude` + skill, nebo hook-řízená relace) | kód je v repu; agent musí vidět soubory, spustit testy, commitovat |
| router, kritici, review | terminál (jiná relace než autor) | nezávislost: server hlídá jméno relace |
| hromadné založení karet z plánu | terminál (`canvas-plan --dry-run` → ostře) | dávka s náhledem a digestem |
| potvrzení hotovo, svěření autonomie, brána sektoru, verze plátna | **jen Opora** (člověk) | agent dostane 403 |
| sledování, co se děje | Opora (plátno: kuličky, pás, obálky na vazbách, lišta „Práce teď“) | jeden pohled, žádné logy |

Praktické pravidlo: **myslí se a schvaluje v Opoře, vykonává se v terminálu.** Jeden terminál = jedna
karta (nebo jedna etapa). Více agentů = více terminálů na nepřekrývajících se cestách.

## 6. Paměť role (OpenViking) a co s ní

OpenViking běží (`/health` ok, v0.4.17.1), ale Opora hlásí `needs_provisioning`: backend musí startovat
s `OPORA_OPENVIKING_ADMIN_API_KEY` (dělá to `tools/opora_remote.ps1`; ruční `uv run opora` ho nemá).
Po provisioningu (`POST /api/memory/provision {"confirmed": true}`) agent v `node-brief.context.roleMemory`
dostane, co se jeho role naučila na podobných kartách, a při uzavření karty se jeho prostor zrcadlí
zpět. Co tam **nepatří**: zadání karty, kód, tajemství; paměť je popis zkušenosti, ne pravda o kódu.

## 7. Co se během noční směny 2026-10-15 změnilo

- Kuličky procesu na kartě (§3), původně jen v bloku Pipeline.
- Velké plátno: drafty bloků v úložišti → kreslí se jen viditelné karty, MiniMap do 500 uzlů, varování
  u stropu.
- Mapa projektu: serverový přehled komunit (`GET /api/graphify/overview`) a vlastní lehká mapa místo
  iframe s 1780 uzly; původní HTML jen na vyžádání.

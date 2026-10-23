# Řízení vývoje z karty: kde data žijí, kudy tečou a odkud se řídí

Karta na plátně je jediné zadání pro agenta a jediné místo, kde člověk vidí, jak práce dopadá. Tento dokument
říká tři věci: **kam se co ukládá** (aby nikdo nehledal pravdu na dvou místech), **jak data procházejí jednou
kartou** od zadání po uzavření, a **odkud se vývoj řídí** – kdy z Opory a kdy z terminálu. Kontrakt dat je
v [karta-pro-agenty.md](karta-pro-agenty.md); tady je mapa a postup.

## 1. Kde co žije

Každý projekt má jednu složku `P:\opora-data\projects\<id>\` (kořen dat nastavuje `opora.local.toml`) a v ní
jednu databázi `project.sqlite`; cesty v tabulce jsou relativní k této složce, pokud není řečeno jinak.
**Kód je v repu, zadání a práce jsou v Opoře, nic není na obou místech.** Dvě výslovné výjimky: mapy
(`graphify-out/`, `archify-out/`) leží v kořeni worktree projektu, protože je čtou nástroje přímo nad kódem,
a jsou git-ignorované; graf plátna git projektu leží v datech Opory, nikdy v cílovém repu. Autoritou pro
průběh etap je `desktop_v3_state.stages`; soubory procesů (`processes/`) jsou starší, nepoužívaná cesta.

| Co | Kde | Kdo zapisuje | Poznámka |
|---|---|---|---|
| Graf plátna (uzly, sektory, oblasti, komentáře, vazby, pozice) | git projekt: `canvas/workspaces/<wid>/graph.json`; lokální projekt: tabulka `drafts` | člověk na plátně, agent přes `canvas-plan` a `/api/graph` | strop 2000 uzlů / 4000 vazeb; plátno varuje od 80 % |
| Stav karty Desktop v3 (fáze, bloky s porty, pipeline etap `stages`, důkazy, podněty `ideas`, kolo `round`, `done`, pravidla, rozhodnutí, zprávy na vazbách `edges`) | tabulka `desktop_v3_state` (jeden revizovaný dokument per workspace) | člověk z inspektoru, agent přes `agent-output` a `block` | každý zápis je CAS na `expectedRevision` |
| Text karty, zadání (`goal / non_goals / acceptance`), deník, odkazy | `node_text_revisions`, `node_spec_revisions`, `node_journal_revisions`, `workspace_documents` | člověk, agent přes `node-text` / `node-spec` | revize se nemažou |
| Prostor agenta (`frame / log / failures / fixes / handoff`) | `agent_workspace_revisions` | agent; člověk smí číst i psát | paměť karty, ne zadání |
| Snímek zadání při převzetí, lease, výsledky agentů, kola karty | `assignment_snapshots`, `card_leases`, `agent_result_records`, `card_rounds` | server při `lease claim`, `agent-output`, `card-round` | append-only evidence; `contextVersion` váže výsledek na verzi zadání |
| Adresované zprávy mezi kartami a potvrzení | `agent_messages`, `agent_message_receipts` | agenti | `identityVerified: false` je záměrné |
| Podklady (obrázky, soubory ke kartě), kresby vrstvy | `nodes/<id>/`, `drawing_revisions`, `drawing_files` | člověk | kresba je per vrstva, obrázky s ní |
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

## 3. Kuličky procesu, sloty dokladů a stavová věta na kartě

Pod hlavou karty uzlu je proces: čip profilu, řada kuliček a počet hotových etap; pod nimi čtyři sloty dokladů
Testy · Security · Review · Merge na pevných místech a jedna stavová věta (kontrakt `docs/proces-karty.md`).
Mnemotechnika kuliček:

| Prvek | Význam |
|---|---|
| **barva kuličky** = kdo pracuje | práce (akcent), test (zelená), review (modrá), oprava (jantar), kritik podle pohledu: hodný uživatel (teal), vyčuraný (fialová), **hacker = security (červená)** |
| **výplň** = jak dopadla | obrys = čeká, plná = prošla, plná s křížkem = selhala, čárkovaná = přeskočil člověk, pulsující = běží |
| **kroužek** = kde proces stojí | akcentový kroužek = etapa na řadě; jantarový kroužek = uvízlo, čeká na člověka (stavová věta „Uvízlo“) |
| **čip profilu** | `Security` je zvýrazněný: karta má bezpečnostní pipeline (review + hacker kritik + test) |
| **„čeká na router“** | karta bez pipeline; router ji ještě nenasměroval |

Sloty dokladů jsou čtverečky (etapy jsou kuličky): prázdný = nedoloženo, poloviční = deklarováno bez dokladu
(agent napsal „prošlo“, ale odkaz ani běh kontroly nejsou), plný = doloženo, křížek = selhalo, čárkovaný =
nevztahuje se. Počítají se z `evidence`, `checksRun` a kontrol karty, ne z poznámek. Stavová věta je jedna
podle přednosti: Uzavřeno · Uvízlo · Čeká na tebe · Ke schválení (+ Potvrdit) · Blokuje · Pracuje · Na řadě ·
Čeká na router · K převzetí. Všechny podrobnosti (odkazy, běhy kontrol, kdo drží, z čeho vychází, pravidla,
zdroj, realizace) má vybraná karta v jednom foldu „Podrobnosti“ pod bloky; formulář důkazů pro člověka
zmizel, důkazy hlásí agent přes `agent-output.evidence`.

V oddálení zůstanou jen tečky a čtverečky, takže z dálky je vidět, kde proces běží, kde selhal, kde čeká na
člověka a co je doložené, aniž by se karta otevírala. Detail etap (zadání, poznámky, přeskočení) je v bloku
Pipeline vedle karty.

## 4. Jak tvořit detail karty

Detail karty je **jednotný drawer** (dvojklik na kartu, odznak etapy, Velín i OporaHub; záložky Zadání, Kroky, Běh,
Review & PR, Historie, viz [oporahub-ui.md](oporahub-ui.md#jednotný-detail-karty)) a **bloky na kartě**. Člověk ho zpravidla nevyplňuje (viz [pyramida.md](pyramida.md): píše záměr oblasti a potvrzuje
dávky); karty plní agent-rozkladač. Dvě cesty, jeden výsledek:

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
| záměr oblasti, rozmístění na plátně, kresba, schválení dávky | **Opora** | záměr píše člověk; rozmístění a kresba se dělají okem; dávku od agenta potvrzuje jedním rozhodnutím |
| rozklad oblasti na sektory, sektoru na karty (dávka `canvas-plan`) | terminál (agent-rozkladač) | strukturované založení oblastí, sektorů, karet a vazeb umí dávka s náhledem; viz [pyramida.md](pyramida.md) §3 |
| psaní zadání jedné karty, bloky, pravidla | Opora (inspektor) nebo asistent v okně | asistent zapisuje po schválení člověkem; výsledek je hned vidět |
| vykonání karty / etapy pipeline | **terminál v kořeni projektu** (`claude` + skill, nebo hook-řízená relace) | kód je v repu; agent musí vidět soubory, spustit testy, commitovat |
| router, kritici, review | terminál (jiná relace než autor) | nezávislost: server hlídá jméno relace |
| hromadné založení karet z plánu | terminál (`canvas-plan --dry-run` → ostře) | dávka s náhledem a digestem |
| potvrzení hotovo, svěření autonomie, brána sektoru, verze plátna | **jen Opora** (člověk) | agent dostane 403 |
| sledování, co se děje | Opora (plátno: kuličky, pás, obálky na vazbách, lišta „Práce teď“) | jeden pohled, žádné logy |

Praktické pravidlo: **myslí se a schvaluje v Opoře, vykonává se v terminálu.** Jeden terminál = jedna
karta (nebo jedna etapa). Více agentů = více terminálů na nepřekrývajících se cestách.

## 6. Paměť role (OpenViking) a co s ní

OpenViking běží (`/health` ok, v0.4.17.1). Backend potřebuje `OPORA_OPENVIKING_ADMIN_API_KEY`: od 2026-10-15 je
v lokálním `.env` (git-ignorovaný, `uv run opora` ho načte), takže po příštím restartu stačí provisioning.
Po provisioningu (`POST /api/memory/provision {"confirmed": true}`) agent v `node-brief.context.roleMemory`
dostane, co se jeho role naučila na podobných kartách, a při uzavření karty se jeho prostor zrcadlí
zpět. Co tam **nepatří**: zadání karty, kód, tajemství; paměť je popis zkušenosti, ne pravda o kódu.

## 7. Co dnes neplatí a je třeba to vědět (nálezy kritika, 2026-10-15)

- **Záloha:** „Verze plátna“ obnoví graf a stav karet, ne výsledky agentů, přílohy ani prostor agenta.
  Úplná záloha je kopie celé složky projektu v `P:\opora-data` v klidu (bez běžících agentů).
- **Atomicita výsledku:** `agent-output` zapisuje stav, etapy a evidenci pod jedním zámkem s CAS revizí;
  opakovaný stejný požadavek po 409 musí agent nejdřív znovu načíst stav. Idempotentní klíč výsledku není.
- **Pád agenta:** lease vyprší; další relace začíná předávkou (`handoff`) a rozpracovanými změnami v repu.
  Výsledek proti zastaralému `contextVersion` server odmítne a karta se neposune bez člověka.
- **Doručení kódu:** uzavření karty nekontroluje commit ani merge. Větev/worktree, commit s trailerem
  `Opora-Node` a `realize-source` jsou doporučení, ne brána. Souběžní agenti v jedné pracovní kopii si
  mohou šlapat do git indexu; drž je na nepřekrývajících se cestách nebo ve worktree.
- **Jedna předávka:** kanonická předávka etapy je `stages[].note`; `agent-workspace.handoff` a zprávy
  na vazbách na ni odkazují (`opora://agent-workspace/<nodeId>#handoff`). Chybí-li `note`, server etapu
  `passed`/`failed` odmítne.
- **Identita:** jméno relace je organizační značka, ne ověřená identita (`identityVerified: false`).
  Nezávislost kritika hlídá jen porovnání jmen.
- **Paměť role:** zrcadlí se prostor agenta; filtr tajemství a kódu je jen pravidlo pro agenta, ne
  mechanismus. Nedostupný OpenViking nic neblokuje, zrcadlení se jen nestane.

## 8. Co se během noční směny 2026-10-15 změnilo

- Kuličky procesu na kartě (§3), původně jen v bloku Pipeline; ráno sloty dokladů, stavová věta a jeden fold
  „Podrobnosti“ místo seznamu řádků (`docs/proces-karty.md`).
- Velké plátno: drafty bloků v úložišti → kreslí se jen viditelné karty, MiniMap do 500 uzlů, varování
  u stropu.
- Mapa projektu: serverový přehled komunit (`GET /api/graphify/overview`) a vlastní lehká mapa místo
  iframe s 1780 uzly; původní HTML jen na vyžádání.

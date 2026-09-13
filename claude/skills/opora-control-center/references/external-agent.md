# Externí agent: Opora → Git workspace → ticket

Použij jen pro výslovně schválenou práci mimo dokumentační/coding runtime Opory.
Export ani návštěva uzlu nespouští model. Externí agent nemá OPORA run ID.

## Převzetí

1. Přes `scripts/opora_read.py` ověř status, project/workspace a konkrétní node.
   `main` je read-only. Git workspace Opory může být jiná složka než původní repo
   otevřené ve VS Code; cestu zjisti GET `/api/workspace/tree?project=...&workspace=...`.
2. Načti uložené Zadání a pravidla. Chybí-li goal/non_goals/acceptance nebo
   konkrétní schválené soubory, implementace je **blocked**. Scope nedoplňuj odhadem.
3. Sestav náhled → vytvoř neměnný snímek → ověř jej zpětným GET.
   Musí souhlasit id, digest a project/workspace/nodeId. Nové snímky obsahují
   `packet.task.depends_on`: příchozí source → target, názvy a uložené fáze
   předchůdců. `status: null` znamená nedostupné; fáze není důkaz dokončení.
4. **Exportovat pro externího agenta** zapíše do vybraného Git workspace
   `docs/opora-control-center/tasks/<node-id>.md`. Nezapisuje do read-only mainu.
   I neúplné zadání lze exportovat, ale zůstává `Status: blocked`.
5. Export obsahuje Cíl, Mimo rozsah, Podmínky dokončení, kandidátní cestu,
   pravidla, depends_on, Snapshot ID/digest, TODO a Result. `sourceRef` ani
   kandidátní cesta nejsou samy souhlas s implementací. Ověř souhlas uživatele.
6. Před úpravou kódu ověř skutečný Git kořen, větev, stav a vlastnictví workspace.
   Pokud je ve workspace aktivní cizí práce, nepřepínej jeho větev. Vlastní
   izolovaná větev `opora/<node-id>` je vhodná jen v agentově vyhrazeném worktree;
   zapiš do Result její skutečnou identitu. Vazbu na workspace Opory neměň odhadem.
7. Agent čte toto zadání, CLAUDE.md a relevantní pravidla; postupuje podle TODO.
   `Status`: planned → in_progress → review/done, nebo blocked.
   Result obsahuje skutečnou větev/commit, změněné soubory, ověření a blokery.

## API exportu (bez modelu)

POST `/api/desktop-v3/packet/snapshots/<snapshot-id>/external-export`:

```json
{"project":"<ID>","workspace":"<ID>","nodeId":"<ID>","digest":"<digest snímku>"}
```

Hlavičky: Content-Type application/json a Origin shodný s lokálním Host.
Backend kontroluje neměnný snímek, současný digest, readOnly, Git workspace,
bezpečnou pevnou cílovou cestu a odmítá přepsat odlišný existující soubor.
Následuje GET stejného endpointu s project/workspace/nodeId/digest v query.
Porovnej scope, path, sha256 a obsah se zápisem. Zastaralý snímek → nový náhled,
ne přepis digestu. Existující Result nejprve zachovej; nemaž jej pro obejití 409.

## Zpět do canvasu: oficiální ticket, bez falešné session

Používá se existující revizované API paměti; žádný watcher souborů neběží.

1. GET `/api/desktop-v3/state?project=...&workspace=...`; uchovej celý state/revision.
   Ověř readOnly=false a existenci uzlu ve view.
2. Přidej ticket s novým UUID (nebo aktualizuj vlastní dříve ověřené ID):

```json
{
  "id":"<nové UUID>",
  "title":"[external:blocked] tasks/<node-id>.md — <stručný skutečný blocker>",
  "priority":"high",
  "status":"open",
  "nodeId":"<skutečné ID uzlu>",
  "sessionId":"",
  "createdBy":"agent"
}
```

3. Titulek nejvýše 400 znaků; dlouhý výsledek patří do Result v Markdownu.
   Označení `[external:<status>]` je konvence, **ne nově vymyšlené API pole**.
   in_progress → ticket doing; blocked → open/high; review nebo done → open/normal
   k ověření člověkem. Agentovo done není uzavření ticketu ani schválení live.
4. POST `/api/desktop-v3/state` s project, workspace, původní expectedRevision
   a celým zachovaným state. `nodes` a cizí tickety neměň. Při 409 žádný force:
   načti současný dokument a vyřeš konkrétní konflikt.
5. GET stejného scope; ověř ticket podle ID i přesného obsahu. V UI je viditelný
   v Live Run → Tickety bez filtru konkrétní session, případně pro vybraný uzel.
   Bezsessionový agentní ticket je označen „externí agent · neověřený výsledek“.
6. Člověk ověří Result, uzavře ticket a případně posune workflow fázi uzlu.
   Automatické obarvení/fáze podle agentova tvrzení není podporované ani důkaz.

## Hranice

- Coding sandbox zůstává `calculator.py`; externí export jej nerozšiřuje.
- Dokumentační handoff zapisuje pouze izolovaný result.md. Limit 10–180 s se
  nastavuje v Nastavení projektu, sdílí se s LLM návrhy a není cenový strop.
- Nečti .env ani tajemství; nikdy nepředávej reference jako oprávnění k celému repu.
- Nové chyby aplikace patří do projektového IMPROVEMENT.md, ne k tichému obejití.

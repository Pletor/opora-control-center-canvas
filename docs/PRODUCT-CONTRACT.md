# Opora Control Center Canvas — opravený produktový kontrakt

## Autorita a původ

Zadání Helmar: funkční Canvas nad schváleným GitHub repozitářem, přepnutí čistého mainu a pracovního prostoru s oddělenými worktrees/forky souběžných agentů na sektorech a uzlech; po merge do mainu synchronizace lokální kopie. Návrh sestaven přímo modelem Astra v Hermesu.

Zdroj schváleného původního Canvasu: `../wt-cc-platno/docs/superpowers/specs/2026-09-08-platno-design.md`, zejména účel, hierarchie, balíčky a UI. Novější `2026-09-09-platno-zrcadlo-design.md` navrhuje kopii bez .git; tuto techniku nelze převzít jako základ Git/worktree lifecycle.

Tento dokument opravuje směr; není důkazem dokončené aplikace. Předchozí `../OporaCC-v3` zůstává zachovaný jako nedokončený odlišný pokus (inventář/balíčky), nikoli výsledný Canvas. Žádná cizí worktree ani její rozpracované změny se nepřepisují.

## Účel

Vidíme celý systém, ale měníme vždy jeden přesně ohraničený uzel. Hlavní pracovní objekt je projekt → sektor → uzel, nikoli soubor. Soubor je podklad, vlastněná cesta nebo důkaz uzlu.

## Technologie

- React + TypeScript + React Flow (@xyflow/react), Vite: samostatně načítaný klient a plátno.
- Python + FastAPI: samostatný Git a projektový aplikační backend, mimo starý OporaCC composition root.
- SQLite: pouze registr schválených zdrojů, graf/rozvržení, vazby na autoritativní entity, joby a audit. Neukládat konkurenční lifecycle WorkUnitů či GitHub Project statusu.
- Git CLI: skutečná kopie repozitáře a pracovní stromy. Síťové a dlouhé Git operace mimo request/render, s omezením času, stavem a chybou.
- Žádný Bridge, GitHub dotaz ani sken celého disku v kritické cestě prvního vykreslení.

## Dva skutečně oddělené režimy

### Čistý main

Samostatná aplikací spravovaná kopie schváleného repozitáře, konkrétní potvrzené SHA výchozí schválené větve (ne slepý předpoklad názvu main). Žádná agentní editace tohoto checkoutu. UI ukazuje repo, větev, SHA, čas poslední synchronizace, její výsledek a případný rozdíl proti remote.

Aktualizace: fetch → ověření schváleného upstreamu a revize → fast-forward/bezpečná aktualizace pouze čisté spravované kopie. Nikdy reset nebo checkout v uživatelově rozpracované složce. Lokální konflikt/dirty = zastavit a zobrazit důvod, nic nezahazovat.

### Pracovní prostor

Každý aktivní WorkUnit má workspace_id, project_id, node_id, vlastní branch/worktree (nebo doložený fork), base SHA, povolené cesty, vazbu na agenta a důkazy. Jeden writer na pracovní strom. Souběžní agenti nemění stejný checkout.

Worktree na WorkUnit platí pro git projekt. Druh projektu volí režim v `frontend/shared/project-capabilities/logic/project-capabilities.ts`: git projekt má main jen ke čtení a pro uzel vlastní workspace (worktree), lokální projekt pracuje v originální složce jen ve workspace `draft` a Git pracovní prostory nevytváří.

Existence worktree nebo procesu neznamená běžícího agenta. Odpojené, prunable, nedostupné a neznámé stavy se ukazují zvlášť.

Přepnutí režimu je změna pohledu, nikoli git checkout. Plátno pracovního prostoru zobrazuje rozdíl oproti schválenému základu a konkrétní aktivní workspace; nebarví vše jako hotový main.

## Hierarchie a uzel

Projekt → sektor → uzel → případné poduzly. Rozkliknutí, drobečky, návrat do stejné vrstvy a viewportu. Boční panel: Podstata, Výkres/spec, Úkol/DoD, Soubory a role, Workspace/agent, Diff, Testy a důkazy, PR/merge, Balíček kontextu.

Graf uzlů je explicitní verzovaná data nebo schválený import, ne odhad ze jmen adresářů. Pokud zdroj uzlů chybí, UI to řekne; nesmí vydávat každou složku za architektonický sektor.

## GitHub a dokončení

Připojení znamená schválení konkrétního upstreamu, výchozí větve a spravované cílové složky. Privátní GitHub používá existující bezpečně nakonfigurovaný serverový Git/gh přístup, nikdy token ve frontendovém vstupu nebo logu.

WorkUnit → změny ve workspace → testy a scope gate → review/PR → autorizovaný merge → readback merged SHA → synchronizace čistého mainu → readback lokálního SHA → aktualizace plátna. Samotné tvrzení agenta COMPLETE ani zelená karta nejsou merge.

Merge a push nejsou povolené samotným založením projektu. Explicitní lidská brána nebo samostatně schválená merge politika. Conflicts, missing checks, stale base a scope violations jsou blockers, ne automaticky opravované další uzly.

## První ověřovací vertikála

1. Schválený skutečný GitHub upstream + izolovaná spravovaná kopie, zachovaná .git historie.
2. Plátno načtené z explicitního zdroje uzlů; při chybě zdroje funkční prázdný/error stav.
3. Přepnutí čistého mainu a dvou samostatných testovacích workspaces; žádné smíchání souborů nebo agentního stavu.
4. Pro izolovaný fixture repozitář změna jednoho uzlu, test, potvrzený merge a readback main SHA. Žádný testovací merge do uživatelova živého projektu.
5. Měřit skutečné načtení plátna a interakci, ne pouze rychlost HTML. Testovat i offline GitHub a nedostupnou pracovní složku.

## Dosud nerozhodnutý konkrétní vstup

Který GitHub upstream a zdroj grafu použít pro první reálný projekt. Lokálně byl nalezen upstream `https://github.com/Pletor/Tajemstvi-opory.git`; samotná existence remote není novým souhlasem s jeho klonováním, push nebo merge. OporaCC nemá při kontrole origin. Uživatelova hlavní složka Tajemstvi-opory je aktuálně na jiné větvi než main, nesmí být použita jako údajně čistý main.

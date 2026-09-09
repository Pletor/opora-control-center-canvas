# Mazání položek a odpojení projektu
STATUS: READY — Astra; aktuální uživatelská žádost o mazání vložených položek.

## Kontrakt
- Uzel/sektor: read-only náhled ukáže serverově vypočtené počty uzlů (včetně potomků) a všech dotčených hran. Potvrzení je svázané s projektem/workspace/target a digestem grafu. Bez confirmed=true, při změně revize nebo main se nic nesmaže.
- Vazba: jde vybrat a potvrzeně odstranit jen tuto vazbu.
- Před odstraněním grafových prvků uložit lokální recovery snapshot; selhání snapshotu blokuje odstranění. Snapshot není potvrzení provedení a při neúspěšné operaci může zůstat. Uložené NodeSpec revize a ostatní workspaces se nezahazují. Neuložené drafty smazaných uzlů se po úspěchu odstraní z klientské paměti.
- Repozitář: odpojit z aktivního seznamu OporaCC. Žádný GitHub delete, push, filesystem removal ani ztráta dirty worktree. Lokální kopie/metadata/spec historie zůstávají v archivech. Archivovaný projekt nepovolí další read/write/sync/workspace operace a jeho jobs se nezobrazují v aktivním bootstrapu.
- Preview repozitáře funguje i při chybějícím lokálním repo; potřebuje jen registry. Potvrzení digestem váže metadata a workspaces. Probíhající/queued jobs blokují odpojení. Job enqueue znovu ověří archive pod DB transakcí; v jedné instanci se odpojení serializuje vůči Git a graph operacím.
- UI jedno potvrzení s dopadem a tlačítkem Zrušit; cancel/GET nemutují. Chyba ponechá dialog s vysvětlením. Výsledek pro starší scope nesmí přepsat aktuální pohled.
- Uživatelská produkční data se při implementaci/testování nemažou. Fixture repo je samostatné, jiné testy neovlivní.

## Scope a oracle
backend/removals.py, backend/service.py, backend/app.py; src/App.tsx, Board.tsx, NodePanel.tsx, NodeSpecEditor.tsx, types.ts, RemovalDialog.tsx, style.css; tests/test_removals.py, tests/test_removal_history.py, e2e/removals.spec.ts, scripts/prepare_e2e.py. RED→GREEN, full pytest/build/UI, nezávislé review a skutečný read-only production smoke.

## Doplněný invariant
Obecný /api/graph nesmí obejít potvrzené mazání. Úbytek ID uzlu/hrany bez interního oprávnění z RemovalService je odmítnutý; přidávání a změny zůstávají kompatibilní.

## Non-goals
Žádné fyzické mazání repo adresářů, remote delete, obnovení archivů přes UI, hromadné mazání projektů, jiná rozšíření editoru. Historické dokumenty ani předchozí aplikace se nemažou.

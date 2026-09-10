# WU-SOURCE-CREATION — zadání z kontroly náhledu

## Cíl a UX
Uživatel schválil vzhled průběžného náhledu a požaduje při vytváření sektoru výběr klíčové složky z hlavního stromu projektu; při vytváření uzlu výběr podsložky/souboru. Nové části se nejdřív navrhují v sektoru a potom v jeho uzlech.

Dvě explicitní možnosti: **Navázat na existující zdroj** a **Navrhnout nové**. Existující navázání ukazuje konkrétní relativní cestu. Nový návrh je zřetelně označený; název a podstata se ukládají do návrhu, nikoli do zdrojového souboru. Zdrojový uzel patří pod sektor; výběr se omezuje na jeho větev. Původní volné poznámky/grafy zůstávají použitelné, neprovádí se zpětná migrace jejich významu.

## Data a bezpečnost
- Vazba/návrh je typovaná volitelná součást uzlu grafu, uložena s grafem v jednom zápisu a dostupná po reloadu.
- Skutečný projekt/workspace určuje server, nikoli podstrčená absolutní cesta klienta.
- Ověřit typ, relativní cestu, sektorovou příslušnost, existenci nového existujícího navázání, symlinky/junctiony; neměnit zdrojový filesystem.
- Návrh nic nespouští: žádný model, shell, mkdir, změna zdrojového souboru, commit nebo worktree.
- Zachovat staré uzly a rozpracovaná data; smazaný zdroj staré vazby nesmí blokovat nesouvisející přesun grafu.

## Důkazy a doručení
RED→GREEN persistence/scope, UI napojení sektor→soubor→reload, návrh sektor→uzel bez nových souborů, legacy regrese. Nezávislé review exact diff, build/lint/backend/UI výstupy. Náhled 8750 aktualizovat až po testech, zachovat jeho vlastní data; 8740 zůstává nedotčený.

## Izolace
Writer: `.worktrees/v2-source-creation`, branch `feat/source-backed-creation`, staged baseline tree `9e90e546a923d3d9883a476c29ad6d8c24212752`. Parent writer řeší jen integrační dokumentaci a následné ověření. Předchozí Live Run lane není součástí tohoto dílčího kroku.

# Kontrakt identity a logického členství (verze 1)

Jeden kontrakt pro Oporu a Agent Office (`docs/opora-identity.md` v `Pletor/agent-office`). Opora
vydává všechna ID; kancelář a Harness je jen čtou a nic neodhadují ze jména ani z polohy na plátně.

## Klíč

Uzel je `opora:<projectId>:<workspace>:<nodeId>`, každá část URI-kódovaná. Stejné `nodeId` v jiném
prostoru projektu je kopie karty, tedy jiný uzel. Klíč z jiného projektu nebo prostoru se odmítá
chybou, nikdy se tiše nepřemapuje.

## Úrovně

`global` › `project` (repozitář) › `page` › `layer` › `area` › `sector` › `task`. Každá úroveň pod
`global` je skutečné ID Opory.

- **Rodič** je `parentId`. `validate_graph` (`backend/canvas/graph.py`) odmítá cyklus, chybějícího
  rodiče a oblast či komentář jako rodiče. Sektor smí ležet pod kartou (stránka › vrstva › sektor)
  a jeho rodič se zachovává.
- **Oblast** rodičem není. Uzel nebo sektor do ní patří jen výslovně: pole `memberOf` = id oblasti
  se **stejným rodičem**. Ověřuje ho `validate_graph`; oblast musí být ve stejném grafu, tedy ve
  stejném projektu a prostoru. Geometrické `areaId` (`areas.area_of`, ve `specification.graph`)
  zůstává nápovědou plátna, ne členstvím.

## Zápis

- `/api/canvas-plan` nové uzly: `"memberOf": "<ref oblasti>"` nebo `"@id"`.
- `/api/canvas-plan` `extend`: `"memberOf": "@id oblasti"` zapíše, `null` zruší.
- `/api/graph`: pole uzlu `memberOf` (frontend ho při uložení přenáší beze změny).
- Grafové návrhy (`/api/oporahub/graph-proposals`) podporují stejné reference v nových
  uzlech. U existujících uzlů `updateNodes[].fields.memberOf` přijímá skutečné ID oblasti
  nebo `null` pro zrušení; oblast musí existovat v přijatém i pracovním grafu.
  Návrh sám graf nemění. Členství se projeví až po přijetí stávajícím lidským review tokem.
  Zrušení členství a odstranění oblasti lze navrhnout společně, atomicky.

Podpora grafových návrhů navazuje na původní implementaci Claude Code v Canvas PR #8;
kompatibilitu se současným protokolem doplnil Codex (OpenAI), model GPT-6.
Tato změna sama nezapojuje resolver Agent Office ani nemění geometrické nápovědy plátna.

## Přesun a zánik

- Přesun karty pod jiného rodiče, dokud má `memberOf` na oblast původního rodiče, se odmítne
  (409, „před přesunem karty nebo smazáním oblasti členství zrušte“).
- Smazání oblasti, která má výslovné členy mimo mazanou větev, odmítne už náhled odstranění
  (`/api/removal-preview`). Nejdřív se členství zruší, pak jde oblast smazat.

## Migrace a návrat

Členství je aditivní nepovinné pole: stávající grafy jsou platné beze změny a nic se automaticky
nedopočítává z polohy. Návrat = `areas.strip_area_membership(graph)`, který vrátí přesně graf
bez `memberOf`, platný i pro starší validaci.

## Verze

Verze kontraktu je 1 (`OPORA_IDENTITY_VERSION` v kanceláři). Změna, která čte ID jinak, zvyšuje
verzi na obou stranách, aby resolver (H02) a registr (H03) poznaly, na čem stojí.

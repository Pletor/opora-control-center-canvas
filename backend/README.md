Veškerá logika a řízení procesů. Strom kopíruje frontend: `project_setup/` → `project/` | `editor/`, pod nimi `canvas/` (základ plátna) a `integrations/` (platforma). Nad prostředími stojí `api/` (routery podle prostředí) a nad API `mcp/` (server pro agenty). Směr závislostí: mcp → api → prostředí → canvas, integrations; nižší vrstva nikdy neimportuje vyšší.

Každý balíček: moduly s logikou + `tests/` + README, jehož první věta říká, co balíček dělá a pro které prostředí pracuje. Plán a tabulka přesunů: STRUCTURE-PLAN.md.

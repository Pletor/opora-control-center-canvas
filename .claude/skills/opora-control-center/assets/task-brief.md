# Zadání karty: <název>

Šablona návrhu karty pro člověka před zápisem. Pole odpovídají tomu, co se zapíše (`/api/canvas-plan`
nebo `/api/graph` + `/api/node-spec`, viz [canvas-plan.md](../references/canvas-plan.md)). Proces karty (pipeline) určí router.

- Projekt / workspace: <z `<opora_context>`, `<projectId>` / `<workspace>`>
- Rodič: <ID sektoru nebo oblasti ověřené přes `view`, nebo kořen>
- Název: <`[task]` / `[research]` / `[grilling]` / `[prototype]` + název, do 160 znaků>
- Popis (`purpose`): <podstata karty>
- Cíl (`goal`): <co má po dokončení platit>
- Mimo rozsah (`non_goals`): <sousední karty, které to řeší, jménem>
- Hotovo když (`acceptance`): <ověřitelné body + příkazy testů projektu>
- Text karty: <doslovný výňatek zadání s názvem kapitoly>
- Bloky a porty: <blok → podmínka → porty s popiskem výsledku>
- Vazby: <odkud a kam, `next` / `block` / `flow`>
- Zdroj (`sourceRef`): <`existing` cesta ověřená v repu / `planned` cesta / žádný u konceptu>
- Pravidla: <`must` / `must_not` ze zadání>

Šablonu s placeholdery nezapisuj. ID ani digest si nevymýšlej; ber je z `view`.

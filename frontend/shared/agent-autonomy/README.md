Plná autonomie agentů v projektu (docs/plna-autonomie-agenta.md): jeden zdroj stavu, štítek a přepínač.

- `logic/agent-autonomy.ts` — tvar `AgentAutonomy {full, since?, by?}`, `readAutonomy(response)` (chybějící nebo cizí tvar = vypnuto), cesty API, `sinceLabel`, `autonomyTitle`. Test vedle.
- `logic/use-agent-autonomy.ts` — `useAgentAutonomy(project)`: čte `agentAutonomy` z `GET /api/project-settings`, `setFull(full)` ukládá hned přes `POST /api/project-settings/agent-autonomy` (lidský doklad `opora_ui` obstará `api`). Volá ho jen App.
- `components/AgentAutonomyBadge.tsx` — trvalý štítek „Plná autonomie agentů“ (hlavička projektu v TopBaru a na úvodní obrazovce, velín). Při vypnuté autonomii nic nekreslí.
- `components/AgentAutonomySwitch.tsx` — přepínač v Nastavení projektu (ProjectHome); zapnutí chce potvrzení, vypnutí je okamžité. Při zapnuté bráně mozku pod ním stojí „Autonomie projde bránou mozku“ (`autonomyPassesGate` přes `POST /api/brain/gate-setting`, `readGate`/`gateWriteBody`); bez něj zeď agenta odmítne 403 `gate_required` a agent-state mu akce nenabídne.
- `styles/agent-autonomy.css` — bloky `agent-autonomy-badge`, `agent-autonomy-switch`.

Přepínač je data projektu, ne vzhled aplikace; agent si ho nikdy nezapne sám (zápis smí jen člověk v UI).

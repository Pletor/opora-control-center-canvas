# Prostředí OporaHub

`OporaHubWorkspace` čte `useAgentState` a skládá rám, detail karty (`CardDetail`) a původní detaily (`DetailContent`). Přes `onDetailOpenChange` hlásí App otevřený detail; periodická čtení starších dílků (změny obsahu, formální podklady, sledování GitHubu, review návrhů) běží jen tehdy. Záložku „Živý proces“ (`hub/process-observatory`) skládá jen při otevřené záložce a předá jí snímek agent-state a jména karet. Přímý odkaz: `?environment=hub&ohView=agents` (nebo `ohView=process`) nebo `&ohCard=<nodeId>` (`logic/hub-link.ts`).

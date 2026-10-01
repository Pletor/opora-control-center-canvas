// Kategorie Hooky a commands: restart serveru po zásahu do backendu a to, co aplikace čte z Claude Code
// (backend/claude_code/README.md). Drop vytvoří akci v bloku Akce; id jsou uložená jako `pipelineId`.
import type { AgentItem } from "./agent-catalog";

export const hookItems: AgentItem[] = [
  {
    id: "hook-restart-backend",
    category: "hooks",
    label: "Restart backendu po změně",
    purpose: "uv run opora nenačítá změny Pythonu za běhu; po zásahu do backend/ se server restartuje, než se ověřuje chování.",
    kind: "action",
    relates: ["@pl-backend-endpoint-cas", "Port 8740 patří instanci uživatele; ověřuje se na vlastním portu."],
    invariants: [],
  },
  {
    id: "hook-claude-code-commands",
    category: "hooks",
    label: "Claude Code: commands, hooky a skills projektu",
    purpose: "backend/claude_code čte SKILL.md z .claude/skills projektu, uživatele a pluginů; aplikace je jen vypisuje a zapíná či vypíná.",
    kind: "action",
    relates: ["@rule-no-model-launch", "Vypnuté skills drží jeden JSON v datovém kořeni projektu."],
    invariants: [],
  },
];

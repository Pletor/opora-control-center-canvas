import { api } from "@/shared/types/logic/types";

/** Skill Claude Code, jak ho vidí backend v katalogu na tomto počítači. */
export type Skill = {
  id: string;
  name: string;
  description: string;
  /** project | user | plugin:<marketplace> */
  scope: string;
  path: string;
};

export type SkillsState = { skills: Skill[]; disabled: string[] };

export function loadSkills(): Promise<SkillsState> {
  return api<SkillsState>("/api/claude-code/skills");
}

export async function saveDisabledSkills(disabled: string[]): Promise<string[]> {
  const result = await api<{ disabled: string[] }>("/api/claude-code/skills/disabled", { disabled });
  return result.disabled;
}

export function scopeLabel(scope: string): string {
  if (scope === "project") return "Tento projekt";
  if (scope === "user") return "Uživatel";
  if (scope.startsWith("plugin:")) return "Plugin · " + scope.slice("plugin:".length);
  return scope;
}

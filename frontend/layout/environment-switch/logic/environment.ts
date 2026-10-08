// Tři prostředí aplikace a jejich čtení z URL bez Reactu. Přepínač je jen kreslí; App drží, které
// svítí, a zapisuje ho zpátky do URL jako `environment=<id>`.
import { readMode, type WorkspaceMode } from "@/shared/surface-settings/logic/workspace-settings";

export type Environment = "project" | "editor" | "hub";

export const ENVIRONMENTS: { id: Environment; label: string; hint: string; subtitle: string }[] = [
  { id: "project", label: "Projekt", hint: "Strom zdrojů, podstata, architektura a dokumentace · Alt+1", subtitle: "Aplikace a kód" },
  { id: "editor", label: "Editor", hint: "Plátno, bloky, deníky, kreslení a kontext · Alt+2", subtitle: "Stavba aplikace" },
  { id: "hub", label: "OporaHub", hint: "Plán a dokumentace 1:1 s kódem · Alt+3", subtitle: "Plán ↔ kód" },
];

/**
 * Prostředí z hodnoty URL. Staré odkazy na zrušený Live Run (`live`) otevřou OporaHub, který
 * zabral jeho místo na Alt+3; cokoli jiného neznámého vrátí null a rozhodne výchozí Editor.
 */
export function readEnvironment(value: string | null): Environment | null {
  if (value === "live") return "hub";
  return ENVIRONMENTS.some((item) => item.id === value) ? (value as Environment) : null;
}

/** Prostředí pro klávesu Alt+<číslo>; jiná klávesa nic. */
export function environmentForKey(key: string): Environment | null {
  return ENVIRONMENTS[Number(key) - 1]?.id ?? null;
}

/**
 * Úvodní mód a prostředí z URL. Čte `environment` i krátké `env`. Zrušený mód `agents` (Běhy)
 * spadne v `readMode` na Strukturu, takže starý odkaz `mode=agents` otevře Editor.
 */
export function resolveInitialModeEnvironment(params: URLSearchParams): { mode: WorkspaceMode; environment: Environment } {
  const environment = readEnvironment(params.get("environment") ?? params.get("env"));
  return { mode: readMode(params.get("mode")), environment: environment ?? "editor" };
}

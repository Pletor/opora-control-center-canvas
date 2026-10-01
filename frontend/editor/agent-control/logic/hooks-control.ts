export type HookState = "active" | "paused" | "stopped";

export type HookBinding = {
  id: string;
  project: string;
  workspace: string;
  nodeId: string;
  sessionId: string;
  revision: number;
  state: HookState;
  approvedTaskRevision: number;
  currentTaskRevision: number;
  acknowledgedRevision: number | null;
  allowedPaths: string[];
  maxToolCalls: number;
  maxFailures: number;
  toolCalls: number;
  consecutiveFailures: number;
  hookObserved: boolean;
  lastEvent: string | null;
  lastDecision: string | null;
  lastSeenAt: string | null;
  expiresAt: string;
  identityVerified: false;
  settingsPath: string;
  launchCommand: string;
};

export type HookEvent = {
  id: string;
  at: string;
  event: string;
  toolName: string | null;
  decision: string | null;
  reason: string | null;
  taskRevision: number;
};

export type Scope = { project: string; workspace: string; nodeId: string | null };

export function currentScope(project: string, workspace: string, nodeId: string | null): Scope {
  return { project, workspace, nodeId };
}

export function isFreshScope(expected: Scope, actual: Scope): boolean {
  return expected.project === actual.project && expected.workspace === actual.workspace && expected.nodeId === actual.nodeId;
}

/** A server binding is actionable only in the exact card scope that returned it. */
export function isBindingInScope(binding: Pick<HookBinding, "project" | "workspace" | "nodeId">, scope: Scope): boolean {
  return scope.nodeId !== null && binding.project === scope.project && binding.workspace === scope.workspace && binding.nodeId === scope.nodeId;
}

export function parseAllowedPaths(value: string): string[] {
  return [...new Set(value.split("\n").map((path) => path.trim()).filter(Boolean))];
}

export function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export function bindingAvailability(binding: Pick<HookBinding, "hookObserved" | "state">): string {
  if (binding.hookObserved) return binding.state === "paused" ? "Hook pozorován · pozastaven" : "Hook pozorován";
  return "Připraveno · hook zatím nebyl pozorován";
}

/** Read-only cards may still pause or request a stop for an already observed binding. */
export function canControlBinding(
  readOnly: boolean,
  binding: Pick<HookBinding, "hookObserved" | "state">,
  action: "pause" | "resume" | "stop",
): boolean {
  if (binding.state === "stopped") return false;
  return !readOnly || (binding.hookObserved && action !== "resume");
}

export function lspProviderLabel(status: "configured" | "unavailable"): string {
  return status === "configured" ? "nakonfigurováno" : "nedostupné";
}

/** React key of one panel part for one card. Each part needs its own prefix: siblings sharing a key are duplicated on every render. */
export function scopeKey(part: "form" | "lsp" | "semantic", scope: Scope): string {
  return `${part}:${scope.project}:${scope.workspace}:${scope.nodeId ?? ""}`;
}

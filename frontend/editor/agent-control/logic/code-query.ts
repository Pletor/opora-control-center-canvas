/** Adresa dotazu na kód: projekt, pracovní prostor a vybraná karta, ke které panel patří. */
export type Scope = { project: string; workspace: string; nodeId: string | null };

export function currentScope(project: string, workspace: string, nodeId: string | null): Scope {
  return { project, workspace, nodeId };
}

/** Pozdní odpověď se použije jen tehdy, když se mezitím nezměnil projekt, prostor ani karta. */
export function isFreshScope(expected: Scope, actual: Scope): boolean {
  return expected.project === actual.project && expected.workspace === actual.workspace && expected.nodeId === actual.nodeId;
}

export function lspProviderLabel(status: "configured" | "unavailable"): string {
  return status === "configured" ? "nakonfigurováno" : "nedostupné";
}

/** React key of one panel part for one card. Each part needs its own prefix: siblings sharing a key are duplicated on every render. */
export function scopeKey(part: "form" | "lsp" | "semantic", scope: Scope): string {
  return `${part}:${scope.project}:${scope.workspace}:${scope.nodeId ?? ""}`;
}

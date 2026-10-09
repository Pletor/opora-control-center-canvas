import { api } from "@/shared/types/logic/types";
import type { HookBinding, HookEvent } from "./hooks-control";

export type CodeScope = { project: string; workspace: string };
export type LspStatus = {
  providers: { language: "typescript" | "python"; status: "configured" | "unavailable"; detail: string }[];
  semantic: { status: "configured" | "unavailable"; reason: string };
  preference: string[];
};
export type LspQueryInput = CodeScope & {
  language: "typescript" | "python";
  path: string;
  operation: "definition" | "references" | "hover" | "documentSymbols";
  line: number;
  character: number;
};
export type LspQueryResponse = {
  status: "ok" | "empty" | "unavailable";
  language: "typescript" | "python";
  operation: string;
  results: unknown[];
  detail: string;
};

export const fetchLspStatus = (scope: CodeScope) =>
  api<LspStatus>(`/api/code-intelligence/status?${new URLSearchParams(scope).toString()}`);
export const queryLsp = (input: LspQueryInput) => api<LspQueryResponse>("/api/code-intelligence/query", input);

/* Hook control: bind, control a instalace do VS Code jsou jen pro člověka (server vrací agentovi 403,
   bez lidské session UI 428); sdílené `api()` lidskou session doplní a 428 zopakuje. */
export type HookScope = { project: string; workspace: string; nodeId: string };
export type HookBindingsResponse = { bindings: HookBinding[]; readOnly: boolean; taskRevision: number };
export type BindInput = HookScope & {
  sessionId: string;
  allowedPaths: string[];
  maxToolCalls: number;
  maxFailures: number;
  ttlSeconds: number;
  allowTextSearch: boolean;
  confirmed: true;
};
export type BindResponse = { binding: HookBinding; settingsPath: string; launchCommand: string };
export type VscodeInstallState = {
  bindingId: string;
  sessionId: string;
  project: string;
  workspace: string;
  nodeId: string;
  installed: boolean;
  settingsPath: string;
  settingsDigest: string | null;
  canInstall: boolean;
  detail: string;
  backupCreated?: boolean;
};

export const fetchBindings = (scope: HookScope) => api<HookBindingsResponse>(`/api/agent-hooks?${new URLSearchParams(scope).toString()}`);
export const bindHook = (input: BindInput) => api<BindResponse>("/api/agent-hooks/bind", input);
export const controlHook = (bindingId: string, expectedRevision: number, action: "pause" | "resume" | "stop") =>
  api<{ binding: HookBinding }>("/api/agent-hooks/control", { bindingId, expectedRevision, action, confirmed: true });
export const fetchEvents = (bindingId: string) =>
  api<{ events: HookEvent[]; truncated: boolean }>(`/api/agent-hooks/events?bindingId=${encodeURIComponent(bindingId)}`);
export const fetchVscodeInstall = (bindingId: string) =>
  api<VscodeInstallState>(`/api/agent-hooks/vscode?bindingId=${encodeURIComponent(bindingId)}`);
export const updateVscodeInstall = (
  bindingId: string,
  expectedBindingRevision: number,
  expectedSettingsDigest: string | null,
  action: "install" | "remove",
) => api<VscodeInstallState>("/api/agent-hooks/vscode", {
  bindingId,
  expectedBindingRevision,
  expectedSettingsDigest,
  action,
  confirmed: true,
});

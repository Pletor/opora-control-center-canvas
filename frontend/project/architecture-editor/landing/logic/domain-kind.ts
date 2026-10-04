import type { CanvasNode } from "@/shared/types/logic/types";

export type DomainKind = "web" | "app" | "admin";

export const DOMAIN_KIND_LABEL: Record<DomainKind, string> = { web: "Web", app: "Aplikace", admin: "Administrace" };

/** Kind of a domain read from the first label of its host: `app.` is the application, `admin*` the administration, anything else a web. */
export function domainKind(host: string): DomainKind {
  const first = host.trim().toLowerCase().split(".")[0];
  if (first.startsWith("admin")) return "admin";
  if (first === "app") return "app";
  return "web";
}

/** Kind of a domain node: from the host of its first environment, otherwise from the node name (a shared domain is named by its host). */
export function domainKindOf(node: CanvasNode): DomainKind {
  const host = node.site?.kind === "application" ? node.site.environments.find((env) => env.host.trim())?.host : undefined;
  return domainKind(host ?? node.name);
}

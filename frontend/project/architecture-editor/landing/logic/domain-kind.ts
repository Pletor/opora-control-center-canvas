import type { CanvasNode, SiteEnvironment } from "@/shared/types/logic/types";

export type DomainKind = "web" | "app" | "admin" | "android" | "ios";

export const DOMAIN_KIND_LABEL: Record<DomainKind, string> = {
  web: "Web", app: "Aplikace", admin: "Administrace", android: "Aplikace Android", ios: "Aplikace iOS",
};

/** Kind of a domain read from the first label of its host: `app.` is the application, `admin*` the administration, anything else a web. */
export function domainKind(host: string): DomainKind {
  const first = host.trim().toLowerCase().split(".")[0];
  if (first.startsWith("admin")) return "admin";
  if (first === "app") return "app";
  return "web";
}

/** Mobile application (Android, iOS): no host, its environments carry a bundle ID and it has no web status. */
export function isMobileDomain(node: Pick<CanvasNode, "site">): boolean {
  return node.site?.kind === "application" && (node.site.platform === "android" || node.site.platform === "ios");
}

/** What identifies an environment for a human: the host of a web, the bundle ID of a mobile application. */
export function environmentAddress(env: SiteEnvironment | null | undefined): string {
  return env?.host || env?.bundleId || "";
}

/** Kind of a domain node: its platform first (Android, iOS), then the host of its first environment, otherwise the node name
 *  (a shared domain is named by its host). */
export function domainKindOf(node: CanvasNode): DomainKind {
  if (node.site?.kind === "application" && (node.site.platform === "android" || node.site.platform === "ios")) return node.site.platform;
  const host = node.site?.kind === "application" ? node.site.environments.find((env) => env.host?.trim())?.host : undefined;
  return domainKind(host ?? node.name);
}

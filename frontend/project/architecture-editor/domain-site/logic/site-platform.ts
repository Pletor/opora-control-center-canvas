// Platforma domény ve formuláři: web má v prostředí host, mobilní aplikace (Android, iOS) místo něj bundle ID.
// Kontrakt je v backend/canvas/site_metadata.py (`platform`, `bundleId`). Bez Reactu, test vedle.
import type { ApplicationSite, SiteEnvironment, SitePlatform } from "@/shared/types/logic/types";

export const PLATFORM_CHOICES: { value: SitePlatform; label: string }[] = [
  { value: "web", label: "Web" }, { value: "android", label: "Aplikace Android" }, { value: "ios", label: "Aplikace iOS" },
];

export const isMobilePlatform = (platform: SitePlatform | undefined) => platform === "android" || platform === "ios";

/** Adresa prostředí, kterou formulář edituje: host u webu, bundle ID u mobilní aplikace. */
export function addressValue(site: ApplicationSite, env: SiteEnvironment): string {
  return (isMobilePlatform(site.platform) ? env.bundleId : env.host) ?? "";
}

/** Nová adresa prostředí; mobilní aplikace host nemá, web nemá bundle ID. */
export function withAddress(site: ApplicationSite, index: number, value: string): ApplicationSite {
  const key = isMobilePlatform(site.platform) ? "bundleId" : "host";
  return { ...site, environments: site.environments.map((env, i) => i === index ? { name: env.name, [key]: value } : env) };
}

/** Přepnutí platformy: prostředí si nechá název, adresa se přesune do pole platformy (host není bundle ID, proto prázdná).
 *  Web se ukládá bez pole `platform`; mobilní aplikace ztrácí `healthPath`, protože nemá web, na který se ptát. */
export function withPlatform(site: ApplicationSite, platform: SitePlatform): ApplicationSite {
  const mobile = isMobilePlatform(platform);
  const { platform: _old, healthPath, ...rest } = site;
  return {
    ...rest,
    ...(platform !== "web" ? { platform } : {}),
    ...(!mobile && healthPath !== undefined ? { healthPath } : {}),
    environments: site.environments.map((env) => mobile ? { name: env.name, bundleId: env.bundleId ?? "" } : { name: env.name, host: env.host ?? "" }),
  };
}

/** Hodnota k uložení: oříznutý název a jen adresa, kterou platforma používá. */
export function applicationSiteForSave(site: ApplicationSite): ApplicationSite {
  const key = isMobilePlatform(site.platform) ? "bundleId" : "host";
  return { ...site, environments: site.environments.map((env) => ({ name: env.name.trim(), [key]: (env[key] ?? "").trim() })) };
}

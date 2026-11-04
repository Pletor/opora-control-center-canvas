// Složky knihovny pláten toku v panelu Komponenty (kontrakt docs/navrhy/2026-11-04-knihovna-platna-toku.md §4,
// rozhodnutí člověka: jedna úroveň složek a štítky). Složka v K1 štítky jako pole nemá, proto štítek je `#slovo`
// v jejím popisu; „+ Složka“ je tam zapíše. Bez Reactu, test vedle.
import type { LibraryFlowSummary, LibraryFolder } from "@/project/library-canvas/logic/library-api";
import { plural } from "./component-shelf";

export function folderTags(description: string): string[] {
  return [...new Set([...description.matchAll(/(?:^|\s)#([\p{L}\d-]+)/gu)].map((match) => match[1].toLowerCase()))];
}

/** Štítky z pole „štítky“ formuláře (čárky nebo mezery, s `#` i bez) jako popis složky. */
export function tagsDescription(input: string): string {
  return [...new Set(input.split(/[\s,]+/).map((tag) => tag.replace(/^#/, "").trim().toLowerCase()).filter(Boolean))].map((tag) => "#" + tag).join(" ");
}

export const flowCount = (folder: LibraryFolder) => plural(folder.flows.length, "plátno", "plátna", "pláten");

/** Plátno agenta ověřené v projektu (`learnedFrom.result == "verified"`) je navržené k povýšení do knihovny člověka. */
export const promotionSuggested = (flow: LibraryFlowSummary) =>
  flow.ownerRef.startsWith("opora:library:agent:") && flow.learnedFrom?.result === "verified";

/** Řádek karty plátna: aktivní verze a kolik prvků z plátna vychází. */
export function flowFacts(flow: LibraryFlowSummary): string {
  const version = flow.activeN ? `aktivní v${flow.activeN}` : "bez aktivní verze";
  return flow.derivedCount ? `${version} · ${plural(flow.derivedCount, "odvozený", "odvozené", "odvozených")}` : version;
}

// Hledání v design systému (kontrakt Správy webu §3, řádek Search): tokeny, typografické styly, komponenty a assety
// rozepsaného dokumentu. Výsledek nese sekci, kam přepnout, a `target`, tedy `data-testid` řádku, který dílek té
// sekce už vykresluje (`color-token-…`, `scale-…`, `type-style-…`, `ds-component-…`, `ds-asset-…`).
import type { Design, ScaleKind } from "@/project/site-admin/logic/site-document";
import type { SiteSection } from "@/project/site-admin/site-menu/logic/site-sections";

export type SearchHit = { section: SiteSection; kind: string; label: string; detail: string; target: string };
export const MAX_HITS = 30;
const SCALES: [ScaleKind, string][] = [["spacing", "Spacing"], ["radius", "Corner radius"], ["shadow", "Shadow"]];

const text = (value: unknown) => typeof value === "string" ? value : value && typeof value === "object" ? Object.values(value).join(" ") : String(value ?? "");

export function searchDesign(design: Design, query: string): SearchHit[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  const hits: SearchHit[] = [];
  const add = (hit: SearchHit, ...fields: unknown[]) => {
    if (hits.length < MAX_HITS && fields.some((field) => text(field).toLowerCase().includes(needle))) hits.push(hit);
  };
  const tokens = design.tokens;
  for (const token of tokens.color.tokens)
    add({ section: "colors", kind: "Color", label: token.name, detail: text(token.value), target: "color-token-" + token.name }, token.name, token.usage, token.value);
  for (const [kind, label] of SCALES)
    for (const token of tokens[kind]?.tokens ?? [])
      add({ section: kind, kind: label, label: token.name, detail: text(token.value), target: `scale-${kind}-${token.name}` }, token.name, token.usage, token.value);
  for (const group of tokens.type.groups)
    for (const style of group.styles)
      add({ section: "typography", kind: "Type", label: style.name, detail: `${group.name} · ${style.fontSize}`, target: "type-style-" + style.name }, style.name, style.usage, style.sample, group.name);
  for (const component of design.components)
    add({ section: "components", kind: "Component", label: component.name, detail: component.group ?? "", target: "ds-component-" + component.name }, component.name, component.group, component.summary);
  for (const group of design.assetGroups) {
    add({ section: "assets", kind: "Asset set", label: group.name, detail: `${group.files.length} souborů`, target: "ds-asset-group-" + group.name }, group.name, group.readme);
    for (const file of group.files)
      add({ section: "assets", kind: "Asset", label: file.name, detail: group.name, target: `ds-asset-${group.name}-${file.name}` }, file.name);
  }
  return hits;
}

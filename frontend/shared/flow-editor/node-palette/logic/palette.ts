// Paleta uzlů: kategorie z registru typů (ne z pevného seznamu), hledání ve jménu a v kindech portů a předfiltr na
// port, ze kterého člověk kliknul na „+“ (n8n to dělá u sub-portů). Zobecněno z katalogu Studia MODEL (`paletteGroups`).
import { compatiblePort } from "../../logic/connection-policy";
import type { NodeTypeSpec, PortSpec } from "../../logic/flow-types";
import { matchesWords, searchWords } from "./palette-search";
import { KIND_LABEL, nodeGlyph, nodeRole, typeLabel } from "../../logic/node-role";

export const PALETTE_DRAG_TYPE = "application/x-opora-flow-type";
export type PaletteItem = { type: string; name: string; family: string; glyph: string; summary: string };
export type PaletteGroup = { id: string; label: string; items: PaletteItem[] };
export type PortFilter = Pick<PortSpec, "kind" | "direction">;

function category(spec: NodeTypeSpec): { id: string; label: string } {
  const role = nodeRole(spec);
  if (role === "trigger") return { id: "trigger", label: "Spouštěče" };
  if (role === "agent") return { id: "agent", label: "Agent" };
  if (role === "sub") return { id: `sub-${spec.ports[0].kind}`, label: `Sub-uzel · ${KIND_LABEL[spec.ports[0].kind]}` };
  if (spec.ports.some((p) => p.direction === "out" && ["approved", "rejected"].includes(p.name))) return { id: "approval", label: "Schválení" };
  return { id: "flow", label: "Tok" };
}
const ORDER = ["trigger", "agent", "flow", "approval"];
const rank = (id: string) => ORDER.includes(id) ? ORDER.indexOf(id) : ORDER.length;

function summary(spec: NodeTypeSpec): string {
  const ins = spec.ports.filter((p) => p.direction === "in").map((p) => p.kind === "main" ? p.name : KIND_LABEL[p.kind]);
  const outs = spec.ports.filter((p) => p.direction === "out").map((p) => p.kind === "main" ? p.name : KIND_LABEL[p.kind]);
  return `${ins.length ? ins.join(", ") : "—"} → ${outs.length ? outs.join(", ") : "—"}`;
}

export function paletteGroups(types: readonly NodeTypeSpec[], query = "", port: PortFilter | null = null): PaletteGroup[] {
  const words = searchWords(query);
  const hay = (spec: NodeTypeSpec) => [spec.type, ...spec.ports.flatMap((p) => [p.name, p.kind, KIND_LABEL[p.kind]])].join(" ");
  const shown = types.filter((spec) => matchesWords(hay(spec), words) && (!port || compatiblePort(spec, port)));
  const groups = new Map<string, PaletteGroup>();
  for (const spec of shown) {
    const { id, label } = category(spec);
    const group = groups.get(id) ?? { id, label, items: [] };
    const { family, name } = typeLabel(spec.type);
    group.items.push({ type: spec.type, name, family, glyph: nodeGlyph(spec), summary: summary(spec) });
    groups.set(id, group);
  }
  return [...groups.values()].sort((a, b) => rank(a.id) - rank(b.id) || a.id.localeCompare(b.id));
}

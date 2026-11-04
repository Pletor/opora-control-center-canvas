// Paleta uzlů: kategorie z registru typů (ne z pevného seznamu), hledání ve jménu a v kindech portů a předfiltr na
// port, ze kterého člověk kliknul na „+“ (n8n to dělá u sub-portů). Zobecněno z katalogu Studia MODEL (`paletteGroups`).
// Typ s `category` (katalog toků dat) jde do kategorie n8n: Spouštěče, AI (Agent a řetězce, pod nimi podle výstupního
// sub-portu Modely, Paměť, Nástroje …), Akce ve službě, Transformace dat, Tok, Lidská kontrola. Předfiltr na port bere
// v úvahu i varianty typu (vektorové úložiště jako nástroj).
import type { NodeTypeSpec, PortSpec } from "../../logic/flow-types";
import { variantFor } from "../../logic/graph-edit";
import { matchesWords, searchWords } from "./palette-search";
import { LAYER_LABEL } from "../../flow-lanes/logic/layers";
import { KIND_LABEL, nodeGlyph, nodeRole, typeLabel } from "../../logic/node-role";

export const PALETTE_DRAG_TYPE = "application/x-opora-flow-type";
/** `use` / `avoid`: „kdy použít / nepoužít“ z registru, v paletě tooltip. */
export type PaletteItem = { type: string; name: string; family: string; glyph: string; summary: string; use?: string; avoid?: string };
export type PaletteGroup = { id: string; label: string; items: PaletteItem[] };
export type PortFilter = Pick<PortSpec, "kind" | "direction">;

const FLOW_CATEGORY: Record<string, string> = { trigger: "Spouštěče", ai: "AI", action: "Akce ve službě", transform: "Transformace dat", flow: "Tok", core: "Jádro", human: "Lidská kontrola" };
const AI_SUB: Partial<Record<PortSpec["kind"], string>> = { model: "Modely", memory: "Paměť", tool: "Nástroje", vectorStore: "Vektorová úložiště", embedding: "Embeddingy",
  document: "Načítače", textSplitter: "Děliče textu", outputParser: "Výstupní parsery", retriever: "Retrievery" };
const FLOW_ORDER = ["layer-fe", "layer-be", "layer-db", "layer-infra", "trigger", "ai", "ai-model", "ai-memory", "ai-tool", "ai-vectorStore", "ai-embedding", "ai-document", "ai-textSplitter", "ai-outputParser", "ai-retriever", "ai-other", "action", "transform", "flow", "core", "human"];

/** AI uzel bez `main` (nebo s variantou bez `main`) patří do podkategorie podle svého výstupního sub-portu. */
function aiCategory(spec: NodeTypeSpec): { id: string; label: string } {
  const out = [spec.ports, ...(spec.variants ?? []).map((variant) => variant.ports)]
    .map((ports) => ports.find((p) => p.direction === "out" && p.kind !== "main")).find(Boolean);
  if (!out) return { id: "ai", label: "AI · Agent a řetězce" };
  return AI_SUB[out.kind] ? { id: `ai-${out.kind}`, label: `AI · ${AI_SUB[out.kind]}` } : { id: "ai-other", label: "AI · Ostatní" };
}

function category(spec: NodeTypeSpec): { id: string; label: string } {
  if (spec.layer && !["ai", "neutral"].includes(spec.layer)) return { id: `layer-${spec.layer}`, label: `${spec.layer.toUpperCase()} · ${LAYER_LABEL[spec.layer]}` };
  if (spec.category === "ai") return aiCategory(spec);
  if (spec.category) return { id: spec.category, label: FLOW_CATEGORY[spec.category] ?? spec.category };
  const role = nodeRole(spec);
  if (role === "trigger") return { id: "trigger", label: "Spouštěče" };
  if (role === "agent") return { id: "agent", label: "Agent" };
  if (role === "sub") { const kind = spec.ports.find((p) => p.direction === "out")!.kind; return { id: `sub-${kind}`, label: `Sub-uzel · ${KIND_LABEL[kind]}` }; }
  if (spec.ports.some((p) => p.direction === "out" && ["approved", "rejected"].includes(p.name))) return { id: "approval", label: "Schválení" };
  return { id: "flow", label: "Tok" };
}
const ORDER = ["trigger", "agent", "flow", "approval"];
const rank = (id: string, order: readonly string[]) => order.includes(id) ? order.indexOf(id) : order.length;

function summary(ports: readonly PortSpec[]): string {
  const ins = ports.filter((p) => p.direction === "in").map((p) => p.kind === "main" ? p.name : KIND_LABEL[p.kind]);
  const outs = ports.filter((p) => p.direction === "out").map((p) => p.kind === "main" ? p.name : KIND_LABEL[p.kind]);
  return `${ins.length ? ins.join(", ") : "—"} → ${outs.length ? outs.join(", ") : "—"}`;
}

export function paletteGroups(types: readonly NodeTypeSpec[], query = "", port: PortFilter | null = null): PaletteGroup[] {
  const words = searchWords(query);
  const hay = (spec: NodeTypeSpec) => [spec.type, ...spec.ports.flatMap((p) => [p.name, p.kind, KIND_LABEL[p.kind]])].join(" ");
  const shown = types.filter((spec) => matchesWords(hay(spec), words) && (!port || variantFor(spec, port)));
  const groups = new Map<string, PaletteGroup>();
  for (const spec of shown) {
    const { id, label } = category(spec);
    const group = groups.get(id) ?? { id, label, items: [] };
    const { family, name } = typeLabel(spec.type);
    group.items.push({ type: spec.type, name, family, glyph: nodeGlyph(spec), summary: summary((port && variantFor(spec, port)?.ports) || spec.ports),
      ...(spec.use ? { use: spec.use } : {}), ...(spec.avoid ? { avoid: spec.avoid } : {}) });
    groups.set(id, group);
  }
  const order = types.some((spec) => spec.category) ? FLOW_ORDER : ORDER;
  return [...groups.values()].sort((a, b) => rank(a.id, order) - rank(b.id, order) || a.id.localeCompare(b.id));
}

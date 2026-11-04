// Role uzlu a rozložení jeho portů jen z registru typů (žádný seznam jmen typů v kódu editoru):
// spouštěč nemá vstup, agent má sub-vstupy (model, paměť, nástroj, subagent) jako kosočtverce na spodní hraně,
// sub-uzel je kruh bez portu `main`, který má výstup jiného kindu (načítač dokumentů smí mít i vlastní sub-vstup,
// třeba dělič textu), a ostatní uzly jsou čtverce hlavního toku.
import type { NodeTypeSpec, PortKind, PortSpec } from "./flow-types";

export type NodeRole = "trigger" | "agent" | "sub" | "main";
export type PortSide = "left" | "right" | "bottom" | "top";
export type PortPlace = PortSpec & { side: PortSide; label: string; required: boolean; offset: number };

/** Povinné sub-porty (jako „Chat Model *“ v n8n): agent bez modelu neběží. */
export const REQUIRED_KINDS: readonly PortKind[] = ["model"];
export const KIND_LABEL: Record<PortKind, string> = { main: "tok", model: "Model", memory: "Paměť", tool: "Nástroj", subagent: "Subagent", approval: "Schválení", data: "Data",
  outputParser: "Výstupní parser", embedding: "Embedding", document: "Dokument", textSplitter: "Dělič textu", retriever: "Retriever", vectorStore: "Vektorové úložiště", reranker: "Reranker" };

/** Povinný port: tak ho označí registr, jinak sub-vstup povinného kindu (model). */
export const isRequired = (port: PortSpec) => port.direction === "in" && (!!port.required || REQUIRED_KINDS.includes(port.kind));
/** Popisek sub-portu: vlastní z registru (liší-li se od jména), jinak český název kindu. */
export const portLabel = (port: PortSpec) => port.label && port.label !== port.name ? port.label : KIND_LABEL[port.kind] ?? port.name;

export function nodeRole(spec: NodeTypeSpec | undefined): NodeRole {
  if (!spec) return "main";
  if (spec.trigger) return "trigger";
  if (spec.ports.length > 0 && spec.ports.every((p) => p.kind !== "main") && spec.ports.some((p) => p.direction === "out")) return "sub";
  if (spec.ports.some((p) => p.direction === "in" && p.kind !== "main")) return "agent";
  return "main";
}

function sideOf(port: PortSpec): PortSide {
  if (port.kind === "main") return port.direction === "in" ? "left" : "right";
  return port.direction === "in" ? "bottom" : "top";
}

/** Porty s polohou: na každé straně rovnoměrně (offset 0–1); jediný `main` výstup nemá popisek, pojmenované ano. */
export function portPlaces(spec: NodeTypeSpec | undefined): PortPlace[] {
  const ports = spec?.ports ?? [];
  const bySide = new Map<PortSide, PortSpec[]>();
  for (const port of ports) bySide.set(sideOf(port), [...(bySide.get(sideOf(port)) ?? []), port]);
  return ports.map((port) => {
    const side = sideOf(port), row = bySide.get(side)!, index = row.indexOf(port);
    const required = isRequired(port);
    const label = port.kind === "main" ? (row.length > 1 || port.name !== "main" ? port.name : "") : portLabel(port);
    return { ...port, side, label, required, offset: (index + 1) / (row.length + 1) };
  });
}

const GLYPH: Record<NodeRole, string> = { trigger: "↯", agent: "✳", sub: "●", main: "▸" };
const SUB_GLYPH: Partial<Record<PortKind, string>> = { model: "M", memory: "P", tool: "T", subagent: "S", embedding: "E", document: "D", textSplitter: "✂",
  outputParser: "{}", retriever: "R", vectorStore: "V", reranker: "≡" };

export function nodeGlyph(spec: NodeTypeSpec | undefined): string {
  const role = nodeRole(spec);
  if (role === "sub") return SUB_GLYPH[spec!.ports.find((p) => p.direction === "out")!.kind] ?? GLYPH.sub;
  if (spec?.ports.some((p) => p.direction === "out" && ["approved", "rejected"].includes(p.name))) return "?";
  return GLYPH[role];
}

/** Čitelný název typu: `trigger.heart_event` → „heart event“, rodina zvlášť jako podtitul. */
export function typeLabel(type: string): { family: string; name: string } {
  const [family, ...rest] = type.split(".");
  return { family, name: (rest.join(".") || family).replace(/_/g, " ") };
}

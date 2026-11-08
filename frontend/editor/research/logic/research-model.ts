import { isDrawingImageType, type DrawingFile } from "@/editor/canvas/drawing/logic/drawing-files";
import type { ResearchEdge, ResearchHeader, Verification } from "./research-types";
export const KIND_LABELS = { question: "Otázka", finding: "Zjištění", visual: "Vizuální rozbor", option: "Varianta", decision: "Rozhodnutí" };
export const RELATION_LABELS: Record<ResearchEdge["relation"], string> = { supports: "dokládá", contradicts: "odporuje", elaborates: "rozpracovává", option_for: "varianta pro", supersedes: "nahrazuje", resolves: "řeší", continues_to: "pokračuje do" };
export const VERIFICATION_LABELS: Record<Verification["status"], string> = { unverified: "Neověřeno", verified: "Ověřeno", observed: "Pozorováno", false: "Vyvráceno", unreachable: "Nedostupný zdroj", inference: "Odvozený závěr", conflict: "Rozpor" };
export const topicLabel = (path: string[]) => path.join(" / ");
export function filterResearch(cards: ResearchHeader[], query: string, topic: string, platform: string) {
  const needle = query.trim().toLocaleLowerCase("cs");
  return cards.filter(card => (!topic || JSON.stringify(card.topicPath) === topic) && (!platform || card.platforms.includes(platform)) &&
    (!needle || [card.id, card.title, card.summary, ...card.topicPath, ...card.refs.questionIds, ...card.refs.ticketIds].join(" ").toLocaleLowerCase("cs").includes(needle)));
}
/** A filtered view is laid out from its own graph; hidden findings reserve no rows or depths. */
export function researchLayout(cards: ResearchHeader[], edges: ResearchEdge[], query: string, topic: string, platform: string) {
  const visible = filterResearch(cards, query, topic, platform);
  const ids = new Set(visible.map(card => card.id));
  const links = edges.filter(edge => ids.has(edge.fromId) && ids.has(edge.toId));
  return { cards: visible, edges: links, positions: researchPositions(visible, links) };
}
/** Deterministic lanes by topic; directed depth handles branching, cycles remain in their lane. */
export function researchPositions(cards: ResearchHeader[], edges: ResearchEdge[]) {
  const ids = new Set(cards.map(card => card.id));
  const incoming = new Map(cards.map(card => [card.id, 0]));
  const next = new Map(cards.map(card => [card.id, [] as string[]]));
  for (const edge of edges) if (!edge.archived && ids.has(edge.fromId) && ids.has(edge.toId)) {
    incoming.set(edge.toId, incoming.get(edge.toId)! + 1); next.get(edge.fromId)!.push(edge.toId);
  }
  const depth = new Map(cards.map(card => [card.id, 0]));
  const queue = cards.filter(card => incoming.get(card.id) === 0).map(card => card.id);
  for (let i = 0; i < queue.length; i++) for (const target of next.get(queue[i])!) {
    depth.set(target, Math.max(depth.get(target)!, depth.get(queue[i])! + 1));
    incoming.set(target, incoming.get(target)! - 1); if (!incoming.get(target)) queue.push(target);
  }
  const ordered = [...cards].sort((a,b) => topicLabel(a.topicPath).localeCompare(topicLabel(b.topicPath), "cs") || a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id));
  const rows = new Map<number, number>();
  return new Map(ordered.map(card => { const column = depth.get(card.id)!; const row = rows.get(column) ?? 0; rows.set(column, row + 1); return [card.id, { x: column * 420, y: row * 340 }]; }));
}
/** External evidence is clickable only for ordinary web URLs; local/code refs remain readable. */
export function sourceUrl(ref: string): string | null {
  try { const url = new URL(ref); return ["https:", "http:"].includes(url.protocol) ? url.href : null; } catch { return null; }
}

export function safeDrawingPreview(file: DrawingFile): string | null {
  return isDrawingImageType(file.mimeType) && file.dataURL.startsWith(`data:${file.mimeType};base64,`) ? file.dataURL : null;
}

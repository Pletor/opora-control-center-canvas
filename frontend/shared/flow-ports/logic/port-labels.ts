// Čistá logika úchytů (portů) na plátně: český název druhu portu pro tooltip a aria-label a převrácená
// hodnota zoomu, kterou CSS použije, aby kulička i zásahová plocha měly na obrazovce stálou velikost.
export type PortKind = "next" | "action" | "rule" | "block" | "flow" | "material" | "pipeline";

const LABEL: Record<PortKind, string> = {
  next: "Další krok",
  action: "Akce",
  rule: "Pravidlo",
  block: "Port bloku",
  flow: "Tok mezi oblastmi",
  material: "Podklady",
  pipeline: "Pipeline",
};

/** Název portu pro člověka; port bloku nese vlastní jméno (`name`), bez něj zůstane obecný popisek. */
export function portLabel(kind: PortKind, name = ""): string {
  const trimmed = name.trim();
  if (kind === "block") return trimmed || LABEL.block;
  return LABEL[kind];
}

/** Text pro `title`: název a případně, co s portem jde dělat. */
export function portTitle(kind: PortKind, name = "", hint = ""): string {
  const label = portLabel(kind, name);
  return hint.trim() ? `${label} · ${hint.trim()}` : label;
}

export const MIN_INV_ZOOM = 0.4;
export const MAX_INV_ZOOM = 3;

/** Převrácený zoom pro `--rf-inv-zoom`. Omezený shora i zdola, aby sousední zásahové plochy při velkém oddálení nelezly přes sebe. */
export function inverseZoom(zoom: number): number {
  if (!Number.isFinite(zoom) || zoom <= 0) return 1;
  const value = Math.min(MAX_INV_ZOOM, Math.max(MIN_INV_ZOOM, 1 / zoom));
  return Math.round(value * 1000) / 1000;
}

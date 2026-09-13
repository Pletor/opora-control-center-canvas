export const WIREFRAME_KINDS = [
  "section",
  "two-columns",
  "three-columns",
  "hero",
  "cta",
  "heading",
  "text",
  "button",
  "input",
  "image-placeholder",
  "card",
  "nav",
] as const;

export type WireframeKind = (typeof WIREFRAME_KINDS)[number];
export type WireframeRole = "block" | "element";
export type WireframeAnimationPreset = "none" | "fade" | "slide" | "scale";

export type WireframeMetadata = {
  version: 1;
  role: WireframeRole;
  component: string;
  template?: string;
  notes: string;
  action: string;
  behavior: string;
  animation: {
    preset: WireframeAnimationPreset;
    durationMs: number;
    delayMs: number;
  };
  parallax: { enabled: boolean; speed: number };
};

export type WireframeCustomData = { oporaWireframe: WireframeMetadata };

export type WireframeTemplate = {
  kind: WireframeKind;
  role: WireframeRole;
  component: string;
  label: string;
  width: number;
  height: number;
  slots?: number;
};

const templates: Record<WireframeKind, WireframeTemplate> = {
  section: { kind: "section", role: "block", component: "section", label: "Sekce", width: 720, height: 380 },
  "two-columns": { kind: "two-columns", role: "block", component: "columns", label: "2 sloupce", width: 720, height: 360, slots: 2 },
  "three-columns": { kind: "three-columns", role: "block", component: "columns", label: "3 sloupce", width: 720, height: 360, slots: 3 },
  hero: { kind: "hero", role: "block", component: "hero", label: "Hero", width: 760, height: 380 },
  cta: { kind: "cta", role: "block", component: "cta", label: "CTA", width: 640, height: 240 },
  heading: { kind: "heading", role: "element", component: "heading", label: "Nadpis", width: 340, height: 48 },
  text: { kind: "text", role: "element", component: "text", label: "Text", width: 360, height: 72 },
  button: { kind: "button", role: "element", component: "button", label: "Tlačítko", width: 150, height: 48 },
  input: { kind: "input", role: "element", component: "input", label: "Vstup", width: 280, height: 48 },
  "image-placeholder": { kind: "image-placeholder", role: "element", component: "image-placeholder", label: "Obrázek", width: 300, height: 190 },
  card: { kind: "card", role: "element", component: "card", label: "Karta", width: 280, height: 180 },
  nav: { kind: "nav", role: "element", component: "nav", label: "Navigace", width: 520, height: 52 },
};

const presets: readonly WireframeAnimationPreset[] = ["none", "fade", "slide", "scale"];
const text = (value: unknown) => (typeof value === "string" ? value : "");
const number = (value: unknown, fallback: number, min: number, max: number, integer = true) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.max(min, Math.min(max, integer ? Math.round(value) : value))
    : fallback;


export function getWireframeTemplate(kind: WireframeKind): WireframeTemplate {
  return templates[kind];
}

export function buildWireframeMetadata(
  kind: WireframeKind,
  patch: Partial<Omit<WireframeMetadata, "version" | "role" | "component" | "template">> = {},
): WireframeCustomData {
  const template = getWireframeTemplate(kind);
  return {
    oporaWireframe: {
      version: 1,
      role: template.role,
      component: template.component,
      ...(template.role === "block" ? { template: kind } : {}),
      notes: text(patch.notes),
      action: text(patch.action),
      behavior: text(patch.behavior),
      animation: {
        preset: presets.includes(patch.animation?.preset as WireframeAnimationPreset)
          ? (patch.animation?.preset as WireframeAnimationPreset)
          : "none",
        durationMs: number(patch.animation?.durationMs, 240, 0, 4000),
        delayMs: number(patch.animation?.delayMs, 0, 0, 4000),
      },
      parallax: {
        enabled: patch.parallax?.enabled === true,
        speed: number(patch.parallax?.speed, 0, -2, 2, false),
      },
    },
  };
}

export function sanitizeWireframeMetadata(value: unknown): WireframeCustomData | null {
  if (!value || typeof value !== "object") return null;
  const source = (value as { oporaWireframe?: unknown }).oporaWireframe;
  if (!source || typeof source !== "object") return null;
  const item = source as Record<string, unknown>;
  const role = item.role === "block" || item.role === "element" ? item.role : null;
  const component = text(item.component);
  if (!role || !component) return null;
  const animation = item.animation && typeof item.animation === "object" ? item.animation as Record<string, unknown> : {};
  const parallax = item.parallax && typeof item.parallax === "object" ? item.parallax as Record<string, unknown> : {};
  return {
    oporaWireframe: {
      version: 1,
      role,
      component,
      ...(role === "block" && text(item.template) ? { template: text(item.template) } : {}),
      notes: text(item.notes),
      action: text(item.action),
      behavior: text(item.behavior),
      animation: {
        preset: presets.includes(animation.preset as WireframeAnimationPreset) ? animation.preset as WireframeAnimationPreset : "none",
        durationMs: number(animation.durationMs, 240, 0, 4000),
        delayMs: number(animation.delayMs, 0, 0, 4000),
      },
      parallax: { enabled: parallax.enabled === true, speed: number(parallax.speed, 0, -2, 2, false) },
    },
  };
}

export function animationCss(metadata: WireframeMetadata): Record<string, string> {
  return {
    animationName: metadata.animation.preset === "none" ? "none" : `wireframe-${metadata.animation.preset}`,
    animationDuration: `${metadata.animation.durationMs}ms`,
    animationDelay: `${metadata.animation.delayMs}ms`,
    "--wireframe-parallax-speed": String(metadata.parallax.enabled ? metadata.parallax.speed : 0),
  };
}

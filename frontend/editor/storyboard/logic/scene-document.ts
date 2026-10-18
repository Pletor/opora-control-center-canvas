// Webová scéna bez Reactu: z HTML dokumentu scény složí stránku pro iframe i render balíčku (CSP + runtime jako první
// skript), textově odmítne externí zdroje dřív, než je CSP mlčky zablokuje, a převede koncept z panelu Scéna na
// `SceneSpec`. Ukázkový dokument `EMPTY_SCENE` předvádí kontrakt z docs/storyboard-karty.md (vrstvy, data-t0, seek).
import runtime from "../assets/render-package/scene-runtime.js?raw";
import { fieldsStoryboard } from "./animations/code";
import { parseShape } from "./code-module";
import { MAX_SCENE_HTML, SCENE_ANIMATION, type SceneSpec, type Storyboard } from "./storyboard-model";

export const SCENE_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'";

/** Hlavička vkládaná před dokument: kódování (runtime by odsunul původní meta charset za prvních 1024 bajtů), CSP a runtime. */
const PREAMBLE = `<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="${SCENE_CSP}">\n<script>\n${runtime.replace(/<\/script/gi, "<\\/script")}\n</script>\n`;

/** Dokument scény se CSP a runtime hned za `<head>`; bez `<head>` za doctype a `<html>`, případně na úplný začátek. */
export function sceneDocument(html: string): string {
  const head = /<head(\s[^>]*)?>/i.exec(html);
  if (head) return html.slice(0, head.index + head[0].length) + "\n" + PREAMBLE + html.slice(head.index + head[0].length);
  const lead = /^\s*(<!doctype[^>]*>\s*)?(<html(\s[^>]*)?>\s*)?/i.exec(html)?.[0] ?? "";
  return lead + PREAMBLE + html.slice(lead.length);
}

const FORBIDDEN: [RegExp, string][] = [
  [/<script\b[^>]*\bsrc\s*=/i, "<script src>"],
  [/<link\b/i, "<link>"],
  [/@import\b/i, "@import"],
  [/url\(\s*['"]?\s*(https?:|\/\/)/i, "url(http…)"],
  [/\bfetch\s*\(/, "fetch"],
  [/\bXMLHttpRequest\b/, "XMLHttpRequest"],
  [/\bWebSocket\b/, "WebSocket"],
  [/\bimport\s*\(/, "import()"],
];

/** Externí zdroj v dokumentu scény jako česká věta; null = dokument je samostatný. */
export function forbiddenScene(html: string): string | null {
  const hit = FORBIDDEN.find(([pattern]) => pattern.test(html));
  return hit ? `Scéna nesmí načítat externí zdroje (${hit[1]}).` : null;
}

/** Koncept z panelu Scéna (dokument, název, JSON polí a vrstev) na `SceneSpec`; chyba jako česká věta. */
export function parseSceneDraft(draft: { html: string; title: string; fields: string; layers: string }): { scene: SceneSpec } | { error: string } {
  if (!draft.html.trim()) return { error: "Dokument scény je prázdný." };
  if (draft.html.length > MAX_SCENE_HTML) return { error: "Dokument scény je delší než 256 kB." };
  const forbidden = forbiddenScene(draft.html);
  if (forbidden) return { error: forbidden };
  const shape = parseShape(draft.fields, draft.layers);
  if ("error" in shape) return shape;
  if (!shape.layers.length) return { error: "Scéna musí mít aspoň jednu vrstvu." };
  return { scene: { html: draft.html, title: draft.title, ...shape } };
}

export const EMPTY_SCENE_HTML = `<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>Webová scéna</title>
<style>
  html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; }
  /* Vrstva pozadi: plocha přes celý viewport. */
  .pozadi { position: absolute; inset: 0; background: linear-gradient(160deg, #101418, #1d2a33); }
  /* Vrstva objekt: koule na pozici x, y; runtime zapisuje stav momentů jako CSS proměnné (--x, --y jsou 0-1). */
  .objekt { position: absolute; left: calc(var(--x, 0.5) * 100%); top: calc(var(--y, 0.5) * 100%);
    width: 10vh; height: 10vh; margin: -5vh 0 0 -5vh; border-radius: 50%; background: #f4b942; }
  /* Pulz: CSS animace počítaná od t0 = 1 s (data-t0 na kouli); runtime ji pozastaví na (t - 1) s. */
  .objekt__pulz { position: absolute; inset: 0; border-radius: 50%; border: 0.8vh solid #f4b942;
    animation: pulz 1.5s ease-out infinite; }
  @keyframes pulz { from { transform: scale(1); opacity: 1; } to { transform: scale(4); opacity: 0; } }
  .titulek { position: absolute; left: 4vw; bottom: 6vh; font: 600 5vh system-ui, sans-serif; color: #e8edf2; }
</style>
</head>
<body>
  <div class="pozadi" data-layer="pozadi"></div>
  <div class="objekt" data-layer="objekt" data-t0="1"><div class="objekt__pulz"></div></div>
  <div class="titulek" data-layer="objekt" id="cas">0.0 s</div>
<script>
  // Čas řídí host: žádné časovače, jen seek(t, state). state = zinterpolovaný stav momentů (fields).
  window.scene = {
    seek(t, state) {
      document.getElementById("cas").textContent = t.toFixed(1) + " s";
    },
  };
</script>
</body>
</html>
`;

export const EMPTY_SCENE: SceneSpec = {
  title: "Webová scéna", html: EMPTY_SCENE_HTML,
  fields: [{ key: "x", label: "Poloha x", kind: "number", min: 0, max: 1, step: 0.01 }, { key: "y", label: "Poloha y", kind: "number", min: 0, max: 1, step: 0.01 }],
  layers: [{ id: "pozadi", label: "Pozadí" }, { id: "objekt", label: "Objekt" }],
};

/** Prázdný storyboard scény: 6 s, dva momenty podle polí (jako u vlastního kódu). */
export const sceneStoryboard = (scene: SceneSpec): Storyboard => ({ ...fieldsStoryboard(SCENE_ANIMATION, scene.title, scene.fields), scene });

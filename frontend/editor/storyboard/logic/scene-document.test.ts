import { describe, expect, it } from "vitest";
import { EMPTY_SCENE, SCENE_CSP, forbiddenScene, parseSceneDraft, sceneDocument, sceneStoryboard } from "./scene-document";
import { validate } from "./storyboard-model";

describe("webová scéna", () => {
  it("sceneDocument vloží CSP a runtime hned za <head>", () => {
    const doc = sceneDocument("<!doctype html><html><HEAD lang=\"cs\"><title>x</title></head><body></body></html>");
    const at = doc.indexOf('<HEAD lang="cs">') + '<HEAD lang="cs">'.length;
    expect(doc.slice(at)).toMatch(/^\s*<meta charset="utf-8">\s*<meta http-equiv="Content-Security-Policy"/);
    expect(doc).toContain(`content="${SCENE_CSP}"`);
    expect(doc).toContain("window.seek = function");
    expect(doc.indexOf("window.seek = function")).toBeLessThan(doc.indexOf("<title>"));
  });
  it("bez <head> jde hlavička za doctype a <html>, jinak na začátek", () => {
    expect(sceneDocument("<!doctype html><html><body>x</body></html>")).toMatch(/^<!doctype html><html><meta charset/);
    expect(sceneDocument("<div>x</div>")).toMatch(/^<meta charset/);
    expect(sceneDocument("<div>x</div>")).toMatch(/<\/script>\n<div>x<\/div>$/);
  });
  it("forbiddenScene odmítne externí zdroje česky", () => {
    expect(forbiddenScene(EMPTY_SCENE.html)).toBeNull();
    for (const bad of ['<script src="a.js"></script>', '<link rel="stylesheet" href="x">', "@import 'x.css';", "background: url(https://x/y.png)",
      "fetch('/api')", "new XMLHttpRequest()", "new WebSocket('ws://x')", "import('./x.js')"]) {
      expect(forbiddenScene(bad)).toMatch(/^Scéna nesmí načítat externí zdroje \(.+\)\.$/);
    }
    expect(forbiddenScene("background: url(data:image/png;base64,AA)")).toBeNull();
  });
  it("parseSceneDraft kontroluje dokument, JSON a vrstvy", () => {
    const ok = parseSceneDraft({ html: EMPTY_SCENE.html, title: "T", fields: JSON.stringify(EMPTY_SCENE.fields), layers: JSON.stringify(EMPTY_SCENE.layers) });
    expect(ok).toEqual({ scene: { ...EMPTY_SCENE, title: "T" } });
    expect(parseSceneDraft({ html: " ", title: "", fields: "[]", layers: "[]" })).toEqual({ error: "Dokument scény je prázdný." });
    expect(parseSceneDraft({ html: "x".repeat(262145), title: "", fields: "[]", layers: "[]" })).toEqual({ error: "Dokument scény je delší než 256 kB." });
    expect("error" in parseSceneDraft({ html: "<link>", title: "", fields: "[]", layers: "[]" })).toBe(true);
    expect(parseSceneDraft({ html: "<p>", title: "", fields: "{", layers: "[]" })).toEqual({ error: "Pole fields nejsou platný JSON." });
    expect(parseSceneDraft({ html: "<p>", title: "", fields: "[]", layers: "[]" })).toEqual({ error: "Scéna musí mít aspoň jednu vrstvu." });
  });
  it("ukázková scéna předvádí kontrakt a sceneStoryboard je platný", () => {
    expect(EMPTY_SCENE.html).toContain('data-layer="pozadi"');
    expect(EMPTY_SCENE.html).toContain('data-layer="objekt"');
    expect(EMPTY_SCENE.html).toContain('data-t0="1"');
    expect(EMPTY_SCENE.html).toContain("window.scene = {");
    const board = sceneStoryboard(EMPTY_SCENE);
    expect(board.animation).toBe("scena");
    expect(board.code).toBeUndefined();
    expect(board.moments.map((m) => m.state.x)).toEqual([0.3, 0.7]);
    expect(validate(board, ["scena"])).toEqual([]);
  });
});

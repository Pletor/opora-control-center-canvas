import { describe, expect, it } from "vitest";
import { ANIMATIONS } from "./animations";
import { EMPTY_CODE, codeStoryboard } from "./animations/code";
import { EMPTY_SCENE, sceneDocument, sceneStoryboard } from "./scene-document";
import { assetFileName, packageAssets, packageSource, renderPackage } from "./render-package";
import type { StoryboardAsset } from "./storyboard-model";

describe("balíček pro render", () => {
  it("pro šablonu nese zdroj z registru a pět souborů", () => {
    const files = renderPackage(ANIMATIONS.kulicka.defaults())!;
    expect(files.map((f) => f.name)).toEqual(["storyboard.json", "animation.js", "CLAUDE.md", "render.py", "index.html"]);
    expect(files[1].text).toBe(ANIMATIONS.kulicka.source);
    expect(JSON.parse(files[0].text!).animation).toBe("kulicka");
  });
  it("pro vlastní kód nese code.source a storyboard.json i s kódem", () => {
    const board = codeStoryboard(EMPTY_CODE);
    const files = renderPackage(board)!;
    expect(files[1].text).toBe(EMPTY_CODE.source);
    expect(JSON.parse(files[0].text!).code.source).toBe(EMPTY_CODE.source);
  });
  it("statické soubory popisují modul animation.js a seek(t)", () => {
    const [, , claude, render, html] = renderPackage(codeStoryboard(EMPTY_CODE))!;
    expect(claude.text).toContain("seek(t)");
    expect(render.text).toContain("STORYBOARD_READY");
    expect(html.text).toContain('import * as animation from "./animation.js"');
  });
  it("neznámá animace nebo kód bez zdroje balíček nevyrobí", () => {
    expect(packageSource({ ...codeStoryboard(EMPTY_CODE), code: undefined })).toBeNull();
    expect(renderPackage({ ...codeStoryboard(EMPTY_CODE), animation: "neznama", code: undefined })).toBeNull();
  });
  it("podklady: storyboard.json nese file, obrázek jde jako asset-<id>.<ext> a bez obrázku balíček není", () => {
    const asset: StoryboardAsset = { id: "a-12345678", name: "šachovnice", fileId: "f1", mimeType: "image/png", purpose: "texture", target: "objekt", momentId: "", color: "#ff0000", colorUse: "tint", note: "na kouli", answered: false };
    const board = { ...codeStoryboard(EMPTY_CODE), assets: [asset] };
    expect(assetFileName(asset)).toBe("asset-a-12345678.png");
    expect(JSON.parse(renderPackage(board)![0].text!).assets[0].file).toBe("asset-a-12345678.png");
    const files = packageAssets(board, [{ id: "f1", dataURL: "data:image/png;base64,AAAA" }]);
    expect(files).toEqual([{ name: "asset-a-12345678.png", type: "image/png", dataURL: "data:image/png;base64,AAAA" }]);
    expect(() => packageAssets(board, [])).toThrow("šachovnice");
    expect(renderPackage(codeStoryboard(EMPTY_CODE))![4].text).toContain("images[asset.id]");
  });
  it("webová scéna: scene.html čistý, index.html se CSP a runtime, render.py fotí viewport", () => {
    const board = sceneStoryboard(EMPTY_SCENE);
    expect(packageSource(board)).toBe(EMPTY_SCENE.html);
    const files = renderPackage(board)!;
    expect(files.map((f) => f.name)).toEqual(["storyboard.json", "scene.html", "index.html", "render.py", "CLAUDE.md"]);
    expect(files[1].text).toBe(EMPTY_SCENE.html);
    expect(files[2].text).toBe(sceneDocument(EMPTY_SCENE.html));
    expect(JSON.parse(files[0].text!).scene.html).toBe(EMPTY_SCENE.html);
    expect(files[3].text).toContain("page.screenshot(");
    expect(files[4].text).toContain("Webová scéna");
    expect(packageSource({ ...board, scene: undefined })).toBeNull();
  });
});

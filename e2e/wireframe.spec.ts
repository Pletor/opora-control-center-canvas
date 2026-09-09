import { expect, test } from "@playwright/test";
import {
  animationCss,
  buildWireframeMetadata,
  getWireframeTemplate,
  isWireframeKind,
  sanitizeWireframeMetadata,
} from "../src/wireframe-model";

test("wireframe templates distinguish blocks and elements", () => {
  expect(isWireframeKind("hero")).toBe(true);
  expect(isWireframeKind("button")).toBe(true);
  expect(isWireframeKind("unknown")).toBe(false);
  expect(getWireframeTemplate("three-columns")).toMatchObject({
    role: "block",
    component: "columns",
    slots: 3,
  });
  expect(getWireframeTemplate("input")).toMatchObject({
    role: "element",
    component: "input",
  });
});

test("wireframe metadata uses only the semantic namespace and bounded values", () => {
  const metadata = buildWireframeMetadata("cta", {
    notes: "Primární výzva",
    action: "open-settings",
    behavior: "submit",
    animation: { preset: "slide", durationMs: 99999, delayMs: -4 },
    parallax: { enabled: true, speed: 99 },
  });
  expect(metadata).toEqual({
    oporaWireframe: {
      version: 1,
      role: "block",
      component: "cta",
      template: "cta",
      notes: "Primární výzva",
      action: "open-settings",
      behavior: "submit",
      animation: { preset: "slide", durationMs: 4000, delayMs: 0 },
      parallax: { enabled: true, speed: 2 },
    },
  });
  expect(Object.keys(metadata.oporaWireframe)).not.toEqual(
    expect.arrayContaining(["x", "y", "width", "height", "color", "frameId", "label"]),
  );
});

test("metadata repair and preview CSS never execute arbitrary action text", () => {
  const repaired = sanitizeWireframeMetadata({
    oporaWireframe: {
      version: 7,
      role: "element",
      component: "button",
      notes: 12,
      action: "javascript:alert(1)",
      behavior: null,
      animation: { preset: "unsafe", durationMs: "no" },
      parallax: { enabled: "yes", speed: -12 },
      x: 10,
    },
  });
  expect(repaired).toEqual({
    oporaWireframe: {
      version: 1,
      role: "element",
      component: "button",
      notes: "",
      action: "javascript:alert(1)",
      behavior: "",
      animation: { preset: "none", durationMs: 240, delayMs: 0 },
      parallax: { enabled: false, speed: -2 },
    },
  });
  expect(animationCss(repaired!.oporaWireframe)).toEqual({
    animationName: "none",
    animationDuration: "240ms",
    animationDelay: "0ms",
    "--wireframe-parallax-speed": "0",
  });
});


test("parallax preserves fractional speed", () => {
  expect(buildWireframeMetadata("card", { parallax: { enabled: true, speed: 0.25 } }).oporaWireframe.parallax.speed).toBe(0.25);
});

test("wireframe insertion selects editable semantics and does not duplicate across modes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  expect(new URL(origin).port).toBe("8741");
  const created = await page.request.post("/api/empty-project", { headers: { origin }, data: { name: "Wireframe fixture", confirmed: true } });
  expect(created.ok()).toBe(true);
  const project = await created.json();
  await page.goto("/?screen=canvas&project=" + project.id + "&workspace=draft&mode=drawing&wireframe=1");
  const palette = page.locator(".wireframe-tools");
  await palette.getByRole("button", { name: "2 sloupce", exact: true }).click();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("3");
  await expect(page.getByLabel("Poznámky", { exact: true })).toBeVisible();
  await page.getByLabel("Poznámky", { exact: true }).fill("Hlavní rozložení stránky");
  await palette.getByRole("button", { name: "Tlačítko", exact: true }).click();
  await page.getByLabel("Poznámky", { exact: true }).fill("Primární CTA");
  await page.getByLabel("Akce (popis, nevykonává se)", { exact: true }).fill("Otevřít registraci");
  await page.getByLabel("Chování", { exact: true }).fill("Po kliknutí zobrazit formulář");
  await page.getByLabel("Animace", { exact: true }).selectOption("fade");
  await page.getByLabel("Výplň", { exact: true }).fill("#335577");
  await page.screenshot({ path: "evidence/wireframe-editing-preview.png", fullPage: true });
  await page.getByRole("button", { name: "Uložit kresbu", exact: true }).click();
  await expect(page.getByTestId("drawing-status")).toContainText("Uloženo · verze 1");
  const query = new URLSearchParams({ project: project.id, workspace: "draft", layer: "" });
  const saved = await (await page.request.get("/api/drawing?" + query)).json();
  const count = saved.scene.elements.length;
  const context = await (await page.request.get("/api/wireframe-context?" + query)).json();
  expect(context.blocks).toHaveLength(1);
  expect(context.elements).toHaveLength(1);
  expect(context.elements[0].wireframe.notes).toBe("Primární CTA");
  expect(context.elements[0].wireframe.action).toBe("Otevřít registraci");
  expect(context.elements[0].frameId).toBe(context.blocks[0].id);
  expect(context.elements[0].backgroundColor).toBe("#335577");
  await page.getByRole("button", { name: "Mód: Mapa", exact: true }).click();
  await page.getByRole("button", { name: "Mód: Kreslení", exact: true }).click();
  await expect(page.getByTestId("drawing-element-count")).toHaveText(String(count));
  await page.getByRole("button", { name: "Uložit kresbu", exact: true }).click();
  await expect(page.getByTestId("drawing-status")).toContainText("Uloženo · verze 2");
  expect((await (await page.request.get("/api/drawing?" + query)).json()).scene.elements).toHaveLength(count);
  await page.screenshot({ path: "evidence/wireframe-editor.png" });
});

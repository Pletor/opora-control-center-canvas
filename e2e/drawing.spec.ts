import { test, expect } from "@playwright/test";

test("draw a real rectangle, save and restore without changing project graph", async ({
  page,
}) => {
  const errors: string[] = [];
  const external: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (
      url.protocol.startsWith("http") &&
      url.origin !== "http://127.0.0.1:8741"
    ) {
      external.push(url.href);
      return route.abort();
    }
    return route.continue();
  });
  await page.goto("/?mode=drawing");
  const before = await (await page.request.get("/api/view")).json();
  await expect(page.getByTestId("drawing-surface")).toBeVisible();
  await page
    .getByRole("button", { name: "Nástroj: Obdélník", exact: true })
    .click();
  const canvas = page
    .getByTestId("drawing-surface")
    .locator("canvas.interactive");
  await expect(canvas).toBeVisible();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + 280, box.y + 110);
  await page.mouse.down();
  await page.mouse.move(box.x + 440, box.y + 220, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  const stored = await (
    await page.request.get("/api/drawing?project=draft&workspace=draft&layer=")
  ).json();
  expect(
    stored.scene.elements
      .filter((e: { isDeleted?: boolean }) => !e.isDeleted)
      .map((e: { type: string }) => e.type),
  ).toEqual(["rectangle"]);
  expect((await (await page.request.get("/api/view")).json()).digest).toBe(
    before.digest,
  );
  await page
    .getByRole("button", { name: "Mód: Struktura", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Mód: Kreslení", exact: true })
    .click();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
  await page.reload();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
  await page.screenshot({ path: "evidence/drawing-rectangle.png" });
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
});

async function newDrawingLayer(
  page: import("@playwright/test").Page,
  name: string,
) {
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  expect(new URL(origin).port).toBe("8741");
  const current = await (await page.request.get("/api/view")).json();
  const id = "draw-" + Date.now().toString();
  const graph = {
    ...current.graph,
    nodes: [
      ...current.graph.nodes,
      { id, parentId: null, kind: "node", name, purpose: "", x: 0, y: 0 },
    ],
  };
  expect(
    (
      await page.request.post("/api/graph", {
        headers: { origin },
        data: {
          project: "draft",
          workspace: "draft",
          digest: current.digest,
          graph,
        },
      })
    ).ok(),
  ).toBe(true);
  await page.goto("/?mode=drawing&layer=" + id);
  await expect(
    page.getByTestId("drawing-surface").locator("canvas.interactive"),
  ).toBeVisible();
  return id;
}

async function shape(
  page: import("@playwright/test").Page,
  label: string,
  start: [number, number],
  end: [number, number],
) {
  const button = page.getByRole("button", {
    name: "Nástroj: " + label,
    exact: true,
  });
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  const box = (await page
    .getByTestId("drawing-surface")
    .locator("canvas.interactive")
    .boundingBox())!;
  await page.mouse.move(box.x + start[0], box.y + start[1]);
  await page.mouse.down();
  await page.mouse.move(box.x + end[0], box.y + end[1], { steps: 8 });
  await page.mouse.up();
}

test("pencil and shapes remain as an unsaved draft across modes and stay layer-scoped", async ({
  page,
}) => {
  const rootBefore = await (
    await page.request.get("/api/drawing?project=draft&workspace=draft&layer=")
  ).json();
  const id = await newDrawingLayer(page, "Kreslicí test");
  await shape(page, "Tužka", [280, 110], [420, 190]);
  await shape(page, "Elipsa", [480, 100], [620, 200]);
  await shape(page, "Šipka", [290, 240], [570, 310]);
  await expect(page.getByTestId("drawing-element-count")).toHaveText("3");
  await page.getByRole("button", { name: "Mód: Mapa", exact: true }).click();
  await page
    .getByRole("button", { name: "Mód: Kreslení", exact: true })
    .click();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("3");
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  const stored = await (
    await page.request.get(
      "/api/drawing?project=draft&workspace=draft&layer=" + id,
    )
  ).json();
  expect(
    stored.scene.elements.map((e: { type: string }) => e.type).sort(),
  ).toEqual(["arrow", "ellipse", "freedraw"]);
  await page
    .getByRole("navigation", { name: "Cesta plátnem" })
    .getByRole("button", { name: "Projekt", exact: true })
    .click();
  await expect(page.getByTestId("drawing-element-count")).toHaveText(
    String(
      rootBefore.scene.elements.filter(
        (e: { isDeleted?: boolean }) => !e.isDeleted,
      ).length,
    ),
  );
});

test("main drawing is honestly unavailable and read-only", async ({ page }) => {
  await page.goto("/?project=fixture&workspace=main&mode=drawing");
  await expect(
    page.getByText("Kreslení v pracovním prostoru", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Uložit kresbu", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Nástroj: Obdélník", exact: true }),
  ).toBeDisabled();
});

test("text can be entered and drawn elements can be deleted and saved", async ({
  page,
}) => {
  const id = await newDrawingLayer(page, "Text a mazání");
  const textTool = page.getByRole("button", {
    name: "Nástroj: Text",
    exact: true,
  });
  await textTool.click();
  await expect(textTool).toHaveAttribute("aria-pressed", "true");
  const canvas = page
    .getByTestId("drawing-surface")
    .locator("canvas.interactive");
  await canvas.click({ position: { x: 320, y: 130 } });
  await page
    .getByTestId("drawing-surface")
    .locator("textarea:visible")
    .fill("Poznámka pro vývoj");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  const first = await (
    await page.request.get(
      "/api/drawing?project=draft&workspace=draft&layer=" + id,
    )
  ).json();
  expect(first.scene.elements[0].text).toBe("Poznámka pro vývoj");
  await page
    .getByRole("button", { name: "Nástroj: Výběr", exact: true })
    .click();
  await canvas.click({ position: { x: 700, y: 280 } });
  await page.keyboard.press("Control+a");
  await page.keyboard.press("Delete");
  await expect(page.getByTestId("drawing-element-count")).toHaveText("0");
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 2",
  );
  expect(
    (
      await (
        await page.request.get(
          "/api/drawing?project=draft&workspace=draft&layer=" + id,
        )
      ).json()
    ).scene.elements,
  ).toEqual([]);
});

test("drawing conflict preserves local work until explicit discard", async ({
  page,
  context,
}) => {
  const id = await newDrawingLayer(page, "Souběh kresby");
  const other = await context.newPage();
  await other.goto("/?mode=drawing&layer=" + id);
  await expect(
    other.getByTestId("drawing-surface").locator("canvas.interactive"),
  ).toBeVisible();
  await shape(page, "Obdélník", [280, 110], [440, 220]);
  await shape(other, "Elipsa", [300, 110], [470, 220]);
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  await other
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(other.getByRole("alert")).toContainText("Kresba se změnila");
  await expect(other.getByTestId("drawing-element-count")).toHaveText("1");
  await other
    .getByRole("button", {
      name: "Zahodit místní a načíst uložené",
      exact: true,
    })
    .click();
  await expect(other.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  await other
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await expect(other.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 2",
  );
  const stored = await (
    await other.request.get(
      "/api/drawing?project=draft&workspace=draft&layer=" + id,
    )
  ).json();
  expect(stored.scene.elements.map((e: { type: string }) => e.type)).toEqual([
    "rectangle",
  ]);
  await other.close();
});

test("in-flight drawing save survives a mode round trip", async ({ page }) => {
  await newDrawingLayer(page, "Čekající save");
  await shape(page, "Obdélník", [280, 110], [440, 220]);
  let release!: () => void;
  let signal!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const arrived = new Promise<void>((resolve) => {
    signal = resolve;
  });
  await page.route("**/api/drawing", async (route) => {
    const response = await route.fetch();
    signal();
    await held;
    await route.fulfill({ response });
  });
  await page
    .getByRole("button", { name: "Uložit kresbu", exact: true })
    .click();
  await arrived;
  await page
    .getByRole("button", { name: "Mód: Struktura", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Mód: Kreslení", exact: true })
    .click();
  await expect(page.getByTestId("drawing-status")).toContainText("Načítám");
  release();
  await expect(page.getByTestId("drawing-status")).toContainText(
    "Uloženo · verze 1",
  );
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
});

test("drawing and settings remain contained on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=drawing");
  await expect(page.getByTestId("drawing-surface")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Nastavení plochy", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Hotovo", exact: true })
    .click();
  await page.getByTestId("drawing-surface").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "evidence/drawing-mobile.png" });
});

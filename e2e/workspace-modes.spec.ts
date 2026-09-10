import { test, expect } from "@playwright/test";

/** Nastavení i operace projektu žijí v jednom menu horní lišty (WU-CLEAN-DESIGN). */
async function openSettings(page: import("@playwright/test").Page, item: string) {
  await page.getByRole("button", { name: "Nastavení", exact: true }).click();
  await page.getByRole("group", { name: "Nastavení a operace" }).getByRole("button", { name: item, exact: true }).click();
}

test("workspace modes and actual grid settings survive reload", async ({
  page,
}) => {
  const fs = await import("node:fs/promises");
  const manifest = JSON.parse(
    await fs.readFile("dist/.vite/manifest.json", "utf8"),
  );
  expect(manifest["index.html"].dynamicImports).toHaveLength(1);
  const drawingEntry = manifest[manifest["index.html"].dynamicImports[0]];
  expect(drawingEntry.isDynamicEntry).toBe(true);
  const resources: string[] = [];
  page.on("request", (r) => resources.push(r.url()));
  await page.goto("/?screen=canvas");
  await expect(
    page.getByRole("button", { name: "Mód: Struktura", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(
    resources.some((r) => new URL(r).pathname === "/" + drawingEntry.file),
  ).toBe(false);
  await openSettings(page, "Nastavení plochy");
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Zobrazit mřížku").uncheck();
  await dialog.getByLabel("Přichytávat k mřížce").check();
  await dialog.getByRole("button", { name: "Hotovo", exact: true }).click();
  await expect(page.locator(".react-flow__background")).toHaveCount(0);
  await page.getByRole("button", { name: "Mód: Mapa", exact: true }).click();
  await expect(page.getByTestId("project-map")).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Mód: Mapa", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await openSettings(page, "Nastavení plochy");
  await expect(page.getByLabel("Zobrazit mřížku")).not.toBeChecked();
  await expect(page.getByLabel("Přichytávat k mřížce")).toBeChecked();
});

test("map shows actual hierarchy and exports source-backed Archify JSON", async ({
  page,
}) => {
  await page.goto("/?project=fixture&workspace=main&mode=map");
  await expect(page.getByTestId("project-map")).toBeVisible();
  await expect(page.getByTestId("map-node-count")).toHaveText("1");
  await expect(
    page.getByTestId("project-map").locator(".react-flow__node"),
  ).toHaveCount(2);
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export pro Archify", exact: true })
    .click();
  const file = await download;
  await file.saveAs("evidence/project-map.architecture.json");
  const fs = await import("node:fs/promises");
  const spec = JSON.parse(
    await fs.readFile("evidence/project-map.architecture.json", "utf8"),
  );
  expect(spec.diagram_type).toBe("architecture");
  expect(spec.components.map((c: { id: string }) => c.id)).toEqual([
    "project",
    "node_sector1",
  ]);
  expect(spec.connections).toContainEqual(
    expect.objectContaining({ from: "project", to: "node_sector1" }),
  );
  await page
    .getByTestId("project-map")
    .locator('.react-flow__node[data-id="node_sector1"]')
    .dblclick();
  await expect(
    page.getByRole("button", { name: "Mód: Struktura", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("navigation", { name: "Cesta plátnem" }),
  ).toContainText("Fixture sector");
});

test("map creates a real cross-layer connection", async ({ page }) => {
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  expect(new URL(origin).port).toBe("8742");
  const current = await (await page.request.get("/api/view")).json();
  const nodes = [
    {
      id: "map-before",
      parentId: null,
      kind: "node",
      name: "Mapa reference",
      purpose: "",
      x: 0,
      y: 180,
    },
    {
      id: "map-parent",
      parentId: null,
      kind: "sector",
      name: "Mapa sektor",
      purpose: "",
      x: 0,
      y: 0,
    },
    {
      id: "map-child",
      parentId: "map-parent",
      kind: "node",
      name: "Mapa vnitřní uzel",
      purpose: "",
      x: 0,
      y: 0,
    },
    {
      id: "map-other",
      parentId: null,
      kind: "node",
      name: "Mapa jiný uzel",
      purpose: "",
      x: 320,
      y: 0,
    },
  ];
  expect(
    (
      await page.request.post("/api/graph", {
        headers: { origin },
        data: {
          project: "draft",
          workspace: "draft",
          digest: current.digest,
          graph: {
            ...current.graph,
            nodes: [...current.graph.nodes, ...nodes],
          },
        },
      })
    ).ok(),
  ).toBe(true);
  await page.goto("/?mode=map");
  await page
    .getByLabel("Propojit z", { exact: true })
    .selectOption("map-child");
  await page
    .getByLabel("Propojit do", { exact: true })
    .selectOption("map-other");
  await page
    .getByRole("button", { name: "Propojit uzly", exact: true })
    .click();
  await expect
    .poll(async () =>
      (await (await page.request.get("/api/view")).json()).graph.edges.some(
        (e: { source: string; target: string }) =>
          e.source === "map-child" && e.target === "map-other",
      ),
    )
    .toBe(true);
  await page.reload();
  await expect(page.getByTestId("project-map")).toBeVisible();
  const graph = (await (await page.request.get("/api/view")).json()).graph;
  await expect(
    page.getByTestId("project-map").locator(".react-flow__edge"),
  ).toHaveCount(graph.nodes.length + graph.edges.length);
  const parentBox = (await page
    .locator('.react-flow__node[data-id="node_map-parent"]')
    .boundingBox())!;
  const childBox = (await page
    .locator('.react-flow__node[data-id="node_map-child"]')
    .boundingBox())!;
  expect(Math.abs(parentBox.y - childBox.y)).toBeLessThan(1);
  await page.screenshot({ path: "evidence/project-map.png" });
});

test("grid snapping changes actual saved node coordinates", async ({
  page,
}) => {
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  const view = await (await page.request.get("/api/view")).json();
  const id = "grid-" + Date.now();
  const graph = {
    ...view.graph,
    nodes: [
      ...view.graph.nodes,
      {
        id,
        parentId: null,
        kind: "node",
        name: "Mřížka",
        purpose: "",
        x: 53,
        y: 37,
      },
    ],
  };
  expect(
    (
      await page.request.post("/api/graph", {
        headers: { origin },
        data: {
          project: "draft",
          workspace: "draft",
          graph,
          digest: view.digest,
        },
      })
    ).ok(),
  ).toBe(true);
  await page.reload();
  await openSettings(page, "Nastavení plochy");
  await page.getByLabel("Přichytávat k mřížce").check();
  await page.getByLabel("Rozteč mřížky").selectOption("40");
  await page.getByRole("button", { name: "Hotovo", exact: true }).click();
  const card = page.locator('.react-flow__node[data-id="' + id + '"]');
  const box = (await card.boundingBox())!;
  await page.mouse.move(box.x + 90, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 127, box.y + 69, { steps: 8 });
  await page.mouse.up();
  await expect
    .poll(async () => {
      const data = (
        await (await page.request.get("/api/view")).json()
      ).graph.nodes.find((n: { id: string }) => n.id === id);
      return data.x % 40 === 0 && data.y % 40 === 0;
    })
    .toBe(true);
});

test("deleting an ancestor from global map repairs active layer", async ({
  page,
}) => {
  await page.goto("/?screen=canvas");
  const origin = new URL(page.url()).origin;
  const view = await (await page.request.get("/api/view")).json();
  const parent = "ancestor-" + Date.now(),
    child = parent + "-child";
  const nodes = [
    {
      id: parent,
      parentId: null,
      kind: "sector",
      name: "Smazaný předek",
      purpose: "",
      x: 0,
      y: 0,
    },
    {
      id: child,
      parentId: parent,
      kind: "node",
      name: "Původní vrstva",
      purpose: "",
      x: 0,
      y: 0,
    },
  ];
  expect(
    (
      await page.request.post("/api/graph", {
        headers: { origin },
        data: {
          project: "draft",
          workspace: "draft",
          graph: { ...view.graph, nodes: [...view.graph.nodes, ...nodes] },
          digest: view.digest,
        },
      })
    ).ok(),
  ).toBe(true);
  await page.goto("/?mode=map&layer=" + child);
  await page
    .locator('.react-flow__node[data-id="node_' + parent + '"]')
    .click();
  await page
    .getByRole("button", { name: "Smazat sektor", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Potvrdit smazání", exact: true })
    .click();
  await expect
    .poll(() => new URL(page.url()).searchParams.get("layer"))
    .toBe(null);
  await page
    .getByRole("button", { name: "Mód: Struktura", exact: true })
    .click();
  await expect(
    page.getByRole("navigation", { name: "Cesta plátnem" }),
  ).toHaveText("Projekt");
});

test("drawing module load failure does not take down the editor shell", async ({
  page,
}) => {
  const fs = await import("node:fs/promises");
  const manifest = JSON.parse(
    await fs.readFile("dist/.vite/manifest.json", "utf8"),
  );
  const entry = manifest[manifest["index.html"].dynamicImports[0]];
  await page.route("**/" + entry.file, (route) => route.abort());
  await page.goto("/?screen=canvas");
  await page
    .getByRole("button", { name: "Mód: Kreslení", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Pracovní plocha není dostupná",
  );
  await page
    .getByRole("button", { name: "Vrátit se do Struktury", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "+ Uzel", exact: true }),
  ).toBeEnabled();
});

import { test, expect } from "@playwright/test";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

async function attach(page: import("@playwright/test").Page, name: string, sourcePath: string) {
  await page.goto("/?screen=home");
  return page.evaluate(
    async ([name, sourcePath]) => {
      const response = await fetch("/api/local-project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, path: sourcePath, confirmed: true }),
      });
      return response.json();
    },
    [name, sourcePath],
  );
}

test("sector binds an existing folder, node binds a file inside it, and both persist after reload", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  mkdirSync(path.join(source, "pkg"));
  writeFileSync(path.join(source, "pkg", "mod.py"), "print(1)\n");

  const project = (await attach(page, "Fixture project", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);

  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Balíček");
  await page.getByRole("button", { name: "Navázat na existující zdroj" }).click();
  await page.getByRole("button", { name: "pkg", exact: true }).click();
  await expect(page.getByText("Vybráno:")).toBeVisible();
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();

  await expect(page.getByText("Existující zdroj")).toBeVisible();
  await expect(page.locator(".source-badge code")).toHaveText("pkg");

  await page.getByRole("button", { name: "Otevřít vnitřní plátno" }).click();
  await page.getByRole("button", { name: "+ Uzel" }).click();
  await page.getByLabel("Název uzlu").fill("Modul");
  await page.getByRole("button", { name: "Navázat na existující zdroj" }).click();
  await page.getByRole("button", { name: "mod.py", exact: true }).click();
  await expect(page.getByText("Vybráno:")).toBeVisible();
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();

  await expect(page.getByText("Existující zdroj")).toBeVisible();
  await expect(page.locator(".source-badge code")).toHaveText("pkg/mod.py");

  await page.reload();
  await expect(page.locator("[data-testid^='rf__node-']").getByText("Modul", { exact: true })).toBeVisible();
  const persisted = await page.evaluate(async (projectId) => (await fetch("/api/view?" + new URLSearchParams({ project: projectId, workspace: "draft" }))).json(), project.id);
  expect(persisted.graph.nodes.find((node: { name: string }) => node.name === "Modul").sourceRef).toEqual({ origin: "existing", path: "pkg/mod.py", kind: "file" });
});

test("planned sector requires a meaningful purpose and never touches disk", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  const project = (await attach(page, "Planned project", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);

  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Navrh");
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Zamýšlená cesta").fill("budouci/oblast");
  const submit = page.getByRole("button", { name: "Vytvořit", exact: true });
  await expect(submit).toBeDisabled();
  await page.getByLabel("Podstata návrhu sektoru").fill("Nová oblast odpovědnosti pro platby.");
  await expect(submit).toBeEnabled();
  await submit.click();

  await expect(page.getByText("Návrh zdroje")).toBeVisible();
  expect(existsSync(path.join(source, "budouci"))).toBe(false);
});

test("creation dialog does not preselect a source and resets between openings", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  mkdirSync(path.join(source, "a"));
  mkdirSync(path.join(source, "b"));
  const project = (await attach(page, "Reset project", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);

  await page.getByRole("button", { name: "+ Sektor" }).click();
  await expect(page.getByRole("button", { name: "Navázat na existující zdroj" })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("button", { name: "Navrhnout nové" })).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Navázat na existující zdroj" }).click();
  await page.getByRole("button", { name: "a", exact: true }).click();
  await expect(page.getByText("Vybráno:")).toBeVisible();
  await page.getByRole("button", { name: "Zavřít dialog" }).click();
  await page.getByRole("button", { name: "+ Sektor" }).click();
  await expect(page.getByRole("button", { name: "Navázat na existující zdroj" })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByText("Vybráno:")).toHaveCount(0);
});

test("attached project requires a sector and opens the selected sector layer for a planned file node", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  mkdirSync(path.join(source, "pkg"));
  const project = (await attach(page, "Sector context project", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);

  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Balíček");
  await page.getByRole("button", { name: "Navázat na existující zdroj" }).click();
  await page.getByRole("button", { name: "pkg", exact: true }).click();
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();

  await page.getByRole("button", { name: "+ Uzel" }).click();
  await page.getByLabel("Název uzlu").fill("Budoucí modul");
  const submit = page.getByRole("button", { name: "Vytvořit", exact: true });
  await expect(submit).toBeDisabled();
  await expect(page.getByText("Tento projekt vyžaduje sektor.")).toBeVisible();
  await page.getByLabel("Cílový sektor").selectOption({ label: "Balíček" });
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Druh navrhovaného zdroje").selectOption("file");
  await page.getByLabel("Podstata návrhu uzlu").fill("Připravovaný soubor modulu.");
  await expect(submit).toBeEnabled();
  await submit.click();

  await expect(page.getByRole("navigation", { name: "Cesta plátnem" }).getByText("Balíček", { exact: true })).toBeVisible();
  await expect(page.locator(".source-badge")).toContainText("Návrh zdroje");
  await expect(page.locator(".source-badge")).toContainText("soubor");
});

test("builtin graph-only draft still creates a free sector without a source proposal", async ({ page }) => {
  await page.goto("/?screen=canvas&project=draft&workspace=draft&mode=structure");
  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Volný sektor");
  const submit = page.getByRole("button", { name: "Vytvořit", exact: true });
  await expect(submit).toBeEnabled();
  await submit.click();
  const persisted = await page.evaluate(async () => (await fetch("/api/view?project=draft&workspace=draft")).json());
  expect(persisted.graph.nodes.find((node: { name: string }) => node.name === "Volný sektor").sourceRef).toBeUndefined();
});

test("planned source without a path is explicitly unspecified, not project root", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  const project = (await attach(page, "Unspecified proposal", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);
  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Budoucí oblast");
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Podstata návrhu sektoru").fill("Budoucí oblast s jasnou odpovědností.");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await expect(page.locator(".source-badge")).toContainText("cesta neurčena");
  await expect(page.locator(".source-badge")).not.toContainText("/");
});

test("planned node path is stored inside the selected sector", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  mkdirSync(path.join(source, "pkg"));
  const project = (await attach(page, "Scoped proposal", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);
  await page.getByRole("button", { name: "+ Sektor" }).click();
  await page.getByLabel("Název uzlu").fill("Balíček");
  await page.getByRole("button", { name: "Navázat na existující zdroj" }).click();
  await page.getByRole("button", { name: "pkg", exact: true }).click();
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await page.getByRole("button", { name: "+ Uzel" }).click();
  await page.getByLabel("Název uzlu").fill("Tajný návrh");
  await page.getByLabel("Cílový sektor").selectOption({ label: "Balíček" });
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Zamýšlená cesta").fill("other/secret.py");
  await page.getByLabel("Druh navrhovaného zdroje").selectOption("file");
  await page.getByLabel("Podstata návrhu uzlu").fill("Budoucí modul zůstává uvnitř balíčku.");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  const persisted = await page.evaluate(async (projectId) => (await fetch("/api/view?" + new URLSearchParams({ project: projectId, workspace: "draft" }))).json(), project.id);
  expect(persisted.graph.nodes.find((node: { name: string }) => node.name === "Tajný návrh").sourceRef.path).toBe("pkg/other/secret.py");
});

test("cross-layer creation uses the target sector's sibling coordinates", async ({ page }) => {
  const source = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  mkdirSync(path.join(source, "pkg"));
  mkdirSync(path.join(source, "other"));
  writeFileSync(path.join(source, "pkg", "existing.py"), "pass\n");
  const project = (await attach(page, "Coordinate project", source)) as { id: string };
  await page.goto(`/?screen=canvas&project=${project.id}&workspace=draft&mode=structure`);
  await page.evaluate(async (projectId) => {
    const view = await (await fetch("/api/view?" + new URLSearchParams({ project: projectId, workspace: "draft" }))).json();
    const graph = { nodes: [
      { id: "pkg", parentId: null, kind: "sector", name: "Balíček", purpose: "", x: 0, y: 0, sourceRef: { origin: "existing", path: "pkg", kind: "directory" } },
      { id: "other", parentId: null, kind: "sector", name: "Jiný", purpose: "", x: 310, y: 0, sourceRef: { origin: "existing", path: "other", kind: "directory" } },
      { id: "old", parentId: "pkg", kind: "node", name: "Starý", purpose: "", x: 0, y: 0, sourceRef: { origin: "existing", path: "pkg/existing.py", kind: "file" } },
    ], edges: [] };
    await fetch("/api/graph", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: projectId, workspace: "draft", digest: view.digest, graph }) });
  }, project.id);
  await page.reload();
  await page.getByRole("button", { name: "+ Uzel" }).click();
  await page.getByLabel("Název uzlu").fill("Nový");
  await page.getByLabel("Cílový sektor").selectOption({ label: "Balíček" });
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Podstata návrhu uzlu").fill("Nový uzel v cílovém sektoru.");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  const persisted = await page.evaluate(async (projectId) => (await fetch("/api/view?" + new URLSearchParams({ project: projectId, workspace: "draft" }))).json(), project.id);
  const created = persisted.graph.nodes.find((node: { name: string }) => node.name === "Nový");
  expect([created.x, created.y]).toEqual([310, 0]);
});

for (const { roundtrip, reject } of [{ roundtrip: false, reject: false }, { roundtrip: true, reject: false }, { roundtrip: false, reject: true }]) {
test(`a completed save cannot navigate a changed scope (roundtrip=${roundtrip}, reject=${reject})`, async ({ page }) => {
  const sourceA = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  const sourceB = mkdtempSync(path.join(tmpdir(), "opora-source-"));
  const projectA = (await attach(page, "Delayed project", sourceA)) as { id: string };
  const projectB = (await attach(page, "Current project", sourceB)) as { id: string };
  await page.goto(`/?screen=canvas&project=${projectA.id}&workspace=draft&mode=structure`);
  await page.evaluate(async (projectId) => {
    const view = await (await fetch("/api/view?" + new URLSearchParams({ project: projectId, workspace: "draft" }))).json();
    const graph = { nodes: [{ id: "sector-a", parentId: null, kind: "sector", name: "Původní", purpose: "Samostatný návrh původního projektu.", x: 0, y: 0, sourceRef: { origin: "planned", path: "", kind: "directory" } }], edges: [] };
    await fetch("/api/graph", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: projectId, workspace: "draft", digest: view.digest, graph }) });
  }, projectA.id);
  await page.goto(`/?screen=canvas&project=${projectA.id}&workspace=draft&mode=structure&layer=sector-a`);
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/graph", async (route) => {
    if (route.request().method() === "POST") {
      await pending;
      if (reject) return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: "STALE_OLD_SCOPE" }) });
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "+ Uzel" }).click();
  await page.getByLabel("Název uzlu").fill("Pozdní uzel");
  await page.getByRole("button", { name: "Navrhnout nové" }).click();
  await page.getByLabel("Podstata návrhu uzlu").fill("Uložení se vrátí po přepnutí rozsahu.");
  await page.getByRole("button", { name: "Vytvořit", exact: true }).click();
  await expect(page.getByText("Ukládám / ověřuji operaci…")).toBeVisible();
  await page.evaluate((projectId) => {
    const select = document.querySelector<HTMLSelectElement>('select[aria-label="Projekt"]')!;
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(select, projectId);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }, projectB.id);
  await expect(page.getByLabel("Projekt")).toHaveValue(projectB.id);
  if (roundtrip) {
    await page.evaluate((projectId) => {
      const select = document.querySelector<HTMLSelectElement>('select[aria-label="Projekt"]')!;
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(select, projectId);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }, projectA.id);
    await expect(page.getByLabel("Projekt")).toHaveValue(projectA.id);
    await expect(page).not.toHaveURL(/layer=sector-a/);
  }
  const completion = page.waitForResponse((response) => response.url().endsWith("/api/graph") && response.request().method() === "POST");
  release();
  await (await completion).finished();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByText("Ukládám / ověřuji operaci…")).toBeHidden();
  await expect(page).not.toHaveURL(/layer=sector-a/);
  await expect(page.getByText(/STALE_OLD_SCOPE/)).toBeHidden();
});
}

import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

function workflowUrl(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=workflow&${q}`;
}

function memoryUrl(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=memory&${q}`;
}

// Delays the next matching POST until the test releases it, so assertions can be made about
// in-flight state before the response resolves.
function interceptOneSave(page: Page, respond: (route: Route) => Promise<void>) {
  let handled = false;
  return page.route("**/api/desktop-v3/state", async (route) => {
    if (route.request().method() !== "POST" || handled) return route.continue();
    handled = true;
    await respond(route);
  });
}

test.describe("NodeWorkflowPanel: failed criterion save preserves draft", () => {
  test("409 conflict preserves the typed criterion text; retry then clears it", async ({ page }) => {
    const project = "proj-wf-draft-conflict";
    const workspace = "draft-a";
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let first = true;
    await page.route("**/api/desktop-v3/state", async (route) => {
      if (route.request().method() === "POST" && first) {
        first = false;
        await route.fulfill({ status: 409, json: { error: "Konflikt revizí; načtěte znovu." } });
        return;
      }
      await route.continue();
    });

    await page.getByLabel("Nové kritérium").fill("Nesmí zmizet po chybě");
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Konflikt revizí; načtěte znovu.");
    // Draft text must survive the failed save; no criterion was actually persisted.
    await expect(page.getByLabel("Nové kritérium")).toHaveValue("Nesmí zmizet po chybě");
    await expect(page.getByText("Nesmí zmizet po chybě", { exact: true }).and(page.locator("li *"))).toHaveCount(0);

    await page.getByRole("button", { name: "Znovu načíst", exact: true }).click();
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
    // Successful retry (using the still-present draft) both persists and clears the input.
    await expect(page.locator("li.v3-criterion")).toContainText("Nesmí zmizet po chybě");
    await expect(page.getByLabel("Nové kritérium")).toHaveValue("");
  });

  test("network/500 failure preserves step text and assignee together", async ({ page }) => {
    const project = "proj-wf-draft-500";
    const workspace = "draft-b";
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    await page.route("**/api/desktop-v3/state", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ status: 500, json: { error: "Interní chyba serveru." } });
        return;
      }
      await route.continue();
    });

    await page.getByLabel("Nový krok").fill("Krok co nesmí zmizet");
    await page.getByLabel("Přiřazení kroku").fill("builder-x");
    await page.getByRole("button", { name: "Přidat krok", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Interní chyba serveru.");
    await expect(page.getByLabel("Nový krok")).toHaveValue("Krok co nesmí zmizet");
    await expect(page.getByLabel("Přiřazení kroku")).toHaveValue("builder-x");
    await expect(page.getByText("Zatím žádné kroky.")).toBeVisible();
  });

  test("a pending add for node A does not clear a newly typed draft for node B after switching", async ({ page }) => {
    const project = "proj-wf-draft-scope";
    const workspace = "draft-c";
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await interceptOneSave(page, async (route) => {
      await gate;
      await route.continue();
    });

    await page.getByLabel("Nové kritérium").fill("Patří uzlu n1");
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();

    // Switch to node n2 via the hash (same mounted component, no full navigation) while the
    // n1 save is still in flight, then type a fresh draft meant for n2.
    await page.evaluate(() => {
      window.location.hash = "nodeId=n2";
    });
    await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
    await page.getByLabel("Nové kritérium").fill("Patří uzlu n2");

    release();
    // Give the n1 response time to resolve and (incorrectly, if buggy) clear the shared input.
    await page.waitForTimeout(300);
    await expect(page.getByLabel("Nové kritérium")).toHaveValue("Patří uzlu n2");

    // Switching back confirms n1's criterion was in fact saved (not silently dropped either).
    await page.evaluate(() => {
      window.location.hash = "nodeId=n1";
    });
    await expect(page.locator("li.v3-criterion")).toContainText("Patří uzlu n1");
  });

  test("rapid double Enter on the criterion input does not send two save requests", async ({ page }) => {
    const project = "proj-wf-draft-dup";
    const workspace = "draft-d";
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let posts = 0;
    await page.route("**/api/desktop-v3/state", async (route) => {
      if (route.request().method() === "POST") posts += 1;
      await route.continue();
    });

    const input = page.getByLabel("Nové kritérium");
    await input.fill("jen jednou");
    await input.press("Enter");
    await input.press("Enter");
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    expect(posts).toBe(1);
  });
});

test.describe("ProjectMemoryPanel: failed setting save preserves draft", () => {
  test("409 conflict preserves the new setting key/value; retry then clears it", async ({ page }) => {
    const project = "proj-mem-draft-conflict";
    const workspace = "draft-a";
    await page.goto(memoryUrl({ project, workspace, path: "" }));

    let first = true;
    await page.route("**/api/desktop-v3/state", async (route) => {
      if (route.request().method() === "POST" && first) {
        first = false;
        await route.fulfill({ status: 409, json: { error: "Konflikt revizí; načtěte znovu." } });
        return;
      }
      await route.continue();
    });

    await page.getByLabel("Klíč nového nastavení").fill("region");
    await page.getByLabel("Hodnota nového nastavení").fill("eu-central");
    await page.getByRole("button", { name: "Přidat nastavení", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Konflikt revizí; načtěte znovu.");
    await expect(page.getByLabel("Klíč nového nastavení")).toHaveValue("region");
    await expect(page.getByLabel("Hodnota nového nastavení")).toHaveValue("eu-central");
    await expect(page.getByText("Zatím žádná nastavení.")).toBeVisible();

    await page.getByRole("button", { name: "Znovu načíst", exact: true }).click();
    await page.getByRole("button", { name: "Přidat nastavení", exact: true }).click();
    await expect(page.getByText("region", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Klíč nového nastavení")).toHaveValue("");
    await expect(page.getByLabel("Hodnota nového nastavení")).toHaveValue("");
  });

  test("rapid double Enter on the decision input does not send two save requests", async ({ page }) => {
    const project = "proj-mem-draft-dup";
    const workspace = "draft-b";
    await page.goto(memoryUrl({ project, workspace, path: "" }));

    let posts = 0;
    await page.route("**/api/desktop-v3/state", async (route) => {
      if (route.request().method() === "POST") posts += 1;
      await route.continue();
    });

    const input = page.getByLabel("Nové rozhodnutí");
    await input.fill("jen jednou");
    await input.press("Enter");
    await input.press("Enter");
    await expect(page.locator("li.v3-decision")).toHaveCount(1);
    expect(posts).toBe(1);
  });
});

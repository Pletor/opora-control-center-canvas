import { test, expect } from "@playwright/test";

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=packet&${q}`;
}

test("sessionId defaults to empty (not a random nonce) for project/editor preview", async ({ page }) => {
  let sentSessionId: string | null = "not-called";
  await page.route("**/api/desktop-v3/packet/preview", async (route) => {
    const body = route.request().postDataJSON();
    sentSessionId = body.sessionId;
    await route.continue();
  });
  await page.goto(url({ project: "proj-pkt-session", workspace: "draft-a", nodeId: "n1", path: "" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  expect(sentSessionId).toBe("");
});

test("explicit sessionId prop is sent as the real scope, not a locally generated id", async ({ page }) => {
  let sentSessionId: string | null = "not-called";
  await page.route("**/api/desktop-v3/packet/preview", async (route) => {
    const body = route.request().postDataJSON();
    sentSessionId = body.sessionId;
    await route.continue();
  });
  await page.goto(url({ project: "proj-pkt-session-2", workspace: "draft-a", nodeId: "n1", path: "", sessionId: "run-abc-123" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  expect(sentSessionId).toBe("run-abc-123");
});

test("scope change on the SAME mounted component (A to B to A) invalidates stale in-flight preview", async ({ page }) => {
  const project = "proj-pkt-scope";
  const workspace = "draft-b";
  // Delay scope A's response so it resolves AFTER we've already navigated to B and back to A.
  let firstCall = true;
  await page.route("**/api/desktop-v3/packet/preview", async (route) => {
    const body = route.request().postDataJSON();
    if (body.nodeId === "node-a" && firstCall) {
      firstCall = false;
      await new Promise((r) => setTimeout(r, 400));
    }
    await route.continue();
  });

  await page.goto(url({ project, workspace, nodeId: "node-a", path: "", references: "[]" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click(); // slow request in flight for node-a

  // Switch to node-b on the SAME mounted component via hash change (no navigation/remount).
  await page.evaluate(() => {
    window.location.hash = "nodeId=node-b&path=&references=%5B%5D";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  await expect(page.getByText("Uzel node-b")).toBeVisible();

  // Switch back to node-a before the original slow response for node-a arrives.
  await page.evaluate(() => {
    window.location.hash = "nodeId=node-a&path=&references=%5B%5D";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  await expect(page.getByText("Uzel node-a")).toBeVisible();

  // The stale node-a response (from the FIRST click) must not populate this fresh node-a view.
  await page.waitForTimeout(600);
  await expect(page.getByText("Zdrojový manifest")).toHaveCount(0);
});

test("a new preview within the same scope does not remove an active run's stop control", async ({ page }) => {
  const project = "proj-pkt-run";
  const workspace = "draft-c";
  await page.goto(url({ project, workspace, nodeId: "n1", path: "", references: "[]" }));
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  await page.getByRole("button", { name: "Vytvořit neměnný snímek" }).click();
  await expect(page.getByText(/Snímek:/)).toBeVisible();
  await page.getByLabel("Zadání dokumentačního běhu").fill("Připravit shrnutí kontextu pro uzel n1.");
  await page.getByRole("button", { name: "Připravit dokumentační běh" }).click();
  await expect(page.getByText("Připraveno — model neběží")).toBeVisible();
  await page.getByLabel("Schvaluji spuštění dokumentačního běhu nad tímto snímkem").check();
  await page.getByRole("button", { name: "Potvrdit a spustit" }).click();
  await expect(page.getByText("Běží")).toBeVisible();

  // Build a fresh preview in the SAME scope — the active run's stop control must remain reachable.
  await page.getByRole("button", { name: "Sestavit náhled balíčku" }).click();
  await expect(page.getByText("Zdrojový manifest")).toBeVisible();
  await expect(page.getByRole("button", { name: "Zastavit běh" })).toBeVisible();
});

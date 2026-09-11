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

// Počítá POST na whole-state endpoint přímo ve stránce (synchronně při volání fetch), takže
// negativní tvrzení „žádný souběžný POST“ nezávisí na časování sítě ani na pevném čekání.
async function countStatePosts(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __statePosts: number };
    w.__statePosts = 0;
    const original = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
      if (url.includes("/api/desktop-v3/state") && method === "POST") w.__statePosts += 1;
      return original(input, init);
    };
  });
}

function statePosts(page: Page) {
  return page.evaluate(() => (window as unknown as { __statePosts: number }).__statePosts);
}

function isStatePost(response: { url(): string; request(): { method(): string } }) {
  return response.url().includes("/api/desktop-v3/state") && response.request().method() === "POST";
}

async function switchNode(page: Page, nodeId: string) {
  await page.evaluate((id) => {
    window.location.hash = `nodeId=${id}`;
  }, nodeId);
}

test.describe("NodeWorkflowPanel: whole-state saves are globally serialized", () => {
  test("held save for n1 blocks a concurrent save for n2; both persist across reload and a further mutation", async ({ page }) => {
    const project = "proj-wf-race-ok";
    const workspace = "race-a";
    await countStatePosts(page);
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await interceptOneSave(page, async (route) => {
      await gate;
      await route.continue();
    });

    await page.getByLabel("Nové kritérium").fill("A na n1");
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
    await expect.poll(() => statePosts(page)).toBe(1);

    await switchNode(page, "n2");
    await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
    const input = page.getByLabel("Nové kritérium");
    // Psaní konceptu pro jiný uzel musí jít i během rozpracovaného zápisu.
    await input.fill("B na n2");
    // Pokus o druhý whole-state zápis, zatímco A ještě visí. Obsluha keydown běží synchronně a
    // evaluate se vyhodnotí až po ní, takže počet je deterministický.
    await input.press("Enter");
    expect(await statePosts(page)).toBe(1);
    await expect(input).toHaveValue("B na n2");

    const aResponse = page.waitForResponse(isStatePost);
    release();
    expect((await aResponse).status()).toBe(200);
    const addButton = page.getByRole("button", { name: "Přidat kritérium", exact: true });
    // Tlačítko je během globálního zápisu zamčené; odemčení = A je usazené v UI.
    await expect(addButton).toBeEnabled();
    await expect(input).toHaveValue("B na n2");

    const bResponse = page.waitForResponse(isStatePost);
    await addButton.click();
    expect((await bResponse).status()).toBe(200);
    expect(await statePosts(page)).toBe(2);
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion")).toContainText("B na n2");
    await expect(input).toHaveValue("");

    // Server musí držet A i B (reload čte uložený stav, ne optimistický).
    await page.reload();
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion")).toContainText("B na n2");
    await switchNode(page, "n1");
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion")).toContainText("A na n1");

    // Další mutace nesmí tichou shodou revizí smazat A ani B.
    const toggleResponse = page.waitForResponse(isStatePost);
    await page.locator("li.v3-criterion input[type=checkbox]").check();
    expect((await toggleResponse).status()).toBe(200);
    await page.reload();
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion input[type=checkbox]")).toBeChecked();
    await switchNode(page, "n2");
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion")).toContainText("B na n2");
  });

  test("failed held save for n1 is not persisted piggyback via the next successful save for n2", async ({ page }) => {
    const project = "proj-wf-race-fail";
    const workspace = "race-b";
    await countStatePosts(page);
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await interceptOneSave(page, async (route) => {
      await gate;
      await route.fulfill({ status: 500, json: { error: "Interní chyba serveru." } });
    });

    await page.getByLabel("Nové kritérium").fill("A selže");
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();
    await expect.poll(() => statePosts(page)).toBe(1);

    await switchNode(page, "n2");
    await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
    const input = page.getByLabel("Nové kritérium");
    await input.fill("B projde");
    await input.press("Enter");
    expect(await statePosts(page)).toBe(1);

    const aResponse = page.waitForResponse(isStatePost);
    release();
    expect((await aResponse).status()).toBe(500);
    await expect(page.getByRole("alert")).toContainText("Interní chyba serveru.");
    const addButton = page.getByRole("button", { name: "Přidat kritérium", exact: true });
    await expect(addButton).toBeEnabled();
    await expect(input).toHaveValue("B projde");

    const bResponse = page.waitForResponse(isStatePost);
    await addButton.click();
    expect((await bResponse).status()).toBe(200);
    expect(await statePosts(page)).toBe(2);

    await page.reload();
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
    await expect(page.locator("li.v3-criterion")).toContainText("B projde");
    await switchNode(page, "n1");
    // Neúspěšné A nesmí být na serveru uložené přes úspěšné B.
    await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
    await expect(page.locator("li.v3-criterion")).toHaveCount(0);
  });
});

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

    const aResponse = page.waitForResponse(isStatePost);
    release();
    expect((await aResponse).status()).toBe(200);
    // Místo pevného čekání: přidávací tlačítko je během globálního zápisu zamčené a odemkne se až
    // v renderu, který usadil odpověď n1 (včetně případného mazání konceptu).
    await expect(page.getByRole("button", { name: "Přidat kritérium", exact: true })).toBeEnabled();
    await expect(page.getByLabel("Nové kritérium")).toHaveValue("Patří uzlu n2");

    // Switching back confirms n1's criterion was in fact saved (not silently dropped either).
    await page.evaluate(() => {
      window.location.hash = "nodeId=n1";
    });
    await expect(page.locator("li.v3-criterion")).toContainText("Patří uzlu n1");
  });

  test("A→B→A: late success for n1 keeps a draft newly typed on n2 and still shown on n1", async ({ page }) => {
    const project = "proj-wf-draft-aba";
    const workspace = "draft-e";
    await page.goto(workflowUrl({ project, workspace, nodeId: "n1" }));

    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await interceptOneSave(page, async (route) => {
      await gate;
      await route.continue();
    });

    await page.getByLabel("Nové kritérium").fill("Odesláno z n1");
    await page.getByRole("button", { name: "Přidat kritérium", exact: true }).click();

    await switchNode(page, "n2");
    await expect(page.getByText("Zatím žádná kritéria.")).toBeVisible();
    await page.getByLabel("Nové kritérium").fill("Novější koncept");
    await switchNode(page, "n1");
    await expect(page.locator("li.v3-criterion")).toContainText("Odesláno z n1");

    const aResponse = page.waitForResponse(isStatePost);
    release();
    expect((await aResponse).status()).toBe(200);
    // Zaškrtávátko je během zápisu zamčené; odemčení = render, který usadil odpověď n1.
    await expect(page.locator("li.v3-criterion input[type=checkbox]")).toBeEnabled();
    // Scope je opět n1, ale koncept je novější než odeslaný – nesmí být smazán.
    await expect(page.getByLabel("Nové kritérium")).toHaveValue("Novější koncept");
    await expect(page.locator("li.v3-criterion")).toHaveCount(1);
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

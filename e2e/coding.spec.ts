import { test, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";

test("coding workspace selection and preview do not run a provider", async ({ page }) => {
  let starts = 0; page.on("request", r => { if (r.url().endsWith("/api/coding/start")) starts++; });
  await page.goto("/");
  await page.getByLabel("Schvaluji oddělený testovací repozitář").check();
  await page.getByRole("button", { name: "Vytvořit testovací repo", exact: true }).click();
  await expect(page.getByTestId("coding-target")).toContainText("work/");
  await page.getByRole("button", { name: "Náhled coding kontextu", exact: true }).click();
  await expect(page.getByTestId("coding-preview")).toContainText("coding_sandbox");
  expect(starts).toBe(0);
});

test("LIVE: UI to Hermes to isolated repo to independent Docker tests", async ({ page }) => {
  test.skip(process.env.OPORA_LIVE_ACCEPTANCE !== "1", "Explicit opt-in for one bounded provider run");
  test.setTimeout(240000);
  await page.goto("/");
  await page.getByLabel("Cíl projektu", { exact: true }).fill("Implementovat add(a,b) a prokázat skutečný coding běh z uloženého kontextu Canvasu.");
  await page.getByLabel("Model", { exact: true }).fill("gpt-6-astra");
  await page.getByRole("button", { name: "Uložit nastavení projektu", exact: true }).click();
  await expect(page.getByTestId("project-settings-status")).toContainText("Uloženo");
  await page.getByLabel("Schvaluji oddělený testovací repozitář").check();
  await page.getByRole("button", { name: "Vytvořit testovací repo", exact: true }).click();
  await expect(page.getByTestId("coding-target")).toContainText("work/");
  await page.getByRole("button", { name: "Náhled coding kontextu", exact: true }).click();
  await expect(page.getByTestId("coding-preview")).toContainText("coding_sandbox");
  const started = page.waitForResponse(r => r.url().endsWith("/api/coding/start"));
  await page.getByRole("button", { name: "Potvrdit a spustit coding agenta", exact: true }).click();
  const response = await started;
  expect(response.status()).toBe(200);
  const initial = await response.json();
  let record: any;
  try {
    await expect.poll(async () => {
      const data = await (await page.request.get("/api/coding/runs")).json();
      record = data.runs.find((r: any) => r.id === initial.id);
      return record?.status;
    }, { timeout: 205000, intervals: [1000] }).toMatch(/^(completed|failed|stopped_local)$/);
    writeFileSync(".opora/workunits/WU-CANVAS-COMPLETION/live-run.json", JSON.stringify(record, null, 2));
    expect(record.status).toBe("completed");
    expect(record.result.verified).toBe(true);
    expect(record.result.tests.exitCode).toBe(0);
    expect(record.result.diff).toContain("return a + b");
    expect(record.events.some((e: any) => e.kind === "file_written")).toBe(true);
    await expect(page.getByTestId("coding-run").filter({ hasText: initial.id })).toContainText("completed");
    await page.screenshot({ path: "evidence/coding-live.png", fullPage: true });
  } finally {
    const result = await page.request.post("/api/coding/stop", { headers: { origin: "http://127.0.0.1:8741" }, data: { project: initial.project, runId: initial.id, confirmed: true } });
    writeFileSync(".opora/workunits/WU-CANVAS-COMPLETION/live-stop.json", JSON.stringify(await result.json(), null, 2));
  }
});

import { test, expect } from "@playwright/test";

function url(params: Record<string, string>) {
  const q = new URLSearchParams(params).toString();
  return `/?panel=live&${q}`;
}

test("pressing digit 5 while the live panel has body focus switches to the 5th detail tab", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-basic", workspace: "draft-kbd-basic" }));
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("5");
  await expect(page.getByRole("tab", { name: "5 Ovládání" })).toHaveAttribute("aria-selected", "true");
});

test("pressing a tab button directly with the mouse still works and digit 1 restores the first tab afterwards", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-click", workspace: "draft-kbd-click" }));
  await page.getByRole("tab", { name: "3 Náklady a výkon" }).click();
  await expect(page.getByRole("tab", { name: "3 Náklady a výkon" })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("1");
  await expect(page.getByRole("tab", { name: "1 Události" })).toHaveAttribute("aria-selected", "true");
});

test("typing a digit into the session search field does not change the active tab", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-search", workspace: "draft-kbd-search" }));
  const search = page.getByLabel("Hledat v bězích a ticketech");
  await search.click();
  await search.pressSequentially("5");
  await expect(search).toHaveValue("5");
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: "5 Ovládání" })).toHaveAttribute("aria-selected", "false");
});

test("typing a digit into the new-ticket title field does not change the active tab", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-ticket", workspace: "draft-kbd-ticket" }));
  await page.getByRole("tab", { name: "6 Tickety" }).click();
  const title = page.getByLabel("Název nového ticketu");
  await title.click();
  await title.pressSequentially("5");
  await expect(title).toHaveValue("5");
  await expect(page.getByRole("tab", { name: "6 Tickety" })).toHaveAttribute("aria-selected", "true");
});

test("typing a digit into the disabled side-thread textarea does not change the active tab", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-textarea", workspace: "draft-kbd-textarea" }));
  await page.evaluate(() => {
    const el = document.querySelector<HTMLTextAreaElement>("textarea");
    if (el) {
      el.disabled = false;
      el.focus();
    }
  });
  await page.keyboard.press("5");
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
});

test("digit keys combined with Alt, Ctrl, Meta or Shift do not change the active tab", async ({ page }) => {
  await page.goto(url({ project: "proj-kbd-modifiers", workspace: "draft-kbd-modifiers" }));
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
  for (const modifier of ["Alt", "Control", "Meta", "Shift"]) {
    await page.keyboard.press(`${modifier}+5`);
  }
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: "5 Ovládání" })).toHaveAttribute("aria-selected", "false");
});

test("digit navigation across all seven tabs issues no write/model-start requests", async ({ page }) => {
  const project = "proj-kbd-nowrite";
  const workspace = "draft-kbd-nowrite";
  const writes: string[] = [];
  await page.goto(url({ project, workspace }));
  await expect(page.getByRole("tab", { name: "2 Důkazy a výstup" })).toHaveAttribute("aria-selected", "true");
  page.on("request", (r) => {
    if (r.method() === "POST") writes.push(r.url());
  });
  for (const digit of ["1", "2", "3", "4", "5", "6", "7"]) {
    await page.keyboard.press(digit);
    await expect(page.getByRole("tab", { name: new RegExp(`^${digit} `) })).toHaveAttribute("aria-selected", "true");
  }
  expect(writes).toEqual([]);
});

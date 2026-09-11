import { test, expect, type Page } from "@playwright/test";

/**
 * Nativní inspektor vybraného tvaru (Excalidraw) nesmí přebírat obecné OPORA styly
 * tlačítek a polí; OPORA ovládání mimo vendor strom si je naopak ponechává.
 */
const panel = (page: Page) => page.locator(".excalidraw .App-menu__left").first();

async function drawRectangle(page: Page) {
  await page.getByRole("button", { name: "Nástroj: Obdélník", exact: true }).click();
  const canvas = page.getByTestId("drawing-surface").locator("canvas.interactive");
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + 280, box.y + 110);
  await page.mouse.down();
  await page.mouse.move(box.x + 440, box.y + 220, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
}

async function selectRectangle(page: Page) {
  await page.getByRole("button", { name: "Nástroj: Výběr", exact: true }).click();
  const box = (await page.getByTestId("drawing-surface").locator("canvas.interactive").boundingBox())!;
  await page.mouse.click(box.x + 280, box.y + 165);
  await expect(panel(page).locator(".color-picker__button").first()).toBeVisible();
}

async function setTheme(page: Page, label: "Světlý" | "Tmavý") {
  await page.getByRole("button", { name: "Vzhled", exact: true }).click();
  await page.getByRole("group", { name: "Vzhled rozhraní" }).getByRole("button", { name: label, exact: true }).click();
  await page.keyboard.press("Escape");
}

async function expectNativeInspector(page: Page, context: string) {
  const state = await panel(page).evaluate((root) => {
    const rect = (e: Element) => e.getBoundingClientRect();
    const host = root.closest(".excalidraw")!;
    const swatches = [...root.querySelectorAll(".color-picker__button")].filter((e) => rect(e).width > 0).map((e) => {
      const r = rect(e), css = getComputedStyle(e);
      return { w: r.width, h: r.height, minHeight: css.minHeight, padding: css.padding };
    });
    const range = root.querySelector('input[type="range"]')!;
    const rangeCss = getComputedStyle(range);
    const sections = [...root.querySelectorAll("fieldset, .panelColumn > *")].map(rect).filter((r) => r.height > 0);
    const overlaps = sections.some((a, i) => sections.slice(i + 1).some((b) => a.bottom - 1 > b.top && b.bottom - 1 > a.top && a.right - 1 > b.left && b.right - 1 > a.left && !(a.top <= b.top && a.bottom >= b.bottom) && !(b.top <= a.top && b.bottom >= a.bottom)));
    const p = rect(root), h = rect(host);
    return {
      swatches,
      range: { h: rect(range).height, minHeight: rangeCss.minHeight, padding: rangeCss.padding, border: rangeCss.borderTopWidth },
      overlaps,
      inside: p.top >= h.top - 1 && p.bottom <= Math.min(h.bottom, innerHeight) + 1 && p.left >= h.left - 1,
      scrollable: root.scrollHeight <= root.clientHeight + 1 || ["auto", "scroll"].includes(getComputedStyle(root).overflowY) || [...root.querySelectorAll("*")].some((e) => ["auto", "scroll"].includes(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight),
    };
  });
  expect(state.swatches.length, context).toBeGreaterThan(4);
  for (const s of state.swatches) {
    expect(Math.abs(s.w - s.h), `${context}: square swatch ${JSON.stringify(s)}`).toBeLessThanOrEqual(1);
    expect(s.h, `${context}: native swatch size ${JSON.stringify(s)}`).toBeLessThan(28);
    expect(s.minHeight, context).not.toBe("32px");
  }
  expect(state.range.h, `${context}: native range ${JSON.stringify(state.range)}`).toBeLessThanOrEqual(8);
  expect(state.range.minHeight, context).not.toBe("32px");
  expect(state.range.padding, context).not.toBe("7px 9px");
  expect(state.range.border, context).toBe("0px");
  expect(state.overlaps, `${context}: overlapping native sections`).toBe(false);
  expect(state.inside, `${context}: native panel clipped`).toBe(true);
  expect(state.scrollable, `${context}: native panel content unreachable`).toBe(true);
}

async function expectNativePopover(page: Page, context: string) {
  await panel(page).locator(".color-picker__button.active-color").first().click();
  const popover = page.locator(".color-picker-content").first();
  await expect(popover).toBeVisible();
  const state = await popover.evaluate((root) => ({
    inVendor: !!root.closest(".excalidraw"),
    swatches: [...root.querySelectorAll(".color-picker__button")].map((e) => { const r = e.getBoundingClientRect(); return { w: r.width, h: r.height, minHeight: getComputedStyle(e).minHeight }; }),
  }));
  expect(state.inVendor, context).toBe(true);
  expect(state.swatches.length, context).toBeGreaterThan(4);
  for (const s of state.swatches) {
    expect(Math.abs(s.w - s.h), `${context}: popover swatch ${JSON.stringify(s)}`).toBeLessThanOrEqual(1);
    expect(s.minHeight, context).not.toBe("32px");
  }
  await page.keyboard.press("Escape");
  await expect(popover).toBeHidden();
}

async function expectOporaControls(page: Page, context: string) {
  for (const control of [
    page.getByRole("button", { name: "Uložit kresbu", exact: true }),
    page.getByRole("button", { name: "Nástroj: Obdélník", exact: true }),
  ]) {
    await expect(control).toBeVisible();
    const css = await control.evaluate((e) => ({ minHeight: getComputedStyle(e).minHeight, h: e.getBoundingClientRect().height }));
    expect(css.minHeight, context).toBe("32px");
    expect(css.h, context).toBeGreaterThanOrEqual(31.5);
  }
  // Pole mimo vendor strom dál nese obecný OPORA rámeček (výšku 30px a padding si select horní lišty určuje sám).
  const field = page.locator("select:not(.excalidraw *)").first();
  await expect(field).toBeVisible();
  const css = await field.evaluate((e) => { const s = getComputedStyle(e); return { border: s.borderTopWidth, radius: s.borderTopLeftRadius, minHeight: s.minHeight }; });
  expect(css.border, context).toBe("1px");
  expect(css.radius, context).not.toBe("0px");
  expect(parseFloat(css.minHeight), context).toBeGreaterThanOrEqual(30);
}

for (const width of [1280, 1440]) {
  test(`native drawing inspector keeps vendor layout without Wireframe at ${width}px`, async ({ page }) => {
    const errors: string[] = [];
    const external: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.protocol.startsWith("http") && url.origin !== "http://127.0.0.1:8742") {
        external.push(url.href);
        return route.abort();
      }
      return route.continue();
    });
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?mode=drawing");
    const before = await (await page.request.get("/api/view")).json();
    await expect(page.getByTestId("drawing-surface")).toBeVisible();
    await drawRectangle(page);
    const wireframe = page.getByRole("checkbox", { name: "Wireframe" });
    await expect(wireframe).not.toBeChecked();

    for (const theme of ["Světlý", "Tmavý"] as const) {
      await setTheme(page, theme);
      await selectRectangle(page);
      await expectNativeInspector(page, `${width} ${theme} wireframe off`);
      await expectNativePopover(page, `${width} ${theme} popover`);
      await expectOporaControls(page, `${width} ${theme} OPORA`);
      await wireframe.check();
      await expect(page.locator(".wireframe-sidecar")).toBeVisible();
      await wireframe.uncheck();
      await expect(page.locator(".wireframe-sidecar")).toHaveCount(0);
      await selectRectangle(page);
      await expectNativeInspector(page, `${width} ${theme} wireframe toggled back off`);
      await expectOporaControls(page, `${width} ${theme} OPORA after toggle`);
    }
    await page.screenshot({ path: `evidence/inspector-style-boundary-${width}.png` });
    await setTheme(page, "Světlý");
    await expect(page.getByTestId("drawing-element-count")).toHaveText("1");
    expect((await (await page.request.get("/api/view")).json()).digest).toBe(before.digest);
    expect(external).toEqual([]);
    expect(errors).toEqual([]);
  });
}

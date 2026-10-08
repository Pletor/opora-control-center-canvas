import { expect, it, vi } from "vitest";
import { drainHistoryPages } from "./history-pagination";

it("Načíst vše dojde přes tři stránky výsledků a zpráv až k poslednímu záznamu", async () => {
  const fetchPage = vi.fn(async (before: number) => ({ next: before === 1 ? null : before - 1, items: [`result-${before}`, `message-${before}`] }));
  const rows: string[] = [];
  await drainHistoryPages(3 as number, fetchPage, page => rows.push(...page.items), () => true);
  expect(fetchPage.mock.calls.map(([before]) => before)).toEqual([3, 2, 1]);
  expect(rows).toEqual(["result-3", "message-3", "result-2", "message-2", "result-1", "message-1"]);
});
it("chyba další stránky nezahodí předchozí data ani nepředstírá dokončení", async () => {
  const rows: number[] = [];
  await expect(drainHistoryPages(3, async before => { if (before === 2) throw new Error("HTTP 500"); return { next: 2, item: 3 }; }, page => rows.push(page.item), () => true)).rejects.toThrow("HTTP 500");
  expect(rows).toEqual([3]);
});
it("po odmountování nepřipojí opožděnou odpověď", async () => {
  let active = true; const append = vi.fn();
  await drainHistoryPages(1, async () => { active = false; return { next: null }; }, append, () => active);
  expect(append).not.toHaveBeenCalled();
});
it("zastaví i cyklus kurzorů přes více stránek", async () => {
  const read = vi.fn(async (before: number) => ({ next: before === 1 ? 2 : 1 }));
  await expect(drainHistoryPages(1 as number, read, () => {}, () => true)).rejects.toThrow("Kurzor");
  expect(read).toHaveBeenCalledTimes(2);
});

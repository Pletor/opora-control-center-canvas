import { expect, it } from "vitest";
import type { DnaTimelineItem } from "./dna-history";
import { localTimelinePage, TIMELINE_LOCAL_BATCH_SIZE } from "./process-pagination";

const row = (index: number): DnaTimelineItem => ({
  at: new Date(Date.UTC(2026, 9, 9, 0, 0, index)).toISOString(), group: "Ověření", label: `run-${String(index).padStart(3, "0")}`, source: `run-${index}`,
});

it("zpřístupní i 101. událost další lokální dávkou bez serverového požadavku", () => {
  const rows = Array.from({ length: 101 }, (_, index) => row(index));
  const first = localTimelinePage(rows, TIMELINE_LOCAL_BATCH_SIZE);
  const expanded = localTimelinePage(rows, TIMELINE_LOCAL_BATCH_SIZE * 2);
  expect(first.rows).toHaveLength(100);
  expect(first.rows[0]?.label).toBe("run-001");
  expect(first.hasOlderLocal).toBe(true);
  expect(expanded.rows).toHaveLength(101);
  expect(expanded.rows[0]?.label).toBe("run-000");
  expect(expanded.hasOlderLocal).toBe(false);
});

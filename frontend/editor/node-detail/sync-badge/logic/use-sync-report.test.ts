import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { shouldFetchSyncReport, syncReportKey } from "./use-sync-report";

describe("sync-report mimo nečinnost", () => {
  it("vypnuté čtení nesahá na síť", () => {
    expect(shouldFetchSyncReport(false, "p", "draft", 0, null)).toBe(false);
  });

  it("bez projektu nebo prostoru nic nenačte", () => {
    expect(shouldFetchSyncReport(true, "", "draft", 0, null)).toBe(false);
    expect(shouldFetchSyncReport(true, "p", "", 0, null)).toBe(false);
  });

  it("první otevření načte, opakované otevření bez změny ne", () => {
    expect(shouldFetchSyncReport(true, "p", "draft", 0, null)).toBe(true);
    expect(shouldFetchSyncReport(true, "p", "draft", 0, syncReportKey("p", "draft", 0))).toBe(false);
  });

  it("refresh, jiný projekt i jiný prostor načtou znovu", () => {
    const last = syncReportKey("p", "draft", 0);
    expect(shouldFetchSyncReport(true, "p", "draft", 1, last)).toBe(true);
    expect(shouldFetchSyncReport(true, "q", "draft", 0, last)).toBe(true);
    expect(shouldFetchSyncReport(true, "p", "ws", 0, last)).toBe(true);
  });

  it("App čte report jen s otevřeným detailem OporaHubu", () => {
    const app = readFileSync(new URL("../../../../app/components/App.tsx", import.meta.url), "utf8");
    expect(app).toMatch(/useSyncReport\(project, workspace, hubDetail\)/);
    expect(app).not.toMatch(/useSyncReport\(project, workspace\)/);
  });
});

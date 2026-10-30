import { describe, expect, it } from "vitest";
import { prBadge } from "./pr-badge";

describe("odznak PR", () => {
  it("sloučené PR na neuzavřené kartě je fialové s číslem", () => {
    expect(prBadge("merge", "awaiting_human_close", { number: 191, state: "merged" }, false))
      .toEqual({ tone: "merged", label: "Sloučeno · PR #191" });
  });

  it("otevřené PR je zelené, zavřené bez sloučení červené", () => {
    expect(prBadge("pull_request", "pull_requests_open", { number: 7, state: "open" }, false))
      .toEqual({ tone: "open", label: "PR #7 otevřené" });
    expect(prBadge("review", "review_gate_pending", { number: 7, state: "open" }, false))
      .toEqual({ tone: "open", label: "PR #7 otevřené" });
    expect(prBadge("review", "human_review_required", { number: 8, state: "closed" }, false))
      .toEqual({ tone: "closed", label: "PR #8 zavřené bez sloučení" });
  });

  it("uzavřená karta odznak nemá", () => {
    expect(prBadge("plan_writeback", "card_closed", { number: 3, state: "merged" }, false)).toBeNull();
    expect(prBadge("merge", "awaiting_human_close", { number: 3, state: "merged" }, true)).toBeNull();
  });

  it("bez PR nic; lokální sloučení bez čísla; starší server bez `pr` podle etapy", () => {
    expect(prBadge("work", "runs_active", null, false)).toBeNull();
    expect(prBadge("plan_writeback", "plan_written_back", { number: null, state: "merged" }, false))
      .toEqual({ tone: "merged", label: "Sloučeno" });
    expect(prBadge("merge", "awaiting_human_close", undefined, false)).toEqual({ tone: "merged", label: "Sloučeno" });
    expect(prBadge("pull_request", "pull_requests_open", undefined, false)).toEqual({ tone: "open", label: "PR otevřené" });
  });
});

import { describe, expect, it } from "vitest";
import { riskReasonLabel, blockedReasonLabel } from "./review-labels";

describe("server evidence labels", () => {
  it("explains known adoption and control reasons without changing raw evidence", () => {
    expect(riskReasonLabel("first_content_manifest_adoption")).toContain("celý výchozí obsah");
    expect(riskReasonLabel("control_field_changed:rules")).toContain("pravidla");
    expect(riskReasonLabel("control_field_changed:downloadsUrl")).toContain("stahuje URL");
  });
  it("names the required corrective action for stale, blocking and missing ACK", () => {
    expect(blockedReasonLabel("Proposal has a stale accepted parent; rebase it explicitly.")).toContain("převeďte");
    expect(blockedReasonLabel("Open blocking findings require a human resolution.")).toContain("člověk");
    expect(blockedReasonLabel("Current human acknowledgement of this proposal, policy and review head is required.")).toContain("Chybí aktuální lidské potvrzení");
  });
  it("preserves unknown reasons visibly", () => {
    expect(riskReasonLabel("future_classification")).toContain("future_classification");
    expect(blockedReasonLabel("Unknown server reason")).toBe("Unknown server reason");
  });
});

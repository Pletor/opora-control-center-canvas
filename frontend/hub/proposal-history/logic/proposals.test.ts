import { describe, expect, it } from "vitest";
import { ProposalRequests, diffValue, proposalPayload } from "./proposals";

describe("proposal request lifecycle", () => {
  it("rejects an old scope response even when the user returns to the same scope", () => {
    const requests = new ProposalRequests();
    const old = requests.next();
    requests.invalidate();
    const current = requests.next();
    expect(old()).toBe(false);
    expect(current()).toBe(true);
  });
  it("only accepts the latest refresh and cancels completion after unmount", () => {
    const requests = new ProposalRequests();
    const first = requests.next();
    const second = requests.next();
    expect(first()).toBe(false);
    expect(second()).toBe(true);
    requests.invalidate();
    expect(second()).toBe(false);
  });
  it("submits the observed assignment without inventing an empty head or content", () => {
    const context = { head: "observed-head", contextVersion: "observed-context", specRevision: 3 };
    const payload = proposalPayload("p", "draft", "n", "  Reason  ", context);
    context.head = "changed-after-capture";
    expect(payload).toEqual({ project: "p", workspace: "draft", scope: "n", subject: "Reason",
      expectedHead: "observed-head", expectedContextVersion: "observed-context" });
    expect(proposalPayload("p", "draft", "n", "Reason", { ...context, head: null }).expectedHead).toBeNull();
  });
});

describe("historical values", () => {
  it("distinguishes deleted, null, false, zero and empty values", () => {
    expect([undefined, null, false, 0, ""].map(diffValue)).toEqual(["—", "null", "false", "0", ""]);
  });
  it("renders nested changes without losing array order", () => {
    expect(diffValue({ ids: ["b", "a"] })).toBe('{\n  "ids": [\n    "b",\n    "a"\n  ]\n}');
  });
});

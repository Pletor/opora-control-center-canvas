import { describe, expect, it, vi } from "vitest";
import { ContentRequests, contentAction, contentAcknowledgement, contentDetailUrl, contentValue } from "./content-changes";
import { parseContentDetail, parseContentList, parseContentProposal, parseContentRebase } from "./content-parse";
import { contentScope, contentDetail, contentList, contentProposal } from "./content-fixtures";
import { postContent } from "./content-api";

describe("content review boundaries", () => {
  it("parses bounded exact scoped records and rejects fallback identities and unknown schemas", () => {
    expect(parseContentList(contentList()).items).toHaveLength(1);
    expect(parseContentDetail(contentDetail(), contentScope, contentProposal().id).proposal.id).toBe(contentProposal().id);
    for (const mutation of [{ schemaVersion: 2 }, { workspace: "other" }, { id: "e".repeat(40) },
      { changes: [] }, { changes: [...contentProposal().changes, ...contentProposal().changes] }])
      expect(() => parseContentProposal({ ...contentProposal(), ...mutation }, contentScope, contentProposal().id)).toThrow();
    expect(() => parseContentList({ ...contentList(), items: Array(101).fill(contentList().items[0]) })).toThrow();
    expect(() => contentDetailUrl(contentScope, "../fallback")).toThrow();
  });
  it("requires human capability, exact common head and exact whole-baseline acknowledgement", () => {
    const detail = contentDetail(), list = contentList();
    expect(() => contentAction(contentScope, list, detail, "accept", "")).toThrow(/celý/);
    expect(contentAction(contentScope, list, detail, "accept", contentAcknowledgement(detail.proposal))).toEqual({ ...contentScope,
      expectedAcceptedHead: list.acceptedHead, reviewedProposalId: detail.proposal.id, adoptBaseContentDigest: detail.proposal.baseContentDigest });
    for (const patch of [{ canAccept: false }, { readOnly: true }, { acceptedHead: "e".repeat(40) }])
      expect(() => contentAction(contentScope, { ...list, ...patch }, detail, "accept", contentAcknowledgement(detail.proposal))).toThrow();
    expect(contentAction(contentScope, list, detail, "rebase", "")).toEqual({ ...contentScope, expectedAcceptedHead: list.acceptedHead });
  });
  it("retains explicit conflicts and accepts only a validated replacement proposal", () => {
    const conflict = { proposal: null, rebased: false, conflicts: [{ kind: "text", target: "card", field: "text", reason: "Source changed" }] };
    expect(parseContentRebase(conflict, contentScope).proposal).toBeNull();
    expect(parseContentRebase({ proposal: contentProposal(), rebased: true, conflicts: [] }, contentScope).proposal?.id).toBe(contentProposal().id);
    expect(() => parseContentRebase({ ...conflict, rebased: true }, contentScope)).toThrow();
    expect(() => parseContentRebase({ ...conflict, conflicts: [] }, contentScope)).toThrow();
  });
  it("downloadsUrl is a boolean flag and never a URL string", () => {
    const original = contentProposal();
    for (const value of [true, false, null]) {
      const changes = [{ ...original.changes[0], kind: "config", field: "downloadsUrl", value, observedRevision: undefined }];
      expect(parseContentProposal({ ...original, changes }, contentScope).changes[0].value).toBe(value);
    }
    for (const value of ["https://example.test", 1, {}])
      expect(() => parseContentProposal({ ...original, changes: [{ ...original.changes[0], kind: "config", field: "downloadsUrl", value }] }, contentScope)).toThrow();
  });
  it("fences late promises immediately on scope/ID changes and serializes writes", async () => {
    const requests = new ContentRequests(); requests.context("scope/one");
    const valid = requests.next();
    let settle!: () => void;
    const old = new Promise<void>(resolve => { settle = resolve; }).then(() => valid());
    requests.context("scope/two"); settle();
    expect(await old).toBe(false);
    const write = requests.beginWrite()!; expect(requests.beginWrite()).toBeNull();
    requests.context("scope/two/other-id"); expect(write()).toBe(false);
    requests.endWrite(); expect(requests.beginWrite()).toBeTypeOf("function");
  });
  it("never retries uncertain mutation and renders explicit shortened previews", async () => {
    const transport = vi.fn().mockResolvedValueOnce(Response.json({ ok: true })).mockRejectedValueOnce(new Error("Uncertain"));
    await expect(postContent("/content/id/accept", { reviewedProposalId: "exact" }, transport)).rejects.toThrow("Uncertain");
    expect(transport).toHaveBeenCalledTimes(2);
    expect(contentValue("a".repeat(9000)).preview).toContain("Zobrazení zkráceno");
    expect(contentValue("a".repeat(9000)).full).toHaveLength(9000);
  });
});

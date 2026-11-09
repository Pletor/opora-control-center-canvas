import { expect, it, vi } from "vitest";
import { proposeStoryboard, storyboardReviewLink } from "./storyboard-proposal";
import { contentList, contentProposal, contentScope } from "@/hub/content-changes/logic/content-fixtures";

const board = { schema: "opora.storyboard/1", title: "Login", moments: [{ id: "m-12345678", t: 0 }], revision: 7 };
function proposal(revision = 7) {
  return { ...contentProposal(), changes: [{ kind: "storyboard", target: "card", field: "storyboard", value: board,
    before: { revision: 7, moments: board.moments, title: "Login", schema: board.schema }, acceptedBefore: null,
    observedOwner: "work", observedRevision: revision, observedRound: null }] };
}
it("proposes exactly the saved source through existing content API and links the existing scoped review", async () => {
  const calls: { url: string; body?: object }[] = [];
  const api = vi.fn(async (url: string, body?: object) => {
    calls.push({ url, body });
    return url.startsWith("/api/storyboard?") ? { revision: 7, storyboard: board } : body ? proposal() : contentList();
  });
  const result = await proposeStoryboard(contentScope, "card", 7, api as never);
  expect(result.id).toBe(contentProposal().id);
  expect(calls[2].body).toMatchObject({ ...contentScope, expectedAcceptedHead: contentList().acceptedHead,
    changes: [{ kind: "storyboard", target: "card", field: "storyboard", value: board }] });
  expect(calls.some(call => call.url.endsWith("/accept"))).toBe(false);
  const link = new URL(storyboardReviewLink(contentScope, result.id), "https://opora.test");
  expect(link.searchParams.get("environment")).toBe("hub");
  expect(link.searchParams.get("ohContent")).toBe(result.id);
  expect(link.searchParams.get("workspace")).toBe("work");
});

it("does not propose stale locally displayed revisions and rejects a race discovered in returned preconditions", async () => {
  const read = vi.fn(async () => ({ revision: 8, storyboard: board }));
  await expect(proposeStoryboard(contentScope, "card", 7, read as never)).rejects.toThrow("změnil");
  expect(read).toHaveBeenCalledTimes(1);
  const raced = vi.fn(async (url: string, body?: object) => url.startsWith("/api/storyboard?")
    ? { revision: 7, storyboard: board } : body ? proposal(8) : contentList());
  await expect(proposeStoryboard(contentScope, "card", 7, raced as never)).rejects.toThrow("nebyl přijat");
});

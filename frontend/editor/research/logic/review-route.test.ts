import { describe, expect, it } from "vitest";
import { reviewRoute } from "./review-route";

describe("scoped exact research review route", () => {
  const scope = { project: "p", workspace: "w" };
  const query = "?project=p&workspace=w&researchCard=c&researchReview=r&researchDigest=d";
  it("retains the exact record and digest and never adopts another scope", () => {
    expect(reviewRoute(query, scope)).toEqual({ card: "c", id: "r", digest: "d" });
    expect(reviewRoute(query, { ...scope, workspace: "other" })).toBeNull();
    expect(reviewRoute(query, { ...scope, project: "other" })).toBeNull();
    expect(reviewRoute(query.replace("&researchDigest=d", ""), scope)).toBeNull();
  });
});

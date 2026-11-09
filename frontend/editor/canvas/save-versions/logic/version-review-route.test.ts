import { expect, it } from "vitest";
import { reviewVersion } from "./version-review-route";
it("selects only the exact explicit scope and immutable identifier", () => {
  const id = "a".repeat(32);
  const query = `?project=p&workspace=w&canvasVersion=${id}`;
  expect(reviewVersion(query, "p", "w")).toBe(id);
  expect(reviewVersion(query, "p", "other")).toBeNull();
  expect(reviewVersion(query, "other", "w")).toBeNull();
  expect(reviewVersion("?canvasVersion=" + id, "p", "w")).toBeNull();
});

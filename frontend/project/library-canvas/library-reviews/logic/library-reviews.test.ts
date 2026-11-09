import {describe, expect, it} from "vitest";
import {reviewRows, selectedReview, scopedReviewId, type LibraryReview} from "./library-reviews";

const base = {id: "review", status: "pending", requiresHuman: true, author: {name: "heart"}, createdAt: "2026-11-09"} as const;

describe("Library human review projection", () => {
  it("never substitutes another review for an unknown scoped deep link", () => {
    const first: LibraryReview = {...base, operation: "folder_create", input: {}, before: {}};
    expect(selectedReview([first], "missing")).toBeNull();
    expect(selectedReview([first], first.id)).toBe(first);
    expect(scopedReviewId("?project=own&workspace=draft&libraryReview=review", "own", "other")).toBe("");
    expect(scopedReviewId("?project=own&workspace=draft&libraryReview=review", "own", "draft")).toBe("review");
  });
  it("shows exact old and proposed values without changing input", () => {
    const review: LibraryReview = {...base, operation: "folder_update", input: {title: "New", description: "Complete description", order: 0},
      before: {folder: {title: "Old", description: "Old description", order: 9, owner: "human"}}};
    expect(reviewRows(review)).toEqual([{label: "Název", before: "Old", after: "New"},
      {label: "Popis", before: "Old description", after: "Complete description"}, {label: "Pořadí", before: "9", after: "0"}]);
    expect(review.before.folder?.title).toBe("Old");
  });
  it("identifies destructive empty-folder deletion", () => {
    expect(reviewRows({...base, operation: "folder_delete", input: {}, before: {folder: {title: "Empty", description: "", order: 0, owner: "human"}}}))
      .toEqual([{label: "Složka", before: "Empty", after: "Bude odstraněna"}]);
  });
});

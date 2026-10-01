import { describe, expect, it } from "vitest";
import { commentView, newComment, nextCommentSpot } from "./comment-model";

describe("comment-model", () => {
  it("commentView přečte název jako titulek a podstatu jako text", () => {
    expect(commentView({ name: "Poznámka", purpose: "Nezapomeň na tohle." })).toEqual({
      title: "Poznámka",
      text: "Nezapomeň na tohle.",
      empty: false,
    });
  });

  it("commentView pozná prázdný i jen bílý text", () => {
    expect(commentView({ name: "Poznámka", purpose: "" }).empty).toBe(true);
    expect(commentView({ name: "Poznámka", purpose: "   " }).empty).toBe(true);
    expect(commentView({ name: "Poznámka", purpose: "x" }).empty).toBe(false);
  });

  it("newComment vytvoří komentář s výchozím jménem a prázdným textem na daném místě", () => {
    const created = newComment("sector-1", 120, 160);
    expect(created.kind).toBe("comment");
    expect(created.parentId).toBe("sector-1");
    expect(created.name).toBe("Poznámka");
    expect(created.purpose).toBe("");
    expect(created.x).toBe(120);
    expect(created.y).toBe(160);
    expect(created.sourceRef).toBeUndefined();
    expect(typeof created.id).toBe("string");
    expect(created.id.length).toBeGreaterThan(0);
  });

  it("newComment funguje i bez rodiče (kořen vrstvy)", () => {
    expect(newComment(null, 0, 0).parentId).toBeNull();
  });

  it("nextCommentSpot posune místo podle počtu komentářů ve stejné vrstvě", () => {
    const nodes = [
      { parentId: "layer-1", kind: "comment" as const },
      { parentId: "layer-1", kind: "comment" as const },
      { parentId: "layer-1", kind: "node" as const },
      { parentId: "layer-2", kind: "comment" as const },
    ];
    expect(nextCommentSpot(nodes, "layer-1")).toEqual({ x: 200, y: 200 });
    expect(nextCommentSpot(nodes, "layer-2")).toEqual({ x: 160, y: 160 });
    expect(nextCommentSpot(nodes, null)).toEqual({ x: 120, y: 120 });
  });
});

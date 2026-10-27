import { describe, expect, it } from "vitest";
import { catalog } from "../../model/logic/catalog";
import { paletteGroups } from "./palette-groups";

describe("palette groups", () => {
  it("lists the whole catalog except the managed Pod in the fixed group order", () => {
    const groups = paletteGroups();
    expect(groups.map((group) => group.id)).toEqual(["Web", "Data", "Control", "Event", "Deployment", "Adapter"]);
    expect(groups.reduce((sum, group) => sum + group.items.length, 0)).toBe(catalog.length - 1);
    expect(groups.flatMap((group) => group.items).some((item) => item.id === "pod")).toBe(false);
    expect(groups[0].items[0].id).toBe("client");
    expect(groups[0].items.find((item) => item.id === "client")).toEqual({ id: "client", name: "Client", icon: "▣", provider: "", summary: "1 port · http-request" });
  });

  it("searches name, category, provider and port types with every word", () => {
    expect(paletteGroups("postgre").flatMap((group) => group.items.map((item) => item.id))).toContain("postgresql");
    expect(paletteGroups("load balancer").flatMap((group) => group.items.map((item) => item.id))).toContain("load-balancer");
    expect(paletteGroups("sql-replication").every((group) => group.items.length > 0)).toBe(true);
    expect(paletteGroups("nic-takoveho")).toEqual([]);
  });
});

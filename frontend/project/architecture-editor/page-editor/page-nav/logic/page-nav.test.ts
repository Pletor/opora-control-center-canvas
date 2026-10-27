import { describe, expect, it } from "vitest";
import type { CanvasNode } from "@/shared/types/logic/types";
import type { ProductBranch } from "@/project/product-tree/logic/product-tree";
import { pageNav } from "./page-nav";

const page = (id: string, navLabel?: string): CanvasNode =>
  ({ id, parentId: null, kind: "node", name: id.toUpperCase(), purpose: "", x: 0, y: 0, site: { kind: "page", path: "/" + id, ...(navLabel ? { navLabel } : {}) } });
const branch = (id: string, children: ProductBranch[] = [], navLabel?: string): ProductBranch => ({ node: page(id, navLabel), children });

const pages = [branch("uvod", [], "Domů"), branch("pestovani", [branch("novinky", [branch("archiv")]), branch("pribeh")]), branch("kontakt")];

describe("pruh navigace domény", () => {
  it("drží pořadí a popisky NAVBARU a zvýrazní otevřenou stránku", () => {
    const nav = pageNav(pages, "kontakt");
    expect(nav.top.map((item) => item.label)).toEqual(["Domů", "PESTOVANI", "KONTAKT"]);
    expect(nav.top.find((item) => item.current)?.id).toBe("kontakt");
    expect(nav.sub).toEqual([]);
  });

  it("u podstránky zvýrazní předka a ukáže podstránky aktivní větve s hloubkou", () => {
    const nav = pageNav(pages, "archiv");
    expect(nav.top.map((item) => [item.id, item.onPath, item.current])).toEqual([["uvod", false, false], ["pestovani", true, false], ["kontakt", false, false]]);
    expect(nav.sub.map((item) => [item.id, item.depth, item.onPath, item.current])).toEqual([
      ["novinky", 1, true, false], ["archiv", 2, true, true], ["pribeh", 1, false, false]]);
  });

  it("hlavní stránka s podstránkami je aktivní větví sama", () => {
    expect(pageNav(pages, "pestovani").sub.map((item) => item.id)).toEqual(["novinky", "archiv", "pribeh"]);
  });

  it("bez aktivní stránky nic nezvýrazní", () => {
    const nav = pageNav(pages, null);
    expect(nav.top.some((item) => item.onPath || item.current)).toBe(false);
    expect(nav.sub).toEqual([]);
  });
});

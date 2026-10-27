import { describe, expect, it } from "vitest";
import { catalog, componentType, portColor } from "./catalog";
import { observedArchitecture, observedGeometry } from "./observed-geometry";
import { observedHttpRoles } from "./observed-http-roles";
import { PORT_TYPES } from "./model-types";

describe("katalog typů", () => {
  it("má 68 typů a 227 portů s jedinečnými id", () => {
    expect(catalog).toHaveLength(68);
    expect(catalog.reduce((n, type) => n + type.ports.length, 0)).toBe(227);
    expect(new Set(catalog.map((type) => type.id)).size).toBe(68);
    for (const type of catalog) expect(new Set(type.ports.map((p) => p.id)).size, type.id).toBe(type.ports.length);
  });

  it("používá právě 12 datových typů portu a směr vstup/výstup", () => {
    const used = new Set(catalog.flatMap((type) => type.ports.map((p) => p.type)));
    expect([...used].sort()).toEqual([...PORT_TYPES].sort());
    expect(catalog.every((type) => type.ports.every((p) => p.direction === "input" || p.direction === "output"))).toBe(true);
  });

  it("každý typ má změřenou geometrii se stejnými porty a rodinu pro podklad", () => {
    let anchors = 0;
    for (const type of catalog) {
      const shape = observedGeometry[type.id];
      expect(shape, type.id).toBeDefined();
      expect(shape.ports.map((p) => p.id).sort(), type.id).toEqual(type.ports.map((p) => p.id).sort());
      expect(observedArchitecture.groups[observedArchitecture.types[type.id]], type.id).toBeDefined();
      anchors += shape.ports.length;
    }
    expect(anchors).toBe(227);
    expect(Object.keys(observedGeometry)).toHaveLength(68);
  });

  it("role HTTP odkazují na typy katalogu; mimo něj jen šest pozorovaných, ale neimplementovaných typů zdroje", () => {
    const outside = new Set<string>();
    for (const [source, targets] of Object.entries(observedHttpRoles))
      for (const id of [source, ...targets]) if (!componentType(id)) outside.add(id);
    expect([...outside].sort()).toEqual(["aliyun-ack-cluster", "aliyun-maxcompute", "aws-eks-cluster", "aws-redshift", "gcp-bigquery", "gcp-gke-cluster"]);
  });

  it("barvy portů podle typu a u obecných typů podle směru", () => {
    expect(portColor("sql-query")).toBe("#a88dff");
    expect(portColor("job", "output")).toBe("#f5b041");
    expect(portColor("health", "input")).toBe("#ff78c8");
    expect(portColor("cache-command", "input")).toBe("#38d996");
    expect(portColor("http-request", "output")).toBe("#38d996");
    expect(portColor("http-request", "input")).toBe("#49b8ff");
    expect(portColor("data")).toBe("#49b8ff");
  });
});

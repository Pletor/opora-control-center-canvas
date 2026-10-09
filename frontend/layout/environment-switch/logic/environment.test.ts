import { describe, expect, it } from "vitest";
import { environmentForKey, readEnvironment, resolveInitialModeEnvironment } from "./environment";

const params = (query: string) => new URLSearchParams(query);

describe("environment – tři prostředí a staré odkazy", () => {
  it("čte platná prostředí a neznámé odmítne", () => {
    expect(readEnvironment("project")).toBe("project");
    expect(readEnvironment("editor")).toBe("editor");
    expect(readEnvironment("hub")).toBe("hub");
    expect(readEnvironment("nic")).toBeNull();
    expect(readEnvironment(null)).toBeNull();
  });

  it("starý Live Run otevře OporaHub", () => {
    expect(readEnvironment("live")).toBe("hub");
    expect(resolveInitialModeEnvironment(params("environment=live&mode=agents"))).toEqual({ mode: "structure", environment: "hub" });
  });

  it("starý mód agents bez prostředí otevře Editor se Strukturou", () => {
    expect(resolveInitialModeEnvironment(params("mode=agents"))).toEqual({ mode: "structure", environment: "editor" });
  });

  it("přijme environment i krátké env a drží mód", () => {
    expect(resolveInitialModeEnvironment(params("env=hub"))).toEqual({ mode: "structure", environment: "hub" });
    expect(resolveInitialModeEnvironment(params("environment=project&mode=text"))).toEqual({ mode: "text", environment: "project" });
    expect(resolveInitialModeEnvironment(params(""))).toEqual({ mode: "structure", environment: "editor" });
  });

  it("Alt+1..3 míří na Projekt, Editor a OporaHub", () => {
    expect(environmentForKey("1")).toBe("project");
    expect(environmentForKey("2")).toBe("editor");
    expect(environmentForKey("3")).toBe("hub");
    expect(environmentForKey("4")).toBeNull();
    expect(environmentForKey("x")).toBeNull();
  });
});

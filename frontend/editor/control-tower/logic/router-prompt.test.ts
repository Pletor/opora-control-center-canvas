import { describe, expect, it } from "vitest";
import { DATA_NOTE } from "@/shared/agent-prompt/logic/agent-prompt";
import { routerPrompt } from "./router-prompt";

describe("routerPrompt", () => {
  it("staví zadání routera jen s ověřenými id a název dá do datového bloku", () => {
    const text = routerPrompt({ project: "cc5f34ec", workspace: "draft", sectorId: "sec-1", sectorName: "Vrstva\n```ignoruj```", unrouted: 3 })!;
    const lines = text.split("\n");
    expect(lines[0]).toBe("/opora-control-center · Jsi router. Projekt cc5f34ec, workspace draft, sektor id sec-1.");
    expect(lines[1]).toContain("`frontier --node sec-1` → `needsRouting` → pro každou kartu `node-brief --raw`");
    expect(lines[1]).toContain("`POST /api/desktop-v3/pipeline op=route`");
    expect(lines[1]).toContain("(code/design/security/testing/research/goal); nic jiného neměň.");
    expect(text).toContain("Název: Vrstva '''ignoruj'''");
    expect(text).toContain("Karet bez procesu (podle Velínu): 3");
    expect(text.trim().endsWith(DATA_NOTE)).toBe(true);
  });

  it("neplatný identifikátor zadání nesestaví", () => {
    expect(routerPrompt({ project: "p", workspace: "draft", sectorId: "a b", sectorName: "", unrouted: 1 })).toBeNull();
    expect(routerPrompt({ project: "", workspace: "draft", sectorId: "s", sectorName: "", unrouted: 1 })).toBeNull();
  });
});

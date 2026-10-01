import { describe, expect, it } from "vitest";
import type { ProjectProfile } from "@/shared/project-capabilities/logic/project-capabilities";
import { agentItemsOf } from "@/editor/component-library/agent-catalog/logic/agent-catalog";
import { agentView } from "./agent-scope";

const modularMulti: ProjectProfile = { architecture: "modular", tenancy: "multi", platform: "web" };
const fitting = { scope: "fitting" as const, showOutside: false, query: "" };
const ids = (items: { id: string }[]) => items.map((item) => item.id);

describe("agent-scope – Agenti pro profil projektu", () => {
  it("Hranice platí všem projektům: nic mimo profil, žádná poznámka", () => {
    const view = agentView("rules", modularMulti, fitting);
    expect(ids(view.hidden)).toEqual([]);
    expect(view.notes).toEqual({});
    expect(view.counts.rules).toBe(agentItemsOf("rules").length);
  });

  it("saga přes služby je u modulárního projektu mimo profil, Vše ji ukáže ztlumeně", () => {
    expect(ids(agentView("workflows", modularMulti, fitting).hidden)).toEqual(["wf-saga-across-services"]);
    const all = agentView("workflows", modularMulti, { ...fitting, scope: "all" });
    expect(ids(all.shown)).toContain("wf-saga-across-services");
    expect(all.notes["wf-saga-across-services"]).toBe("mimo profil");
    expect(all.counts.workflows).toBe(agentItemsOf("workflows").length);
  });

  it("hledání v kategorii najde i postup mimo profil", () => {
    const view = agentView("workflows", modularMulti, { ...fitting, query: "saga" });
    expect(ids(view.shown)).toEqual(["wf-saga-across-services"]);
  });
});

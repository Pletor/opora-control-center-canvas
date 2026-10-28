import { describe, expect, it } from "vitest";
import { emptyStudioModel } from "../../model/logic/model-types";
import { modelBindingIds } from "./model-targets";

const unit = (id: string, binding?: string) => ({ id, type: "service", name: id, position: { x: 0, y: 0 }, config: {}, ...(binding ? { binding: { nodeId: binding } } : {}) });

describe("cíl z MODELu", () => {
  it("bere id karet, na které váže uzel modelu domény", () => {
    const model = { ...emptyStudioModel("web"), revision: 2, nodes: [unit("a", "api"), unit("b"), unit("c", "kontakt"), unit("d", "api")] };
    expect([...modelBindingIds(model, "web")]).toEqual(["api", "kontakt"]);
  });

  it("cizí doména, neznámý tvar nebo prázdná vazba = žádný odznak", () => {
    expect(modelBindingIds({ ...emptyStudioModel("scenario:x"), nodes: [unit("a", "api")] }, "web").size).toBe(0);
    expect(modelBindingIds(null, "web").size).toBe(0);
    expect(modelBindingIds({ ...emptyStudioModel("web"), nodes: [{ ...unit("a"), binding: { nodeId: "" } }, null] }, "web").size).toBe(0);
  });
});

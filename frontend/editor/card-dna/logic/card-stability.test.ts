import { describe, expect, it } from "vitest";
import { stabilizeCardData } from "./card-stability";

describe("stabilizeCardData", () => {
  it("keeps a card object for an equal, freshly-polled card model", () => {
    const first = { view: { name: "Build", rows: [{ id: "block", ports: [{ id: "out", label: "Next" }] }] }, evidence: { checksRun: Array.from({ length: 200 }, (_, index) => ({ checkId: String(index), exitCode: 0 })) } };
    const stable = stabilizeCardData(undefined, first);
    const again = stabilizeCardData(stable, structuredClone(first));
    expect(again).toBe(stable);
  });

  it("updates a semantic change but ignores a callback identity change", () => {
    let firstCalls = 0;
    let freshCalls = 0;
    const stable = stabilizeCardData(undefined, { view: { name: "Build" }, ports: { toggle: () => { firstCalls += 1; } } });
    const same = stabilizeCardData(stable, { view: { name: "Build" }, ports: { toggle: () => { freshCalls += 1; } } });
    expect(same).toBe(stable);
    same.ports.toggle();
    expect(firstCalls).toBe(0);
    expect(freshCalls).toBe(1);

    const changed = stabilizeCardData(same, { view: { name: "Verify" }, ports: { toggle: () => undefined } });
    expect(changed).not.toBe(same);
  });

  it("does not retain a removed callback as an active callback", () => {
    type MaybeAction = { view: { name: string }; action?: () => string };
    const stable = stabilizeCardData<MaybeAction>(undefined, { view: { name: "Build" }, action: () => "old" });
    const changed = stabilizeCardData<MaybeAction>(stable, { view: { name: "Build" } });
    expect(changed).not.toBe(stable);
    expect(changed.action).toBeUndefined();
  });
});

import { describe, expect, it } from "vitest";
import { requestKey, requestsView } from "./linie-requests";

describe("žádosti srdci", () => {
  it("řetězec pěti kroků: hotový jen s potvrzením, selhání zůstává vidět, opakování ho přebije", () => {
    const [q] = requestsView({ requests: [{ id: "rq_1", text: "Linie: kuličky na čase", at: "2026-11-06T10:00:00Z", steps: [
      { k: "accepted", at: "", by: "human" },
      { k: "plan", at: "", by: "agent:heart", evidence: { cardId: "c1" } },
      { k: "ticket", at: "", by: "agent:heart", evidence: { ticket: "tk_9" } },
      { k: "attempt", failed: true, why: "relace kanceláře spadla", at: "", by: "agent:office" },
    ] }], open: 1 });
    expect(q).toMatchObject({ id: "rq_1", text: "Linie: kuličky na čase", open: true });
    expect(q.steps.map((s) => [s.k, s.state, s.why])).toEqual([
      ["accepted", "ok", ""], ["plan", "ok", ""], ["ticket", "ok", ""], ["attempt", "fail", "relace kanceláře spadla"], ["commit", "wait", ""]]);
    const retried = requestsView({ requests: [{ id: "rq_1", text: "x", steps: [{ k: "attempt", failed: true, why: "spadla" }, { k: "attempt", evidence: { attemptId: "at_1" } }, { k: "commit", evidence: { sha: "a" } }] }] })[0];
    expect(retried.steps.map((s) => s.state)).toEqual(["wait", "wait", "wait", "ok", "ok"]);
    expect(retried.open).toBe(false);
    expect(requestsView(null)).toEqual([]);
  });
  it("klíč idempotence nese nonce, aby druhé odeslání téhož textu nevyrobilo druhou žádost", () => {
    expect(requestKey(" ahoj ", "n1")).toBe("ui-n1-4");
  });
});

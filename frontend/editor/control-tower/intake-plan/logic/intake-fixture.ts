// Vzorová odpověď `GET /api/intake` pro testy pohledu (logika i komponenty): aktivní milník, návrh srdce, prázdná oblast.
import type { IntakeResponse } from "./intake-plan";

const requirement = (id: string, status: string, openCondition: string | null = null) =>
  ({ id, title: "Požadavek " + id, status, openCondition, milestoneId: null });
export const intakeFixture: IntakeResponse = {
  areas: [
    { id: "a1", name: "Vyhledání", proposed: [],
      milestone: { id: "ms_1", title: "bge-m3 lokálně", status: "active", progress: 50, done: false, criteria: [
        { id: "c1", text: "Sloupec 1024", cards: [{ id: "k1", done: true }], done: true },
        { id: "c2", text: "Hledání čte jen aktuální model", cards: [{ id: "k2", done: false }], done: false }] },
      requirements: [requirement("rq_1", "open")], deferred: [requirement("rq_2", "deferred", "ms_1")] },
    { id: "a2", name: "Odpovídání", milestone: null, requirements: [], deferred: [requirement("rq_3", "deferred", "až bude review")],
      proposed: [{ id: "ms_2", title: "Citace ověřitelné", status: "proposed", criteria: [{ id: "c1", text: "Citace", cards: ["k2", "neznámá"] }] }] },
    { id: "a3", name: "", milestone: null, proposed: [], requirements: [], deferred: [] },
  ],
  unassigned: [requirement("rq_4", "open")],
  entries: [{ id: "ie_1", layer: "heart", verdict: "done" }, { id: "ie_2", layer: "jev", verdict: "pending" }, { id: "ie_3", layer: "determinism", verdict: "duplicate" }],
  pending: 1, duplicates: 1,
};

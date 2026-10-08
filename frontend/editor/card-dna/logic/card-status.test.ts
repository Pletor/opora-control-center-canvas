import { expect, it } from "vitest";
import { cardStatusData } from "./card-status";
import { assignmentStatusView } from "./code-status";

it("předá stav z pollu Boardu do dat karty včetně current/unbound, nikoli jen changed warning", () => {
  const source = { status: "present" as const, path: "src/app.ts", origin: "existing" as const };
  for (const status of ["current", "changed", "unbound"] as const) {
    const assignment = { status, resultId: "r", source: "result" as const };
    const data = cardStatusData("n", { n: source }, { n: assignment });
    expect(data.sourceStatus).toBe(source); expect(data.assignmentStatus).toBe(assignment);
    expect(assignmentStatusView(data.assignmentStatus?.status).kind).toBe(status);
  }
  expect(cardStatusData("missing", { n: source }, {})).toEqual({ sourceStatus: undefined, assignmentStatus: undefined });
});

import { expect, it } from "vitest";
import { releaseLeaseBody } from "./release-lease";

it("releases a lease as human without a token", () => {
  const body = releaseLeaseBody("p", "w", "n1");
  expect(body).toEqual({ project: "p", workspace: "w", nodeId: "n1", op: "release" });
  expect("token" in body).toBe(false);
});

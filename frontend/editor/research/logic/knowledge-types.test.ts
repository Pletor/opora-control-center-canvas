import { expect, it } from "vitest";
import { knowledgeIdentity, sourceRoute, solutionVerificationLabel, solutionVerificationDetail } from "./knowledge-types";
it("keeps origin and exact revision in identities and canonical source navigation", () => {
 const ref={projectId:"ample",workspaceId:"work",id:"login",revision:3};
 expect(knowledgeIdentity(ref)).not.toBe(knowledgeIdentity({...ref,projectId:"other"}));
 expect(knowledgeIdentity(ref)).not.toBe(knowledgeIdentity({...ref,revision:4}));
 const params=new URL(sourceRoute(ref),"http://localhost").searchParams;
 expect(params.get("project")).toBe("ample");
 expect(params.get("workspace")).toBe("work");
 expect(params.get("researchSource")).toBe("login");
 expect(params.get("researchRevision")).toBe("3");
});

it("labels functional worker evidence without claiming independent verification", () => {
 const proof = { status: "reported_evidence" as const, verified: true, independent: false as const,
  level: "reported_evidence" as const, acceptedRevision: "spec", headSha: "commit", executionId: "run", receiptId: "receipt", source: "agent-reported execution receipt" };
 expect(solutionVerificationLabel(proof)).toBe("Doloženo Kanceláří");
 expect(solutionVerificationDetail(proof)).toContain("spec");
 expect(solutionVerificationDetail(proof)).toContain("Nejde o nezávislé");
 expect(solutionVerificationLabel({ status: "unknown", reason: "Verified research alone" })).toBe("Nedoloženo");
 expect(solutionVerificationLabel({ ...proof, status: "unproven", verified: false })).toBe("Nedoloženo");
});

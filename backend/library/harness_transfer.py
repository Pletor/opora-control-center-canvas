"""Read-only fixture transfer eligibility from explicitly shareable native references."""
from backend.canvas.graph import digest
from backend.library import harness_transfer_policy as policy
from backend.library import harness_verifier_plan as plans
from backend.library.harness_stability_retained import RetainedStability


class SharedEligibility:
    def __init__(self, canvas):
        self.reader = RetainedStability(canvas)

    def _proof(self, source, approved):
        configured = plans.configuration(source["project"], source["workspace"])
        assessment = self.reader.assess(source)
        if plans.configuration(source["project"], source["workspace"]) != configured:
            raise ValueError("Source runtime changed during assessment.")
        if (assessment["eligible"] is not True or assessment["candidate"] != approved["candidate"]
                or assessment["scope"] != {"project": source["project"], "workspace": source["workspace"],
                                            "problem": approved["problem"]}):
            raise ValueError("Source does not establish this shared candidate's eligibility.")
        # Only the operator-declared references and content-addressed proof are public.
        # Never copy retained execution metadata, accepted content, tokens or raw outputs.
        return {**source, "reportDigest": assessment["source"]["reportDigest"],
                "evidenceDigest": assessment["evidenceDigest"], "image": configured["image"]}

    def assess(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"publication"}:
            raise ValueError("Shared eligibility requires only a publication identifier.")
        approved = policy.publication(payload["publication"])
        proofs, reasons = [], []
        for source in approved["sources"]:
            try:
                proofs.append(self._proof(source, approved))
            except (ValueError, KeyError, TypeError):
                reasons.append("source-unavailable-or-ineligible")
        projects = len({proof["project"] for proof in proofs})
        images = len({proof["image"] for proof in proofs})
        if projects < 3:
            reasons.append("fewer-than-three-projects")
        if images < 2:
            reasons.append("fewer-than-two-pinned-images")
        if not reasons:
            # Project databases have separate transactions. Detect changed source snapshots
            # before returning; this is not a reservation against future evidence changes.
            for source, previous in zip(approved["sources"], proofs):
                try:
                    if self._proof(source, approved) != previous:
                        reasons.append("source-changed-during-assessment")
                except (ValueError, KeyError, TypeError):
                    reasons.append("source-changed-during-assessment")
        if policy.publication(payload["publication"]) != approved:
            raise ValueError("Shared publication changed during assessment.")
        result = {"schema": "harness.shared-eligibility/1", "authority": "native-policy-assessment",
                  "publication": approved["id"], "policyDigest": digest(approved),
                  "candidate": approved["candidate"], "problem": approved["problem"],
                  "eligible": not reasons, "reasons": sorted(set(reasons)), "sources": proofs,
                  "verifiedProjects": projects, "verifiedImages": images,
                  "environmentBasis": "pinned-node-image-content",
                  "minimumProjects": 3, "minimumImages": 2,
                  "executionAuthority": False, "promotionAllowed": False, "reservation": False,
                  "evidenceBasis": {"taskOutcomes": "selected-kit-association", "causalBenefitEstablished": False,
                                    "directObservation": "approved-fixture-cases-only"},
                  "meaning": "Fixture transfer eligibility for an intentionally published version. Target compatibility and "
                             "accepted assignment remain required. Distinct images are not independent production environments; "
                             "this snapshot neither publishes code nor authorizes global promotion or production use."}
        return {**result, "evidenceDigest": digest(result)}

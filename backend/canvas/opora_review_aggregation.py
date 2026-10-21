"""Pure, deterministic bookkeeping between finders and voters (docs/oporahub-review-jobs.md).

Models only propose and vote; this module decides. Candidates are grouped by fingerprint,
fingerprints already known on the PR (posted, fixed or resolved in any round) are never
proposed again, and a candidate becomes a finding only with enough independent confirms."""
import hashlib

SEVERITY_RANK = {"important": 0, "nit": 1, "pre_existing": 2}


def short_id(prefix, *parts):
    return prefix + hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:24]


def finding_id(repository, number, fingerprint):
    return short_id("rf_", repository, number, fingerprint)


def candidates(job_id, submissions, known_fingerprints):
    """`submissions` = [(slot, {findings, fixed})]; returns stable candidates for the vote phase.

    Same fingerprint from several finders collapses into one candidate keeping the most severe
    severity and the lowest-slot wording; `finders` lists the slots that raised it."""
    grouped, fixes = {}, {}
    for slot, submission in sorted(submissions, key=lambda item: item[0]):
        for item in submission["findings"]:
            if item["fingerprint"] in known_fingerprints:
                continue
            current = grouped.get(item["fingerprint"])
            if current is None:
                grouped[item["fingerprint"]] = current = {**item, "finders": []}
            elif SEVERITY_RANK[item["severity"]] < SEVERITY_RANK[current["severity"]]:
                current["severity"] = item["severity"]
            current["finders"].append(slot)
        for claim in submission.get("fixed", []):
            current = fixes.setdefault(claim["findingId"], {"findingId": claim["findingId"],
                                                            "rationale": claim["rationale"], "finders": []})
            current["finders"].append(slot)
    result = [{"candidateId": short_id("rc_", job_id, "finding", key), "kind": "finding", **value}
              for key, value in grouped.items()]
    result += [{"candidateId": short_id("rc_", job_id, "fix", key), "kind": "fix", **value}
               for key, value in fixes.items()]
    return sorted(result, key=lambda item: (item["kind"], item.get("fingerprint") or item["findingId"]))


def tally(items, ballots, required_votes):
    """`ballots` = [{votes: [{candidateId, verdict}]}]; returns candidates with confirms/rejects/accepted."""
    result = []
    for item in items:
        verdicts = [vote["verdict"] for ballot in ballots for vote in ballot["votes"]
                    if vote["candidateId"] == item["candidateId"]]
        confirms = verdicts.count("confirm")
        result.append({**item, "confirms": confirms, "rejects": verdicts.count("reject"),
                       "accepted": confirms >= required_votes})
    return result

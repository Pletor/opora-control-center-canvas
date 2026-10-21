"""Conformance bridge: TLA+ invariants of ExecutionAuthority.tla as predicates over an event log.

This is NOT a proof and not a refinement mapping. The TLC model (tools/formal/oporahub-execution)
proves the invariants for a finite abstract protocol; these predicates check that one
recorded run of the real `opora_executions` service did not violate the same properties.
Each event is a dict recorded by the driver after one API call:
  op, executionId, epoch (credential used), ok, receiptId (result only),
  epochBefore/epochAfter (card epoch), authorityBefore/authorityAfter (execution ids whose
  lease would pass `lease_valid` at that instant).
Each predicate returns the list of violating events (empty = conforms).
"""


def one_active_owner(log):
    """OneActiveOwner: at most one execution holds valid authority at any instant."""
    return [event for event in log if len(event["authorityAfter"]) > 1 or len(event["authorityBefore"]) > 1]


def no_stale_epoch_receipt(log):
    """NoStaleEpochReceipt: a new receipt only from the current-epoch holder of valid authority."""
    seen, bad = set(), []
    for event in log:
        if event["op"] != "result" or not event["ok"] or event["receiptId"] in seen:
            continue
        seen.add(event["receiptId"])
        if event["epoch"] != event["epochBefore"] or event["executionId"] not in event["authorityBefore"]:
            bad.append(event)
    return bad


def one_receipt_per_execution(log):
    """OneReceiptPerExecution: replays return the same receipt; no second receipt per execution."""
    receipts, bad = {}, []
    for event in log:
        if event["op"] == "result" and event["ok"]:
            first = receipts.setdefault(event["executionId"], event["receiptId"])
            if first != event["receiptId"]:
                bad.append(event)
    return bad


def monotonic_epoch(log):
    """MonotonicEpoch: the card epoch never decreases."""
    return [event for event in log if event["epochAfter"] < event["epochBefore"]]


INVARIANTS = {"OneActiveOwner": one_active_owner, "NoStaleEpochReceipt": no_stale_epoch_receipt,
              "OneReceiptPerExecution": one_receipt_per_execution, "MonotonicEpoch": monotonic_epoch}


def violations(log):
    return {name: found for name, check in INVARIANTS.items() if (found := check(log))}

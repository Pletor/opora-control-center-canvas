--------------------- MODULE ExecutionAuthority ---------------------
EXTENDS Naturals, FiniteSets, TLC
CONSTANTS Owners, ClaimIds, RequestIds, Payloads, MaxEpoch, MaxTime, EnforceFence
VARIABLES now, epoch, lease, revision, context, runs, claims, receipts, audit
vars == <<now, epoch, lease, revision, context, runs, claims, receipts, audit>>
Epochs == 1..MaxEpoch
TTLs == {1, 2}
EmptyRun == [owner |-> "none", rev |-> 0, ctx |-> 0, expires |-> 0,
             ttl |-> 0, state |-> "unused"]
Audit(kind, before, after) == [kind |-> IF kind \in {"claim-replay", "claim-conflict", "result-replay", "result-conflict"} THEN kind ELSE "other", before |-> before, after |-> after]
Count == Cardinality(receipts)
Init == /\ now = 0 /\ epoch = 0 /\ lease = 0
        /\ revision = 0 /\ context = 0
        /\ runs = [e \in Epochs |-> EmptyRun]
        /\ claims = [q \in ClaimIds |-> 0]
        /\ receipts = {}
        /\ audit = Audit("init", 0, 0)

Fence(e) == ~EnforceFence \/ (e = epoch /\ lease = e)
Valid(e) == /\ e <= epoch /\ runs[e].state = "running"
            /\ now < runs[e].expires /\ runs[e].rev = revision
            /\ runs[e].ctx = context /\ Fence(e)
Available == IF lease = 0 THEN TRUE ELSE now >= runs[lease].expires

Claim(owner, q, ttl) ==
    /\ claims[q] = 0 /\ epoch < MaxEpoch /\ Available
    /\ epoch' = epoch + 1 /\ lease' = epoch + 1
    /\ runs' = [runs EXCEPT ![epoch + 1] =
          [owner |-> owner, rev |-> revision, ctx |-> context,
           expires |-> now + ttl, ttl |-> ttl, state |-> "running"]]
    /\ claims' = [claims EXCEPT ![q] = epoch + 1]
    /\ audit' = Audit("claim", Count, Count)
    /\ UNCHANGED <<now, revision, context, receipts>>

ClaimReplay(owner, q, rev, ctx, ttl) ==
    /\ claims[q] # 0
    /\ LET r == runs[claims[q]] IN
       audit' = Audit(IF <<owner, rev, ctx, ttl>> = <<r.owner, r.rev, r.ctx, r.ttl>>
                      THEN "claim-replay" ELSE "claim-conflict", Count, Count)
    /\ UNCHANGED <<now, epoch, lease, revision, context, runs, claims, receipts>>

Heartbeat(e, owner, ttl) ==
    /\ Valid(e) /\ runs[e].owner = owner
    /\ runs' = [runs EXCEPT ![e].expires = now + ttl]
    /\ audit' = Audit("heartbeat", Count, Count)
    /\ UNCHANGED <<now, epoch, lease, revision, context, claims, receipts>>

Release(e, owner) ==
    /\ e <= epoch /\ runs[e].owner = owner
    /\ runs[e].state \in {"running", "released"}
    /\ runs' = [runs EXCEPT ![e].state = "released"]
    /\ lease' = IF lease = e THEN 0 ELSE lease
    /\ audit' = Audit("release", Count, Count)
    /\ UNCHANGED <<now, epoch, revision, context, claims, receipts>>

ForceRelease ==
    /\ lease # 0 /\ lease' = 0
    /\ audit' = Audit("force-release", Count, Count)
    /\ UNCHANGED <<now, epoch, revision, context, runs, claims, receipts>>

Result(e, owner, q, body) ==
    /\ Valid(e) /\ runs[e].owner = owner
    /\ ~\E r \in receipts : r.e = e /\ r.q = q
    /\ receipts' = receipts \cup {
          [e |-> e, q |-> q, body |-> body, owner |-> owner,
           grantedOwner |-> runs[e].owner, grantEpoch |-> epoch,
           grantLease |-> lease, at |-> now, expiry |-> runs[e].expires,
           rev |-> runs[e].rev, ctx |-> runs[e].ctx,
           liveRev |-> revision, liveCtx |-> context]}
    /\ runs' = [runs EXCEPT ![e].state = "done"]
    /\ lease' = IF lease = e THEN 0 ELSE lease
    /\ audit' = Audit("result-new", Count, Count + 1)
    /\ UNCHANGED <<now, epoch, revision, context, claims>>

ResultReplay(e, owner, q, body) ==
    /\ runs[e].owner = owner
    /\ \E r \in receipts : r.e = e /\ r.q = q
    /\ LET saved == CHOOSE r \in receipts : r.e = e /\ r.q = q IN
       audit' = Audit(IF saved.body = body THEN "result-replay" ELSE "result-conflict",
                      Count, Count)
    /\ UNCHANGED <<now, epoch, lease, revision, context, runs, claims, receipts>>

Tick == /\ now < MaxTime /\ now' = now + 1
        /\ audit' = Audit("tick", Count, Count)
        /\ UNCHANGED <<epoch, lease, revision, context, runs, claims, receipts>>
Revise == /\ revision = 0 /\ revision' = 1
          /\ audit' = Audit("revision-drift", Count, Count)
          /\ UNCHANGED <<now, epoch, lease, context, runs, claims, receipts>>
Edit == /\ context = 0 /\ context' = 1
        /\ audit' = Audit("context-drift", Count, Count)
        /\ UNCHANGED <<now, epoch, lease, revision, runs, claims, receipts>>

Next == \/ \E owner \in Owners, q \in ClaimIds, ttl \in TTLs : Claim(owner, q, ttl)
        \/ \E owner \in Owners, q \in ClaimIds, rev \in 0..1, ctx \in 0..1, ttl \in TTLs :
               ClaimReplay(owner, q, rev, ctx, ttl)
        \/ \E e \in Epochs, owner \in Owners, ttl \in TTLs : Heartbeat(e, owner, ttl)
        \/ \E e \in Epochs, owner \in Owners : Release(e, owner)
        \/ \E e \in Epochs, owner \in Owners, q \in RequestIds, body \in Payloads :
               Result(e, owner, q, body) \/ ResultReplay(e, owner, q, body)
        \/ ForceRelease \/ Tick \/ Revise \/ Edit
Spec == Init /\ [][Next]_vars

TypeOK == /\ now \in 0..MaxTime /\ epoch \in 0..MaxEpoch
          /\ lease \in 0..MaxEpoch /\ revision \in 0..1 /\ context \in 0..1
          /\ DOMAIN runs = Epochs /\ DOMAIN claims = ClaimIds
          /\ \A e \in Epochs : runs[e].owner \in Owners \cup {"none"}
          /\ \A q \in ClaimIds : claims[q] \in 0..MaxEpoch
          /\ Cardinality(receipts) <= MaxEpoch
MonotonicEpoch == [][epoch' >= epoch]_vars
OneActiveOwner == Cardinality({e \in Epochs : Valid(e)}) <= 1
NoUnauthorizedReceipt == \A r \in receipts :
    /\ r.e = r.grantEpoch /\ r.e = r.grantLease
    /\ r.at < r.expiry /\ r.rev = r.liveRev /\ r.ctx = r.liveCtx
    /\ r.owner = r.grantedOwner
NoStaleEpochReceipt == \A r \in receipts : r.e = r.grantEpoch
OneReceiptPerExecution == \A a,b \in receipts : a.e = b.e => a = b
Idempotency == audit.kind \in {"claim-replay", "claim-conflict", "result-replay", "result-conflict"}
              => audit.before = audit.after
=============================================================================

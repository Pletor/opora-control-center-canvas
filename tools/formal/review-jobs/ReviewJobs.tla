------------------------------ MODULE ReviewJobs ------------------------------
(* Automated review jobs on one PR (docs/oporahub-review-jobs.md; implementation
   backend/canvas/opora_review_jobs.py, opora_review_job_tasks.py, opora_review_aggregation.py,
   merge gate opora_review_gate*.py). Finite abstraction:
   - one job per PR head, at most MaxRounds completed rounds (then a human decides),
   - finders propose fingerprints; known ones are never proposed again,
   - a candidate becomes a finding only with >= Required confirms out of Voters,
   - a human approval counts only for the head it was given on; merge needs it at the
     current head.
   Mutant selects a deliberate bug for the negative configs ("none" = the real rule). *)
EXTENDS Naturals, Sequences, FiniteSets
CONSTANTS FP, Voters, Required, MaxHead, MaxRounds, Mutant
VARIABLES head, jobs, known, postings, approvedHead, merged, mergedHead
vars == <<head, jobs, known, postings, approvedHead, merged, mergedHead>>

Phases == {"find", "vote", "completed"}
NoJob == [head |-> 0, phase |-> "completed", cands |-> {}]
Done == {i \in 1..Len(jobs) : jobs[i].phase = "completed"}
Live(h) == \E i \in 1..Len(jobs) : jobs[i].head = h
Capped == Cardinality(Done) >= MaxRounds
Threshold == IF Mutant = "threshold" THEN Required - 1 ELSE Required

Init == /\ head = 1 /\ jobs = << >> /\ known = {} /\ postings = << >>
        /\ approvedHead = 0 /\ merged = FALSE /\ mergedHead = 0

\* GitHub: the author pushes a new head.
Push == /\ ~merged /\ head < MaxHead /\ head' = head + 1
        /\ UNCHANGED <<jobs, known, postings, approvedHead, merged, mergedHead>>

\* Enqueue: one job per head while the round cap is not reached and no job is running.
Enqueue == /\ ~merged /\ ~Live(head)
           /\ (Mutant = "no_cap" \/ ~Capped)
           /\ \A i \in 1..Len(jobs) : jobs[i].phase = "completed"
           /\ jobs' = Append(jobs, [head |-> head, phase |-> "find", cands |-> {}])
           /\ UNCHANGED <<head, known, postings, approvedHead, merged, mergedHead>>

\* Finders: candidates exclude fingerprints already known on the PR.
Find(i, S) == /\ jobs[i].phase = "find"
              /\ S \subseteq (IF Mutant = "repost" THEN FP ELSE FP \ known)
              /\ jobs' = [jobs EXCEPT ![i] = [@ EXCEPT !.phase = "vote", !.cands = S]]
              /\ UNCHANGED <<head, known, postings, approvedHead, merged, mergedHead>>

\* Voters: each candidate gets some number of confirms; enough confirms post a finding.
Vote(i, confirms) ==
    /\ jobs[i].phase = "vote"
    /\ LET accepted == {c \in jobs[i].cands : confirms[c] >= Threshold}
           order == CHOOSE s \in [1..Cardinality(accepted) -> accepted] :
                        \A a, b \in DOMAIN s : a # b => s[a] # s[b]
       IN /\ known' = known \cup accepted
          /\ postings' = postings \o [k \in 1..Cardinality(accepted) |->
                                         [fp |-> order[k], confirms |-> confirms[order[k]]]]
    /\ jobs' = [jobs EXCEPT ![i].phase = "completed"]
    /\ UNCHANGED <<head, approvedHead, merged, mergedHead>>

\* A human approves the current head; GitHub keeps the approval on that commit only.
Approve == /\ ~merged /\ approvedHead' = head
           /\ UNCHANGED <<head, jobs, known, postings, merged, mergedHead>>

GateOpen == IF Mutant = "stale_approval" THEN approvedHead # 0 ELSE approvedHead = head

Merge == /\ ~merged /\ GateOpen
         /\ \A i \in 1..Len(jobs) : jobs[i].phase = "completed"
         /\ merged' = TRUE /\ mergedHead' = head
         /\ UNCHANGED <<head, jobs, known, postings, approvedHead>>

Next == \/ Push \/ Enqueue \/ Approve \/ Merge
        \/ \E i \in 1..Len(jobs) : \/ \E S \in SUBSET FP : Find(i, S)
                                   \/ \E c \in [FP -> 0..Voters] : Vote(i, c)
Spec == Init /\ [][Next]_vars

TypeOK == /\ head \in 1..MaxHead
          /\ \A i \in 1..Len(jobs) : jobs[i].phase \in Phases /\ jobs[i].cands \subseteq FP
          /\ known \subseteq FP /\ approvedHead \in 0..MaxHead /\ merged \in BOOLEAN

\* At most MaxRounds review rounds on one PR.
RoundsCap == Len(jobs) <= MaxRounds
\* A fingerprint is posted at most once on the PR.
NoRepost == \A a, b \in 1..Len(postings) : a # b => postings[a].fp # postings[b].fp
\* Every posted finding had at least Required independent confirms.
VoteThreshold == \A k \in 1..Len(postings) : postings[k].confirms >= Required
\* Merge only with a human approval bound to the merged head SHA.
ApprovalBoundToHead == merged => mergedHead = approvedHead
\* One job per head.
OneJobPerHead == \A a, b \in 1..Len(jobs) : a # b => jobs[a].head # jobs[b].head
==============================================================================

-------------------------------- MODULE PrLoop --------------------------------
(* Execution -> PR -> merge loop closure (docs/oporahub-executions.md "Uzavření smyčky";
   implementation backend/canvas/opora_execution_pull_requests.py, opora_execution_pr_closure.py,
   opora_execution_pr_manager.py). GitHub moves on its own; the Canvas loop observes it and
   writes back, possibly repeatedly (restarts, concurrent ticks).
   - the merge write-back happens exactly once (one `execution.merged`, run released,
     awaitingHumanClose),
   - a close without merge writes one `execution.pr_closed` per close and raises attention,
     a reopen clears it,
   - a new head SHA of the same PR is re-linked (liveness under weak fairness).
   Mutant selects a deliberate bug for the negative configs ("none" = the real rule). *)
EXTENDS Naturals
CONSTANTS MaxHead, MaxCloses, Mutant
VARIABLES gh, head, closes, link, linkedHead, merges, closeEvents, attention, awaiting, run
vars == <<gh, head, closes, link, linkedHead, merges, closeEvents, attention, awaiting, run>>

Init == /\ gh = "open" /\ head = 1 /\ closes = 0
        /\ link = "none" /\ linkedHead = 0 /\ merges = 0 /\ closeEvents = 0
        /\ attention = FALSE /\ awaiting = FALSE /\ run = "submitted"

\* --- GitHub (environment, no fairness) ---
Push == /\ gh = "open" /\ head < MaxHead /\ head' = head + 1
        /\ UNCHANGED <<gh, closes, link, linkedHead, merges, closeEvents, attention, awaiting, run>>
GhMerge == /\ gh = "open" /\ gh' = "merged"
           /\ UNCHANGED <<head, closes, link, linkedHead, merges, closeEvents, attention, awaiting, run>>
GhClose == /\ gh = "open" /\ closes < MaxCloses /\ gh' = "closed" /\ closes' = closes + 1
           /\ UNCHANGED <<head, link, linkedHead, merges, closeEvents, attention, awaiting, run>>
GhReopen == /\ gh = "closed" /\ gh' = "open"
            /\ UNCHANGED <<head, closes, link, linkedHead, merges, closeEvents, attention, awaiting, run>>

\* --- Canvas ---
\* The agent links exactly one PR to the submitted run.
Link == /\ link = "none" /\ gh = "open" /\ link' = "open" /\ linkedHead' = head
        /\ UNCHANGED <<gh, head, closes, merges, closeEvents, attention, awaiting, run>>
\* Same PR, new head SHA, new requestId: only the SHA moves.
Relink == /\ Mutant # "no_relink"
          /\ link = "open" /\ gh = "open" /\ linkedHead # head /\ linkedHead' = head
          /\ UNCHANGED <<gh, head, closes, link, merges, closeEvents, attention, awaiting, run>>
\* Loop tick: idempotent write-back keyed by (run, merge SHA) / (run, close episode).
WriteMerged == /\ gh = "merged" /\ link # "none"
               /\ (Mutant = "double_merge" \/ link # "merged")
               /\ merges < 3
               /\ link' = "merged" /\ merges' = merges + 1 /\ awaiting' = TRUE /\ run' = "released"
               /\ attention' = FALSE
               /\ UNCHANGED <<gh, head, closes, linkedHead, closeEvents>>
WriteClosed == /\ gh = "closed" /\ link = "open"
               /\ link' = "closed" /\ closeEvents' = closeEvents + 1
               /\ attention' = (Mutant # "no_attention")
               /\ UNCHANGED <<gh, head, closes, linkedHead, merges, awaiting, run>>
WriteReopened == /\ gh = "open" /\ link = "closed"
                 /\ link' = "open" /\ attention' = FALSE
                 /\ UNCHANGED <<gh, head, closes, linkedHead, merges, closeEvents, awaiting, run>>
WriteBack == WriteMerged \/ WriteClosed \/ WriteReopened

Next == Push \/ GhMerge \/ GhClose \/ GhReopen \/ Link \/ Relink \/ WriteBack
Spec == Init /\ [][Next]_vars /\ WF_vars(Relink) /\ WF_vars(WriteBack)

TypeOK == /\ gh \in {"open", "merged", "closed"} /\ link \in {"none", "open", "merged", "closed"}
          /\ head \in 1..MaxHead /\ linkedHead \in 0..MaxHead /\ merges \in 0..3
          /\ closeEvents \in 0..MaxCloses /\ attention \in BOOLEAN /\ awaiting \in BOOLEAN
          /\ run \in {"submitted", "released"}

\* Exactly-once merge write-back, with its effects.
MergeOnce == merges <= 1
MergedWriteBack == link = "merged" <=> (merges >= 1 /\ awaiting /\ run = "released")
\* One close event per GitHub close, never more.
OneEventPerClose == closeEvents <= closes
\* Closed without merge <=> attention.
ClosedAttention == attention <=> link = "closed"
\* The linked head never runs ahead of GitHub.
LinkedHeadKnown == link # "none" => linkedHead \in 1..head

\* Liveness: an open linked PR with a newer head is eventually re-linked (or stops being open).
RelinkOnNewHead == [](link = "open" /\ gh = "open" /\ linkedHead # head
                      => <>(linkedHead = head \/ gh # "open"))
\* Liveness: a merge on GitHub is eventually written back once a PR is linked.
MergeEventuallyWritten == [](gh = "merged" /\ link # "none" => <>(link = "merged"))
==============================================================================

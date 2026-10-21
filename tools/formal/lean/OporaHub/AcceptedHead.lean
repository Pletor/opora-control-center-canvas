/-
Accepted-head compare-and-set advance.

Implementation: database/repositories/opora_changesets.py `ChangesetRepository.advance`
(compare current head with `expected`, then INSERT or `UPDATE … WHERE accepted_id=expected`)
called by every acceptance after `insert(parentRevision=expected)` in the same transaction
(backend/canvas/opora_acceptance.py and the graph/content acceptances).

Specification:
* A stale `expected` (≠ current head) never advances; the state is unchanged.
* A successful advance records the new revision with parent = previous head.
* Starting from no head, every reachable state has a linear history: the newest log
  entry is the head and each entry's parent is the next older entry (or none for the root).
-/
namespace OporaHub.AcceptedHead

structure State where
  head : Option Nat
  /-- Accepted revisions, newest first: (revision, parentRevision). -/
  log : List (Nat × Option Nat)
  deriving DecidableEq, Repr

def init : State := ⟨none, []⟩

/-- CAS advance; `none` = rejected ("Přijatá revize se změnila"). -/
def advance (s : State) (expected : Option Nat) (rev : Nat) : Option State :=
  if s.head = expected then some ⟨some rev, (rev, expected) :: s.log⟩ else none

/-- Linear history anchored at `head`. -/
def Linear : Option Nat → List (Nat × Option Nat) → Prop
  | none, [] => True
  | some h, (r, p) :: rest => h = r ∧ Linear p rest
  | _, _ => False

theorem stale_never_advances (s : State) (expected : Option Nat) (rev : Nat)
    (stale : s.head ≠ expected) : advance s expected rev = none := by
  simp [advance, stale]

theorem advance_parent_is_previous_head (s s' : State) (expected : Option Nat) (rev : Nat)
    (h : advance s expected rev = some s') :
    s'.head = some rev ∧ s'.log = (rev, s.head) :: s.log := by
  unfold advance at h
  split at h
  · rename_i heq
    cases h
    simp [heq]
  · contradiction

theorem advance_preserves_linear (s s' : State) (expected : Option Nat) (rev : Nat)
    (lin : Linear s.head s.log) (h : advance s expected rev = some s') :
    Linear s'.head s'.log := by
  obtain ⟨hh, hl⟩ := advance_parent_is_previous_head s s' expected rev h
  rw [hh, hl]
  exact ⟨rfl, lin⟩

/-- Apply attempts in order; rejected attempts leave the state unchanged. Returns
the final state and whether each attempt advanced. -/
def run (s : State) : List (Option Nat × Nat) → State × List Bool
  | [] => (s, [])
  | (e, r) :: rest =>
    match advance s e r with
    | some s' => let (f, oks) := run s' rest; (f, true :: oks)
    | none => let (f, oks) := run s rest; (f, false :: oks)

theorem run_preserves_linear (s : State) (ops : List (Option Nat × Nat))
    (lin : Linear s.head s.log) : Linear (run s ops).1.head (run s ops).1.log := by
  induction ops generalizing s with
  | nil => exact lin
  | cons op rest ih =>
    obtain ⟨e, r⟩ := op
    simp only [run]
    split
    · rename_i s' h
      exact ih s' (advance_preserves_linear s s' e r lin h)
    · exact ih s lin

/-- Every reachable accepted history is linear. -/
theorem reachable_linear (ops : List (Option Nat × Nat)) :
    Linear (run init ops).1.head (run init ops).1.log :=
  run_preserves_linear init ops trivial

/-- The log grows by exactly one entry per successful advance (no lost or duplicated writes). -/
theorem run_log_length (s : State) (ops : List (Option Nat × Nat)) :
    (run s ops).1.log.length = s.log.length + ((run s ops).2.filter id).length := by
  induction ops generalizing s with
  | nil => simp [run]
  | cons op rest ih =>
    obtain ⟨e, r⟩ := op
    simp only [run]
    split
    · rename_i s' h
      have := (advance_parent_is_previous_head s s' e r h).2
      simp [ih s', this]
      omega
    · simp [ih s]

end OporaHub.AcceptedHead

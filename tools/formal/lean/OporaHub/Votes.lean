/-
Review vote aggregation and fingerprint dedupe.

Implementation: backend/canvas/opora_review_aggregation.py (`candidates`, `tally`) and the
posting step in backend/canvas/opora_review_job_tasks.py (`advance`: a finding is stored
exactly when `tally(...)["accepted"]`). Fingerprints are modelled as `Nat`; the
differential test renders them as zero-padded strings so string order equals `Nat` order.

Specification (written for humans first):
* A candidate is posted iff it was proposed and at least `required` voters confirmed it.
* A ballot covers every candidate exactly once (voter validation), so a finding needs
  `required` distinct voters: with fewer ballots nothing is posted.
* More confirming ballots never un-post a candidate.
* Dedupe returns each new fingerprint once, in ascending order, never a known one,
  is idempotent, and re-running after posting proposes nothing (no repost).
-/
namespace OporaHub.Votes

inductive Verdict where
  | confirm
  | reject
  deriving DecidableEq, Repr

structure Vote where
  cand : Nat
  verdict : Verdict
  deriving DecidableEq, Repr

abbrev Ballot := List Vote

/-- Confirms for candidate `c` in one ballot. -/
def confirmsIn (c : Nat) : Ballot → Nat
  | [] => 0
  | v :: vs => (if v.cand = c ∧ v.verdict = .confirm then 1 else 0) + confirmsIn c vs

/-- Confirms for candidate `c` over all ballots (`confirms` in `tally`). -/
def confirms (c : Nat) : List Ballot → Nat
  | [] => 0
  | b :: bs => confirmsIn c b + confirms c bs

/-- `tally(...)["accepted"]`: confirms ≥ required. -/
def accepted (required c : Nat) (bs : List Ballot) : Bool :=
  decide (required ≤ confirms c bs)

/-- Candidates the job posts as findings. -/
def posted (required : Nat) (cands : List Nat) (bs : List Ballot) : List Nat :=
  cands.filter (fun c => accepted required c bs)

theorem posted_iff (required c : Nat) (cands : List Nat) (bs : List Ballot) :
    c ∈ posted required cands bs ↔ c ∈ cands ∧ required ≤ confirms c bs := by
  simp [posted, accepted]

/-- A ballot that names `c` at most once contributes at most one confirm. -/
def AtMostOnce (c : Nat) (b : Ballot) : Prop := (b.filter (fun v => v.cand = c)).length ≤ 1

theorem confirmsIn_le_filter (c : Nat) (b : Ballot) :
    confirmsIn c b ≤ (b.filter (fun v => v.cand = c)).length := by
  induction b with
  | nil => simp [confirmsIn]
  | cons v vs ih =>
    by_cases h : v.cand = c
    · by_cases hv : v.verdict = .confirm
      · simp [confirmsIn, h, hv]; omega
      · simp [confirmsIn, h, hv]; omega
    · simp [confirmsIn, h]; omega

theorem confirms_le_ballots (c : Nat) (bs : List Ballot) (h : ∀ b ∈ bs, AtMostOnce c b) :
    confirms c bs ≤ bs.length := by
  induction bs with
  | nil => simp [confirms]
  | cons b bs ih =>
    have hb := confirmsIn_le_filter c b
    have h1 : AtMostOnce c b := h b (by simp)
    have h2 := ih (fun x hx => h x (by simp [hx]))
    simp [confirms, AtMostOnce] at *
    omega

/-- Threshold soundness: fewer valid ballots than `required` never posts anything. -/
theorem not_posted_below_quorum (required c : Nat) (cands : List Nat) (bs : List Ballot)
    (valid : ∀ b ∈ bs, AtMostOnce c b) (few : bs.length < required) :
    c ∉ posted required cands bs := by
  have := confirms_le_ballots c bs valid
  rw [posted_iff]
  omega

theorem confirms_append (c : Nat) (bs extra : List Ballot) :
    confirms c (bs ++ extra) = confirms c bs + confirms c extra := by
  induction bs with
  | nil => simp [confirms]
  | cons b bs ih => simp [confirms, ih]; omega

/-- Monotonicity: further ballots never retract a posted finding. -/
theorem posted_monotone (required c : Nat) (cands : List Nat) (bs extra : List Ballot)
    (h : c ∈ posted required cands bs) : c ∈ posted required cands (bs ++ extra) := by
  rw [posted_iff] at *
  rw [confirms_append]
  exact ⟨h.1, by omega⟩

/-! ### Fingerprint dedupe (`candidates`) -/

/-- Insert into a strictly ascending list, dropping duplicates. -/
def ins (x : Nat) : List Nat → List Nat
  | [] => [x]
  | y :: ys => if x < y then x :: y :: ys else if x = y then y :: ys else y :: ins x ys

/-- New fingerprints proposed for voting: unknown ones, each once, ascending. -/
def dedupe (known fps : List Nat) : List Nat :=
  (fps.filter (fun f => f ∉ known)).foldr ins []

theorem mem_ins (x a : Nat) (l : List Nat) : x ∈ ins a l ↔ x = a ∨ x ∈ l := by
  induction l with
  | nil => simp [ins]
  | cons y ys ih =>
    unfold ins
    split
    · simp
    · split
      · subst_vars; simp
      · simp [ih, or_left_comm]

theorem mem_foldr_ins (x : Nat) (l : List Nat) : x ∈ l.foldr ins [] ↔ x ∈ l := by
  induction l with
  | nil => simp
  | cons a l ih => simp [List.foldr, mem_ins, ih]

theorem mem_dedupe (x : Nat) (known fps : List Nat) :
    x ∈ dedupe known fps ↔ x ∈ fps ∧ x ∉ known := by
  simp [dedupe, mem_foldr_ins]

/-- No known (already posted, fixed or resolved) fingerprint is ever proposed again. -/
theorem dedupe_excludes_known (x : Nat) (known fps : List Nat) (h : x ∈ known) :
    x ∉ dedupe known fps := by
  rw [mem_dedupe]; simp [h]

theorem ins_sorted (x : Nat) (l : List Nat) (h : l.Pairwise (· < ·)) :
    (ins x l).Pairwise (· < ·) := by
  induction l with
  | nil => simp [ins]
  | cons y ys ih =>
    rw [List.pairwise_cons] at h
    unfold ins
    split
    · rename_i hxy
      refine List.Pairwise.cons ?_ (List.Pairwise.cons h.1 h.2)
      intro z hz
      simp at hz
      rcases hz with rfl | hz
      · exact hxy
      · exact Nat.lt_trans hxy (h.1 z hz)
    · split
      · exact List.Pairwise.cons h.1 h.2
      · rename_i hxy hne
        refine List.Pairwise.cons ?_ (ih h.2)
        intro z hz
        rw [mem_ins] at hz
        rcases hz with rfl | hz
        · omega
        · exact h.1 z hz

theorem foldr_ins_sorted (l : List Nat) : (l.foldr ins []).Pairwise (· < ·) := by
  induction l with
  | nil => simp
  | cons a l ih => exact ins_sorted a _ ih

/-- Each proposed fingerprint appears once, in ascending order. -/
theorem dedupe_sorted (known fps : List Nat) : (dedupe known fps).Pairwise (· < ·) :=
  foldr_ins_sorted _

theorem dedupe_nodup (known fps : List Nat) : (dedupe known fps).Nodup :=
  (dedupe_sorted known fps).imp (fun h => Nat.ne_of_lt h)

theorem foldr_ins_of_sorted (l : List Nat) (h : l.Pairwise (· < ·)) : l.foldr ins [] = l := by
  induction l with
  | nil => rfl
  | cons a l ih =>
    rw [List.pairwise_cons] at h
    simp only [List.foldr]
    rw [ih h.2]
    cases l with
    | nil => rfl
    | cons y ys =>
      have : a < y := h.1 y (by simp)
      simp [ins, this]

/-- Dedupe is idempotent. -/
theorem dedupe_idempotent (known fps : List Nat) :
    dedupe known (dedupe known fps) = dedupe known fps := by
  have hf : (dedupe known fps).filter (fun f => f ∉ known) = dedupe known fps := by
    rw [List.filter_eq_self]
    intro x hx
    have := (mem_dedupe x known fps).1 hx
    simp [this.2]
  have e : dedupe known (dedupe known fps)
      = ((dedupe known fps).filter (fun f => f ∉ known)).foldr ins [] := rfl
  rw [e, hf]
  exact foldr_ins_of_sorted _ (dedupe_sorted known fps)

/-- No repost: after posting the proposed fingerprints, the same submissions propose nothing. -/
theorem no_repost (known fps : List Nat) :
    dedupe (known ++ dedupe known fps) fps = [] := by
  have : fps.filter (fun f => f ∉ known ++ dedupe known fps) = [] := by
    rw [List.filter_eq_nil_iff]
    intro x hx
    by_cases hk : x ∈ known
    · simp [hk]
    · have : x ∈ dedupe known fps := (mem_dedupe x known fps).2 ⟨hx, hk⟩
      simp [this]
  have e : dedupe (known ++ dedupe known fps) fps
      = (fps.filter (fun f => f ∉ known ++ dedupe known fps)).foldr ins [] := rfl
  rw [e, this]
  rfl

end OporaHub.Votes

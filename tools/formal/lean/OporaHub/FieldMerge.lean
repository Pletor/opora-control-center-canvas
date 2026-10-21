/-
Field-level three-way merge for rebasing a stale proposal.

Implementation: backend/canvas/opora_field_merge.py `merge_fields(base, ours, theirs)`.
A record maps field → value; `none` means the field is absent. Server-side auto-rebase
(backend/canvas/opora_auto_rebase_merge.py) decides every field with `merge_field`, so this
is the proved decision rule of the automatic rebase.

Specification:
* Per field: unchanged on one side → take the other side; same change on both → take it;
  different changes on both → conflict.
* Swapping ours/theirs gives the same conflicts and the same merged values (commutative).
* When the changed fields are disjoint there is no conflict and both changes survive.
-/
namespace OporaHub.FieldMerge

abbrev Val := Option Nat
abbrev Record := Nat → Val

/-- `none` = conflict, `some v` = merged value (`v = none` means absent). -/
def mergeField (b o t : Val) : Option Val :=
  if o = b then some t else if t = b then some o else if o = t then some o else none

theorem mergeField_comm (b o t : Val) : mergeField b o t = mergeField b t o := by
  unfold mergeField
  by_cases h1 : o = b <;> by_cases h2 : t = b <;> by_cases h3 : o = t <;> simp_all
  exact fun h => h3 h.symm

theorem mergeField_conflict_iff (b o t : Val) :
    mergeField b o t = none ↔ o ≠ b ∧ t ≠ b ∧ o ≠ t := by
  unfold mergeField
  by_cases h1 : o = b <;> by_cases h2 : t = b <;> by_cases h3 : o = t <;> simp_all

/-- Disjoint change on one field: the changed side wins, the other side is kept. -/
theorem mergeField_disjoint (b o t : Val) (h : o = b ∨ t = b) :
    mergeField b o t = some (if o = b then t else o) := by
  unfold mergeField
  by_cases h1 : o = b <;> by_cases h2 : t = b <;> simp_all

def conflicts (fs : List Nat) (b o t : Record) : List Nat :=
  fs.filter (fun f => (mergeField (b f) (o f) (t f)).isNone)

def merged (fs : List Nat) (b o t : Record) : List (Nat × Val) :=
  fs.filterMap (fun f => (mergeField (b f) (o f) (t f)).map (fun v => (f, v)))

theorem conflicts_comm (fs : List Nat) (b o t : Record) : conflicts fs b o t = conflicts fs b t o := by
  simp [conflicts, mergeField_comm]

theorem merged_comm (fs : List Nat) (b o t : Record) : merged fs b o t = merged fs b t o := by
  simp [merged, mergeField_comm]

/-- Disjoint field changes merge without conflict. -/
theorem disjoint_no_conflict (fs : List Nat) (b o t : Record)
    (h : ∀ f ∈ fs, o f = b f ∨ t f = b f) : conflicts fs b o t = [] := by
  rw [conflicts, List.filter_eq_nil_iff]
  intro f hf
  simp [mergeField_disjoint _ _ _ (h f hf)]

/-- Disjoint field changes: every field carries our change, their change, or the base. -/
theorem disjoint_preserves_both (fs : List Nat) (b o t : Record)
    (h : ∀ f ∈ fs, o f = b f ∨ t f = b f) :
    merged fs b o t = fs.map (fun f => (f, if o f = b f then t f else o f)) := by
  induction fs with
  | nil => rfl
  | cons f fs ih =>
    have hf := mergeField_disjoint _ _ _ (h f (by simp))
    have rest := ih (fun g hg => h g (by simp [hg]))
    simp only [merged, List.filterMap_cons, hf, Option.map_some] at rest ⊢
    rw [rest]
    rfl

/-- Corollary: a field only we changed keeps our value; a field only they changed keeps theirs. -/
theorem ours_kept (b o t : Val) (ho : o ≠ b) (ht : t = b) : mergeField b o t = some o := by
  rw [mergeField_disjoint _ _ _ (Or.inr ht)]; simp [ho]

theorem theirs_kept (b o t : Val) (ho : o = b) : mergeField b o t = some t := by
  rw [mergeField_disjoint _ _ _ (Or.inl ho)]; simp [ho]

end OporaHub.FieldMerge

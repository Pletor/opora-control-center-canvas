/-
Executable test vectors from the proved models (`lake exe vectors > vectors.json`).

backend/canvas/test_opora_lean_differential.py runs the real Python functions on the same
inputs and compares. CI regenerates this file and fails when it drifts from the committed
copy, so model, vectors and implementation stay in lock-step.
-/
import OporaHub

open OporaHub

/-- Deterministic LCG; the vectors must be byte-identical on every machine. -/
def step (s : Nat) : Nat := (s * 1103515245 + 12345) % 2147483648

def pick (s n : Nat) : Nat × Nat := let s' := step s; ((s' / 65536) % n, s')

def jsonList (xs : List String) : String := "[" ++ ",".intercalate xs ++ "]"
def jNat (n : Nat) : String := toString n
def jOpt : Option Nat → String
  | none => "null"
  | some n => toString n
def jNats (xs : List Nat) : String := jsonList (xs.map jNat)

def genList (s count bound : Nat) : List Nat × Nat := Id.run do
  let mut out := []
  let mut st := s
  for _ in [0:count] do
    let (v, st') := pick st bound
    out := out ++ [v]
    st := st'
  return (out, st)

/-! Votes: every ballot covers every candidate exactly once (voter validation). -/
def votesCase (seed : Nat) : String := Id.run do
  let (nc, s) := pick seed 5
  let (nv, s) := pick s 4
  let (r0, s) := pick s 4
  let cands := (List.range (nc + 1))
  let voters := nv + 1
  let required := r0 + 1
  let mut st := s
  let mut ballots : List Votes.Ballot := []
  for _ in [0:voters] do
    let mut ballot : Votes.Ballot := []
    for c in cands do
      let (v, st') := pick st 3
      st := st'
      ballot := ballot ++ [⟨c, if v = 0 then .reject else .confirm⟩]
    ballots := ballots ++ [ballot]
  let jb := ballots.map fun b => jsonList (b.map fun v =>
    "[" ++ jNat v.cand ++ ",\"" ++ (if v.verdict = .confirm then "confirm" else "reject") ++ "\"]")
  return "{\"required\":" ++ jNat required ++ ",\"candidates\":" ++ jNats cands ++
    ",\"ballots\":" ++ jsonList jb ++ ",\"posted\":" ++ jNats (Votes.posted required cands ballots) ++ "}"

def dedupeCase (seed : Nat) : String := Id.run do
  let (nk, s) := pick seed 4
  let (known, s) := genList s nk 12
  let (ns, s) := pick s 3
  let mut st := s
  let mut subs : List (List Nat) := []
  for _ in [0:ns + 1] do
    let (len, st1) := pick st 5
    let (fps, st2) := genList st1 len 12
    subs := subs ++ [fps]
    st := st2
  let proposed := Votes.dedupe known subs.flatten
  return "{\"known\":" ++ jNats known ++ ",\"submissions\":" ++ jsonList (subs.map jNats) ++
    ",\"proposed\":" ++ jNats proposed ++ "}"

/-! CAS: expected is the current head, a stale older revision, or none. -/
def casCase (seed : Nat) : String := Id.run do
  let (n, s) := pick seed 7
  let mut st := s
  let mut ops : List (Option Nat × Nat) := []
  let mut sim := AcceptedHead.init
  let mut seen : List Nat := []
  for i in [0:n + 1] do
    let (choice, st1) := pick st 4
    let (idx, st2) := pick st1 (seen.length + 1)
    st := st2
    let expected := if choice ≤ 1 then sim.head else if choice = 2 then none else seen[idx]?
    let rev := 100 + i
    ops := ops ++ [(expected, rev)]
    seen := seen ++ [rev]
    sim := (AcceptedHead.run sim [(expected, rev)]).1
  let (final, oks) := AcceptedHead.run AcceptedHead.init ops
  let jo := ops.map fun (e, r) => "[" ++ jOpt e ++ "," ++ jNat r ++ "]"
  let jl := final.log.map fun (r, p) => "[" ++ jNat r ++ "," ++ jOpt p ++ "]"
  return "{\"ops\":" ++ jsonList jo ++ ",\"oks\":" ++ jsonList (oks.map fun b => if b then "true" else "false") ++
    ",\"head\":" ++ jOpt final.head ++ ",\"log\":" ++ jsonList jl ++ "}"

def mergeCase (seed : Nat) : String := Id.run do
  let fields := List.range 4
  let (bs, s) := genList seed 4 3
  let (os, s) := genList s 4 3
  let (ts, _) := genList s 4 3
  -- value 0 = absent, otherwise the value itself.
  let rec' : List Nat → FieldMerge.Record := fun xs f => match xs[f]? with
    | some 0 | none => none
    | some v => some v
  let b := rec' bs
  let o := rec' os
  let t := rec' ts
  let jr : FieldMerge.Record → String := fun r => jsonList (fields.map fun f => jOpt (r f))
  let jm := (FieldMerge.merged fields b o t).map fun (f, v) => "[" ++ jNat f ++ "," ++ jOpt v ++ "]"
  return "{\"fields\":" ++ jNats fields ++ ",\"base\":" ++ jr b ++ ",\"ours\":" ++ jr o ++
    ",\"theirs\":" ++ jr t ++ ",\"conflicts\":" ++ jNats (FieldMerge.conflicts fields b o t) ++
    ",\"merged\":" ++ jsonList jm ++ "}"

def cases (f : Nat → String) (salt : Nat) : String :=
  jsonList ((List.range 60).map fun i => f (step (i * 7919 + salt)))

def main : IO Unit :=
  IO.println ("{\"schemaVersion\":1,\"votes\":" ++ cases votesCase 1 ++ ",\"dedupe\":" ++ cases dedupeCase 2 ++
    ",\"cas\":" ++ cases casCase 3 ++ ",\"merge\":" ++ cases mergeCase 4 ++ "}")

// Sloty dokladů karty (docs/proces-karty.md §2): čtyři pevná místa Testy · Security · Review · Merge, jejichž
// stav se počítá z uložených důkazů (`evidence`), kontrol karty (`checks`) a pipeline etap, ne z poznámek agenta.
// Čistá data bez funkcí, aby je `stable-nodes.ts` mohl porovnat hluboce.
import type { CompletionEvidence, Proof } from "../components/CardEvidence";
import type { CardPipeline, PipelineStage } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import { pipelineSummary } from "@/editor/workflow/card-pipeline/logic/pipeline-model";

export type ProofKey = "tests" | "security" | "review" | "merge";
export type ProofStatus = "none" | "declared" | "proven" | "failed" | "na" | "running";
export type ProofSlot = { key: ProofKey; label: string; status: ProofStatus; title: string };

export const PROOF_LABEL: Record<ProofKey, string> = { tests: "Testy", security: "Security", review: "Review", merge: "Merge" };
export const PROOF_STATUS_LABEL: Record<ProofStatus, string> = {
  none: "nedoloženo", declared: "deklarováno bez dokladu", proven: "doklad přiložen (server neověřuje)", failed: "selhalo", na: "nevztahuje se", running: "běží",
};

type Check = { id: string; command: string };
type StageLook = { running: boolean; stuck: boolean; passed: boolean; doneBy: string };

/** Pohled na etapy jednoho druhu: rozhoduje **poslední** etapa druhu (starší úspěch nedokládá novější audit;
 *  po selhání a opakování platí až výsledek opakování), uvíznutí počítá `pipelineSummary`. */
function stages(pipeline: CardPipeline | undefined, pick: (s: PipelineStage) => boolean): StageLook {
  const items = (pipeline?.items ?? []).filter((s) => s.approved && pick(s));
  const stuck = pipeline ? new Set(pipelineSummary(pipeline).stuck.map((s) => s.id)) : new Set<string>();
  const last = items[items.length - 1];
  return {
    running: items.some((s) => s.status === "doing"),
    stuck: items.some((s) => stuck.has(s.id)),
    passed: last?.status === "passed",
    doneBy: last?.status === "passed" ? last.doneBy : "",
  };
}

const slot = (key: ProofKey, status: ProofStatus, ...notes: string[]): ProofSlot => ({
  key, label: PROOF_LABEL[key], status,
  title: [PROOF_LABEL[key], PROOF_STATUS_LABEL[status], ...notes.filter(Boolean)].join(" · "),
});

/** Důkaz s odkazem nebo s jiným dokladem; `passed` bez dokladu je jen deklarace. Běžící etapa (opakování po
 *  selhání) pulsuje i přes starší selhaný důkaz; uvíznutí a selhání bez běhu jsou červené. */
function proofStatus(proof: Proof | undefined, look: StageLook, proven: boolean): ProofStatus {
  if (look.running) return "running";
  if (look.stuck || proof?.status === "failed") return "failed";
  if (proof?.status === "not_applicable") return "na";
  if (proof?.status === "passed") return proven ? "proven" : "declared";
  return look.passed ? "declared" : "none";
}

/** Testy: důkaz testů, běhy kontrol a předepsané kontroly karty musí sedět dohromady. */
function testsSlot(evidence: CompletionEvidence | undefined, checks: Check[], pipeline: CardPipeline | undefined): ProofSlot {
  const look = stages(pipeline, (s) => s.kind === "test");
  const runs = evidence?.checksRun ?? [];
  const runOf = (check: Check) => runs.find((r) => r.checkId === check.id && r.command === check.command);
  const ran = runs.map((r) => (r.exitCode === 0 ? "✓ " : "✗ ") + r.checkId);
  const missing = checks.filter((c) => !runOf(c)).map((c) => "… " + c.id);
  const notes = [...ran, ...missing].join(", ");
  const failedRun = runs.some((r) => r.exitCode !== 0);
  const allChecks = checks.every((c) => runOf(c)?.exitCode === 0);
  const proof = evidence?.tests;
  if (failedRun && !look.running) return slot("tests", "failed", notes);
  // Doklad je, ale některá předepsaná kontrola karty neběžela: deklarováno, tooltip řekne která („… e2e“).
  const proven = !!proof && (!!proof.url || runs.length > 0) && allChecks;
  const status = proofStatus(proof, look, proven);
  return slot("tests", status, status === "na" ? proof?.note ?? "" : notes);
}

/** Security: kritik hacker (útok) v pipeline; bez něj je slot prázdný, nikdy „nevztahuje se“. */
function securitySlot(pipeline: CardPipeline | undefined): ProofSlot {
  const look = stages(pipeline, (s) => s.kind === "critic" && s.lens === "hacker");
  if (look.running) return slot("security", "running", "kritik hacker");
  if (look.stuck) return slot("security", "failed", "kritik hacker selhal, čeká na tebe");
  if (look.passed) return slot("security", "proven", "kritik hacker prošel", look.doneBy);
  return slot("security", "none", "kritik hacker zatím neproběhl");
}

function linkedSlot(key: "review" | "merge", evidence: CompletionEvidence | undefined, pipeline: CardPipeline | undefined): ProofSlot {
  const look = key === "review" ? stages(pipeline, (s) => s.kind === "review") : { running: false, stuck: false, passed: false, doneBy: "" };
  const proof = evidence?.[key];
  const status = proofStatus(proof, look, !!proof?.url);
  return slot(key, status, status === "na" ? proof?.note ?? "" : proof?.note ?? "");
}

/** Čtyři sloty v pevném pořadí; stejné pořadí má karta bez pipeline i bez důkazů. */
export function proofSlots(evidence: CompletionEvidence | undefined, checks: Check[] | undefined, pipeline: CardPipeline | undefined): ProofSlot[] {
  return [
    testsSlot(evidence, checks ?? [], pipeline),
    securitySlot(pipeline),
    linkedSlot("review", evidence, pipeline),
    linkedSlot("merge", evidence, pipeline),
  ];
}

/** Věta pro čtečku: „Doklady: Testy doloženo, Security nedoloženo, …“. */
export const proofSentence = (slots: ProofSlot[]) => "Doklady: " + slots.map((s) => s.label + " " + PROOF_STATUS_LABEL[s.status]).join(", ");

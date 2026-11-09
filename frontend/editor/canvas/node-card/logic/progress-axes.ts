import type { CardFace } from "@/editor/canvas/card-face/logic/card-face";
import type { CardView } from "./card-model";
export type ProgressAxis = { label: string; value: string; detail: string };
/** Only describe the evidence actually present. Workflow closure and prototypes do not prove operation. */
export function progressAxes(view: Pick<CardView, "design"> & Partial<Pick<CardView, "name">>, face?: CardFace): ProgressAxis[] {
  const preparatory = ["prototype", "research", "grilling"].some(kind => face?.kindChip === kind || view.name?.startsWith(`[${kind}] `));
  const running = !preparatory && face?.raw.stage === "work" && !!face.raw.executionId;
  const merged = !preparatory && ["plan_written_back", "card_closed", "awaiting_human_close"].includes(face?.raw.reason ?? "");
  const accepted = !preparatory && face?.progressEvidence?.designAccepted;
  const proof = !preparatory ? face?.progressEvidence?.verification : undefined;
  const evidenced = proof?.verified === true && proof.independent === false && proof.level === "reported_evidence"
    && (proof.currentAcceptedRevision ?? proof.acceptedRevision) === face?.progressEvidence?.acceptedRevision;
  const evidenceDetail = evidenced ? `Kancelář doložila kladný i záporný integrační test; revize ${proof.acceptedRevision}, commit ${proof.headSha}, běh ${proof.executionId}, doklad ${proof.receiptId}. Nejde o nezávislé spuštění testů.` : "";
  if (evidenced) return [
    { label: "Návrh", value: accepted ? "Přijatý" : "Nedoloženo", detail: `Přijatá revize ${face?.progressEvidence?.acceptedRevision}` },
    { label: "Realizace", value: "Doložena Kanceláří", detail: evidenceDetail },
    { label: "Ověření", value: "Doloženo Kanceláří", detail: evidenceDetail },
  ];
  return [
    { label: "N\u00e1vrh", value: accepted ? "Přijatý" : view.design ? "Podklad existuje" : "Nedolo\u017eeno", detail: accepted ? `Přijatá revize ${face?.progressEvidence?.acceptedRevision}` : view.design ? `Artefakt ${view.design.version}; p\u0159ijet\u00ed n\u00e1vrhu nen\u00ed v t\u011bchto datech dolo\u017eeno.` : "Chyb\u00ed doklad p\u0159ijat\u00e9ho n\u00e1vrhu." },
    { label: "Realizace", value: merged ? "Práce začleněna" : running ? "Prob\u00edh\u00e1" : !preparatory && face?.raw.executionId ? "B\u011bh evidov\u00e1n" : "Nedolo\u017eeno", detail: preparatory ? "Prototyp nebo rešerše nedokládají realizaci funkce." : merged ? "Agent-state eviduje za\u010dlen\u011bn\u00ed t\u00e9to pr\u00e1ce; funk\u010dn\u00ed ov\u011b\u0159en\u00ed je samostatn\u00e9." : face?.raw.executionId ? `Realizace ${face.raw.executionId}` : "Bez nav\u00e1zan\u00e9 realizace v agent-state." },
    { label: "Ov\u011b\u0159en\u00ed", value: "Nedolo\u017eeno", detail: face?.raw.gateStatus === "ready" ? "Technick\u00e1 br\u00e1na je p\u0159ipraven\u00e1. Tyto vstupy neobsahuj\u00ed d\u016fkaz funk\u010dn\u00ed zkou\u0161ky konkr\u00e9tn\u00ed revize." : "Chyb\u00ed d\u016fkaz funk\u010dn\u00ed zkou\u0161ky konkr\u00e9tn\u00ed revize." },
  ];
}

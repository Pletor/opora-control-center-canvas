import type { SpecFields } from "@/shared/types/logic/types";
export type PlanDocument = { nodeId: string; ownerWorkspace: string; revision: number; fields: SpecFields };
export type PlanContext = { acceptedHead: string | null; graphDigest: string; specificationsVersion: string;
  documents: PlanDocument[]; acceptedDocuments: PlanDocument[]; workingDiffers: boolean; readOnly: boolean };
export type PlanChange = { nodeId: string; ownerWorkspace: string; expectedRevision: number; before: SpecFields; acceptedBefore: PlanDocument; fields: SpecFields };
export type PlanChangeset = { id: string; parentRevision: string; subject: string; by: { kind: string; name: string };
  createdAt: string; changes: PlanChange[]; accepted: boolean };
export const fieldLabels: Record<keyof SpecFields, string> = {
  goal: "Cíl", non_goals: "Omezení a co není cílem", acceptance: "Podmínky dokončení",
};
export const fieldLimits: Record<keyof SpecFields, number> = { goal: 4000, non_goals: 8000, acceptance: 12000 };
export const fieldKeys = Object.keys(fieldLabels) as (keyof SpecFields)[];
export function changedFields(before: SpecFields, after: SpecFields) {
  return fieldKeys.filter(key => before[key] !== after[key]);
}
export function changesetPayload(project: string, workspace: string, subject: string, context: PlanContext,
  document: PlanDocument, fields: SpecFields) {
  if (!context.acceptedHead) throw new Error("Nejprve přijměte základ zadání.");
  const accepted = context.acceptedDocuments.find(item => item.nodeId === document.nodeId);
  if (!accepted) throw new Error("Nová karta ještě není v přijatém základu; změny grafu tato etapa nepodporuje.");
  if (!changedFields(document.fields, fields).length && !changedFields(accepted.fields, fields).length) throw new Error("Návrh neobsahuje změnu.");
  return { project, workspace, subject: subject.trim(), parentRevision: context.acceptedHead,
    expectedGraphDigest: context.graphDigest,
    changes: [{ nodeId: document.nodeId, expectedRevision: document.revision, fields: { ...fields } }] };
}

export function inspectedFields(change: PlanChange) {
  return fieldKeys.filter(key => change.acceptedBefore.fields[key] !== change.fields[key] || change.before[key] !== change.fields[key]);
}

type PlanScope = { project: string; workspace: string };
/** Server mutation effects survive leaving Hub, but never target another project's editor. */
export function notifyCurrentPlanScope(captured: PlanScope, current: PlanScope, notify: () => void) {
  if (captured.project !== current.project || captured.workspace !== current.workspace) return;
  notify();
}

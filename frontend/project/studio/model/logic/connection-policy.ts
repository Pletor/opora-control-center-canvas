// Pravidla rolí vazeb Studia (prototyp `connection-policy.mjs`). Shodný datový typ portů nestačí: HTTP vazba musí
// vést jen na roli, kterou Studio pozorovaně dovolí (`observed-http-roles.ts`), řízený Pod se propojuje přes svůj
// Deployment a pár asynchronních vazeb na serverless a object-store je omezený. Mimo HTTP platí jen typy portů.
import { observedHttpRoles } from "./observed-http-roles";
import type { PortType } from "./model-types";

/** Pravidla Studia v2 (výchozí pro model). */
export const STUDIO_POLICY = "studio-roles/2";
/** Jen typy portů bez rolí (pro kontrolu typové matice a pro starší definice prototypu). */
export const TYPED_POLICY = "typed-ports/1";
export type ConnectionPolicy = typeof STUDIO_POLICY | typeof TYPED_POLICY;

export type RoleEndpoint = { type: string; name: string; parentId?: string };

const OBJECT_STORES = ["aws-s3", "gcp-gcs", "aliyun-oss"];
const OBJECT_EVENT_TARGETS = ["aws-lambda", "gcp-cloud-run", "aliyun-fc", "stream-processor", "aws-sqs", "gcp-cloud-tasks", "gcp-pubsub", "aliyun-mns", "aliyun-rocketmq"];
const SERVERLESS = ["aws-lambda", "gcp-cloud-run", "aliyun-fc"];

/** Proč role nedovolí vazbu `from → to` s datovým typem `type`; null = dovoleno. */
export function roleConnectionError(from: RoleEndpoint, to: RoleEndpoint, type: PortType, policy: ConnectionPolicy = STUDIO_POLICY): string | null {
  if (policy !== STUDIO_POLICY) return null;
  if ((from.type === "pod" && from.parentId) || (to.type === "pod" && to.parentId))
    return "Vazba obchází hranici rodiče: řízený Pod propojujte přes Kubernetes Deployment.";
  // Všechny tři object-store výběry událostí pozorovaly stejných devět cílů.
  if (OBJECT_STORES.includes(from.type) && type === "event" && !OBJECT_EVENT_TARGETS.includes(to.type))
    return "Object-store events require an observed function, stream or provider-queue target.";
  if (SERVERLESS.includes(to.type) && ((type === "event" && from.type === "event-producer") || (type === "job" && from.type === "queue")
    || (to.type === "aws-lambda" && type === "event" && ["scheduled-job-cron", "workflow-orchestrator"].includes(from.type))))
    return `Role Studia: ${from.name} nelze přímo propojit s ${to.name} tímto asynchronním portem.`;
  if (type !== "http-request") return null;
  if (observedHttpRoles[from.type]?.includes(to.type)) return null;
  return `Role Studia: ${from.name} (${from.type}) nelze přímo propojit s ${to.name} (${to.type}). Datový typ HTTP se shoduje, role nikoli.`;
}

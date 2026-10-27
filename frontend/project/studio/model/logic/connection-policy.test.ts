// Pravidla rolí převedená z prototypu `test/connection-policy.test.mjs`. Nezávislá matice full80 (REA, 24 zdrojů,
// `analysis/evidence/full80-http-role-matrix.json`) je zhuštěná na jedinečné dvojice zdroj → cíl typů katalogu.
import { describe, expect, it } from "vitest";
import { roleConnectionError, STUDIO_POLICY, TYPED_POLICY } from "./connection-policy";

const FULL80: Record<string, { valid: string[]; invalid: string[] }> = {
  "client": { valid: ["aliyun-alb","aliyun-api-gateway","aliyun-cdn","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","cdn-edge-cache","circuit-breaker","frontend-app","gcp-api-gateway","gcp-cloud-cdn","gcp-lb","load-balancer"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-fc","aws-eks-cluster","aws-lambda","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","pod","service","service-mesh"] },
  "cdn-edge-cache": { valid: ["aliyun-alb","aliyun-api-gateway","auth-provider","aws-alb","aws-api-gateway","frontend-app","gcp-api-gateway","gcp-lb"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-cdn","aliyun-fc","api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "aws-cloudfront": { valid: ["aliyun-alb","aliyun-api-gateway","auth-provider","aws-alb","aws-api-gateway","frontend-app","gcp-api-gateway","gcp-lb"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-cdn","aliyun-fc","api-gateway","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "gcp-cloud-cdn": { valid: ["aliyun-alb","aliyun-api-gateway","auth-provider","aws-alb","aws-api-gateway","frontend-app","gcp-api-gateway","gcp-lb"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-cdn","aliyun-fc","api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "aliyun-cdn": { valid: ["aliyun-alb","aliyun-api-gateway","auth-provider","aws-alb","aws-api-gateway","frontend-app","gcp-api-gateway","gcp-lb"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-fc","api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "frontend-app": { valid: ["aliyun-alb","aliyun-api-gateway","api-gateway","auth-provider","aws-alb","aws-api-gateway","circuit-breaker","gcp-api-gateway","gcp-lb","load-balancer"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-cdn","aliyun-fc","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","pod","service","service-mesh"] },
  "api-gateway": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "load-balancer": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-fc","aws-eks-cluster","aws-lambda","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","service"], invalid: ["aliyun-alb","aliyun-api-gateway","aliyun-cdn","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","cdn-edge-cache","circuit-breaker","frontend-app","gcp-api-gateway","gcp-cloud-cdn","gcp-lb","pod","service-mesh"] },
  "sync-client": { valid: ["aliyun-alb","aliyun-api-gateway","aliyun-cdn","api-gateway","aws-api-gateway","aws-cloudfront","cdn-edge-cache","circuit-breaker","frontend-app","gcp-api-gateway","gcp-cloud-cdn","gcp-lb"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-fc","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "aws-alb": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-fc","aws-eks-cluster","aws-lambda","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","service"], invalid: ["aliyun-alb","aliyun-api-gateway","aliyun-cdn","api-gateway","auth-provider","aws-api-gateway","aws-cloudfront","cdn-edge-cache","circuit-breaker","frontend-app","gcp-api-gateway","gcp-cloud-cdn","gcp-lb","load-balancer","pod","service-mesh"] },
  "aws-api-gateway": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "gcp-lb": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "gcp-api-gateway": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "aliyun-alb": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "aliyun-api-gateway": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "circuit-breaker": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "host-policy-gate": { valid: ["aliyun-api-gateway","api-gateway","aws-api-gateway","gcp-api-gateway"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-cdn","aliyun-fc","auth-provider","aws-alb","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","frontend-app","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "auth-provider": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service","service-mesh"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "service-mesh": { valid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-eks-cluster","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","service"], invalid: ["aliyun-cdn","aws-api-gateway","aws-cloudfront","cdn-edge-cache","frontend-app","gcp-cloud-cdn","pod"] },
  "analytical-store": { valid: ["frontend-app"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-cdn","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-api-gateway","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "aws-redshift": { valid: ["frontend-app"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-cdn","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-api-gateway","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "gcp-bigquery": { valid: ["frontend-app"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-cdn","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-api-gateway","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "aliyun-maxcompute": { valid: ["frontend-app"], invalid: ["ai-inference","aliyun-ack-cluster","aliyun-alb","aliyun-api-gateway","aliyun-cdn","aliyun-fc","api-gateway","auth-provider","aws-alb","aws-api-gateway","aws-cloudfront","aws-eks-cluster","aws-lambda","cdn-edge-cache","circuit-breaker","gcp-api-gateway","gcp-cloud-cdn","gcp-cloud-run","gcp-gke-cluster","gcp-lb","kubernetes-deployment","load-balancer","pod","service","service-mesh"] },
  "api-adapter": { valid: ["ai-inference","aliyun-alb","aliyun-api-gateway","aliyun-fc","api-gateway","aws-alb","aws-api-gateway","aws-lambda","circuit-breaker","gcp-api-gateway","gcp-cloud-run","gcp-lb","load-balancer","service","service-mesh"], invalid: ["aliyun-ack-cluster","aliyun-cdn","auth-provider","aws-cloudfront","aws-eks-cluster","cdn-edge-cache","frontend-app","gcp-cloud-cdn","gcp-gke-cluster","kubernetes-deployment","pod"] },
};

const end = (type: string, parentId?: string) => ({ type, name: type, ...(parentId ? { parentId } : {}) });

describe("roleConnectionError", () => {
  it("souhlasí s každou HTTP anotací nezávislé matice full80", () => {
    let checked = 0;
    for (const [source, { valid, invalid }] of Object.entries(FULL80)) {
      for (const target of valid) { expect(roleConnectionError(end(source), end(target), "http-request"), `${source} -> ${target}`).toBeNull(); checked++; }
      for (const target of invalid) { expect(roleConnectionError(end(source), end(target), "http-request"), `${source} -> ${target}`).not.toBeNull(); checked++; }
    }
    expect(Object.keys(FULL80)).toHaveLength(24);
    expect(checked).toBeGreaterThan(400);
  });

  it("řízený Pod se propojuje jen přes Deployment, samostatný Pod smí", () => {
    expect(roleConnectionError(end("pod", "controller"), end("postgresql"), "sql-query")).toMatch(/hranici rodiče/);
    expect(roleConnectionError(end("pod"), end("postgresql"), "sql-query")).toBeNull();
  });

  it("události object-store jen na pozorované funkce, proudy a fronty", () => {
    expect(roleConnectionError(end("aws-s3"), end("aws-lambda"), "event")).toBeNull();
    expect(roleConnectionError(end("aws-s3"), end("queue"), "event")).toMatch(/Object-store/);
  });

  it("serverless nepřijme producenta událostí ani frontu přímo", () => {
    expect(roleConnectionError(end("event-producer"), end("aws-lambda"), "event")).toMatch(/asynchronním/);
    expect(roleConnectionError(end("queue"), end("gcp-cloud-run"), "job")).toMatch(/asynchronním/);
    expect(roleConnectionError(end("scheduled-job-cron"), end("aws-lambda"), "event")).toMatch(/asynchronním/);
    expect(roleConnectionError(end("scheduled-job-cron"), end("gcp-cloud-run"), "event")).toBeNull();
  });

  it("mimo HTTP rozhodují jen typy portů a typová pravidla role nekontrolují", () => {
    expect(roleConnectionError(end("service"), end("postgresql"), "sql-query")).toBeNull();
    expect(roleConnectionError(end("client"), end("service"), "http-request", STUDIO_POLICY)).toMatch(/Role Studia/);
    expect(roleConnectionError(end("client"), end("service"), "http-request", TYPED_POLICY)).toBeNull();
  });
});

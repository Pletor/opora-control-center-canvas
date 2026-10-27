// Pozorované cíle HTTP vazeb podle role (pravidla Studia v2, `studio-roles/2`). Převzato 1:1 z prototypu
// `observed-http-roles.mjs` (generováno z REA pozorování, ne z upstream kódu). Čistě datová tabulka, jeden zdroj na řádek.

/** typ zdroje → typy, na jejichž `http-in` smí vést `http-request`. */
export const observedHttpRoles: Readonly<Record<string, readonly string[]>> = {
  "client": ["frontend-app","cdn-edge-cache","api-gateway","load-balancer","aws-cloudfront","aws-alb","aws-api-gateway","gcp-cloud-cdn","gcp-lb","gcp-api-gateway","aliyun-cdn","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider"],
  "cdn-edge-cache": ["frontend-app","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","auth-provider"],
  "aws-cloudfront": ["frontend-app","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","auth-provider"],
  "gcp-cloud-cdn": ["frontend-app","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","auth-provider"],
  "aliyun-cdn": ["frontend-app","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","auth-provider"],
  "frontend-app": ["api-gateway","load-balancer","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider"],
  "api-gateway": ["load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "load-balancer": ["service","ai-inference","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "sync-client": ["frontend-app","cdn-edge-cache","api-gateway","aws-cloudfront","aws-api-gateway","gcp-cloud-cdn","gcp-lb","gcp-api-gateway","aliyun-cdn","aliyun-alb","aliyun-api-gateway","circuit-breaker"],
  "aws-alb": ["service","ai-inference","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "aws-api-gateway": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "gcp-lb": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "gcp-api-gateway": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "aliyun-alb": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-api-gateway","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "aliyun-api-gateway": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","circuit-breaker","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "circuit-breaker": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","auth-provider","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster","circuit-breaker"],
  "host-policy-gate": ["api-gateway","aws-api-gateway","gcp-api-gateway","aliyun-api-gateway"],
  "auth-provider": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","service-mesh","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "service-mesh": ["api-gateway","load-balancer","service","ai-inference","aws-alb","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","auth-provider","kubernetes-deployment","aws-lambda","aws-eks-cluster","gcp-cloud-run","gcp-gke-cluster","aliyun-fc","aliyun-ack-cluster"],
  "analytical-store": ["frontend-app"],
  "aws-redshift": ["frontend-app"],
  "gcp-bigquery": ["frontend-app"],
  "aliyun-maxcompute": ["frontend-app"],
  "api-adapter": ["api-gateway","load-balancer","service","ai-inference","aws-alb","aws-api-gateway","gcp-lb","gcp-api-gateway","aliyun-alb","aliyun-api-gateway","circuit-breaker","service-mesh","aws-lambda","gcp-cloud-run","aliyun-fc"],
};

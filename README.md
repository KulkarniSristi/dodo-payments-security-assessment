# Dodo Payments — Security & DevOps Engineer Assessment

Hardened Kubernetes workload, secure CI/CD supply chain, Istio zero-trust mesh, and recon/penetration testing for `ledger-api`, a PCI-DSS-scoped payments microservice.

## Structure
- [`task1-harden-workload/`](./task1-harden-workload) — Workload hardening, RBAC, secrets management, Kyverno guardrails ✅
- [`task2-cicd-supply-chain/`](./task2-cicd-supply-chain) — Secure CI/CD pipeline (Semgrep, Trivy, Gitleaks) + GitOps via ArgoCD ✅
- `task3-zero-trust-mesh/` — Istio mTLS + zero-trust networking (in progress)
- `task4-recon-pentest/` — OSINT recon + penetration test (pending)

## Status summary
All four tasks run entirely locally (kind on WSL2/Ubuntu, no cloud account). Each task folder contains its own README with implementation details, evidence, and documented trade-offs/limitations encountered along the way.

## Environment
Runs fully local: kind (Kubernetes in Docker) on WSL2/Ubuntu, no cloud account required.

## Known Gaps / With More Time

**RBAC personas (Task 1 bonus) - partial:**
Three Roles (payments-developer, payments-operator, payments-admin) are defined
in task1-harden-workload/deploy/08-rbac-personas.yaml with correctly scoped verb
sets and are applied to the cluster. RoleBindings to actual ServiceAccounts/Users
were not completed due to time constraints. With more time: create a
ServiceAccount per persona (kubectl create serviceaccount), bind each to its
matching Role via RoleBinding, and verify enforcement with
kubectl auth can-i --as=system:serviceaccount:payments:<persona-sa> <verb> <resource>.

**Kyverno require-image-signature exclusion (Task 1):**
The require-image-signature ClusterPolicy was originally cluster-wide and blocked
ArgoCD's own dex-server pod (ghcr.io/dexidp/dex:v2.45.0, unsigned), since ArgoCD's
control-plane images are not part of the signed supply chain this assessment
covers. Added an exclude block for the argocd and kube-system namespaces so the
policy only enforces on application workloads, not cluster infrastructure. With
more time: sign or vendor-verify ArgoCD's own images too, so the exclusion isn't
needed and image-signature enforcement is truly cluster-wide.

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

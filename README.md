# Dodo Payments — Security & DevOps Engineer Assessment

Hardened Kubernetes workload, secure CI/CD supply chain, Istio zero-trust mesh, and recon/penetration testing for `ledger-api`, a PCI-DSS-scoped payments microservice.

## Structure
- [`task1-harden-workload/`](./task1-harden-workload) — Workload hardening, RBAC, secrets management, Kyverno guardrails
- `task2-cicd-supply-chain/` — Secure CI/CD pipeline + GitOps (in progress)
- `task3-zero-trust-mesh/` — Istio mTLS + zero-trust networking (pending)
- `task4-recon-pentest/` — OSINT recon + penetration test (pending)

## Environment
Runs fully local: kind (Kubernetes in Docker) on WSL2/Ubuntu, no cloud account required.

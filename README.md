# Dodo Payments — Security & DevOps Engineer Assessment

Hardened Kubernetes workload, secure CI/CD supply chain, Istio zero-trust mesh, and recon/penetration testing for ledger-api, a PCI-DSS-scoped payments microservice.

Everything runs fully local - kind (Kubernetes in Docker) on WSL2/Ubuntu, free-tier tooling only, no cloud account required.

## Structure

- [task1-harden-workload/](./task1-harden-workload) - Workload hardening: securityContext, RBAC, Sealed Secrets, Kyverno guardrails
- [task2-cicd-supply-chain/](./task2-cicd-supply-chain) - Secure CI/CD pipeline (Gitleaks, Semgrep, Trivy, Cosign) + GitOps via ArgoCD
- [task3-zero-trust-mesh/](./task3-zero-trust-mesh) - Istio mTLS + zero-trust networking
- [task4-recon-pentest/](./task4-recon-pentest) - OSINT recon (Part A) + authorized penetration test (Part B)

All four tasks are complete. Each task folder contains its own README with implementation details, evidence, and documented trade-offs/limitations encountered along the way.

---

## Task 1 - Harden the Workload

ledger-api and a reporting neighbour service deployed with non-root, read-only-root-filesystem, all-capabilities-dropped containers, seccomp RuntimeDefault, resource limits, and health probes on /health. Runs under a dedicated, least-privilege ServiceAccount rather than default.

Secrets never touch git - Sealed Secrets encrypts STRIPE_API_KEY / DB_PASSWORD via kubeseal. Kyverno ClusterPolicies enforce non-root pods, reject :latest/untagged images, and verify image signatures (Enforce mode).

Bonus work completed: three RBAC personas (payments-developer, payments-operator, payments-admin) defined and applied as Roles with correctly scoped verb sets (see Known Gaps below for the one incomplete piece); Pod Security Standards (baseline) enforced at the namespace level - restricted was attempted but conflicts with the istio-init container's need for root/NET_ADMIN to configure sidecar iptables redirection, a known Istio limitation without istio-cni mode (see Known Gaps); a live admission-rejection demo where an insecure raw pod (nginx:latest, no securityContext) was blocked by Kyverno citing both policy violations.

Full details: [task1-harden-workload/README.md](./task1-harden-workload/README.md)

---

## Task 2 - Secure CI/CD Pipeline & Supply Chain + GitOps

Pipeline: [.github/workflows/secure-pipeline.yml](./.github/workflows/secure-pipeline.yml) - gates run before build, then the image is signed, attested, and auto-deployed via GitOps.

| Gate | Tool | Fail policy |
|---|---|---|
| Secrets scan | Gitleaks | Hard block on any detected secret |
| SAST | Semgrep (security-audit, OWASP Top 10) | Hard block on ERROR-severity findings |
| Dependency/image CVE scan | Trivy | Hard block on CRITICAL/HIGH with a known fix |
| Signing | Cosign (keyless, OIDC) | Image signed post-build |
| Provenance | Cosign attest | SLSA-style attestation attached |
| Deploy | update-manifest job + ArgoCD | Manifest auto-bumped, ArgoCD auto-syncs to cluster |

GitOps via ArgoCD: installed in-cluster, watching this repo's task1-harden-workload/deploy path with automated prune + selfHeal. Verified live: manually scaled a deployment out-of-band, watched ArgoCD detect drift and auto-revert within ~7 seconds. Also verified the full CI -> CD -> GitOps loop end-to-end: a pipeline run built/signed a new image, the update-manifest job committed the new tag back to main, ArgoCD picked it up and rolled the deployment with zero downtime.

Full details: [task2-cicd-supply-chain/README.md](./task2-cicd-supply-chain/README.md)

---

## Task 3 - Istio Zero-Trust Mesh

PeerAuthentication set to STRICT mTLS in the payments namespace, backed by a default-deny AuthorizationPolicy with explicit identity-based allows.

Proof it's enforced, not just applied:
- A plaintext pod (no sidecar) hitting ledger-api over HTTP is refused at the TLS layer - connection reset, no client cert presented.
- An in-mesh pod (reporting, sidecar injected) reaches the same endpoint successfully via a real mTLS handshake using istiod-issued workload certificates.
- Certificate issuance/rotation and NetworkPolicy-vs-Istio layering are both documented in detail with live log evidence (istio-agent CSR flow, observed root cert rotation, a real debugging example of an intra-namespace egress rule gap).

Full details: [task3-zero-trust-mesh/README.md](./task3-zero-trust-mesh/README.md)

---

## Task 4 - Recon & Penetration Test

Part A - OSINT recon ([full report](./task4-recon-pentest/part-a-osint/attack-surface-report.md)): passive-only enumeration of dodopayments.tech via subfinder/assetfinder, fingerprinted with httpx. 108 subdomains found, 56 live. Notable exposure: several internal engineering tools are directly internet-facing with no VPN/network boundary, including an identity-provider admin console (keycloak), a production analytics database (clickhouse-prod-v2), and a code-quality platform (sonarqube).

Known coverage gaps in Part A, documented in the report itself: the crt.sh certificate-transparency query returned zero results (rate-limited/transient failure) so subdomain discovery relied on subfinder + assetfinder only, not the full suggested toolset (amass was not run); TLS posture (testssl.sh) was reviewed for only 2 of the 56 live hosts due to time constraints.

Part B - Authorized pentest ([full report](./task4-recon-pentest/part-b-pentest/pentest-report.md)): black-box testing of ledger-api locally, no credentials. Two confirmed vulnerabilities:

| # | Finding | Severity | CVSS 3.1 |
|---|---|---|---|
| 1 | Unauthenticated exposure of full, unmasked cardholder PAN data via GET /transactions | High | 7.5 |
| 2 | SSRF via /fetch?url= | Medium | 6.5 |

The SSRF finding's real-world blast radius is substantially reduced once deployed into the Task 1-3 hardened environment, since NetworkPolicy egress restrictions and Istio identity-based AuthorizationPolicy limit what an SSRF can actually reach. That's the intended defense-in-depth story across all four tasks: the app-layer bug isn't fixed at the source, but the platform contains it.

---

## Known Gaps / With More Time

**RBAC personas (Task 1 bonus) - partial:**
Three Roles (payments-developer, payments-operator, payments-admin) are defined in task1-harden-workload/deploy/08-rbac-personas.yaml with correctly scoped verb sets and are applied to the cluster. RoleBindings to actual ServiceAccounts/Users were not completed due to time constraints. With more time: create a ServiceAccount per persona, bind each to its matching Role via RoleBinding, and verify enforcement with kubectl auth can-i --as=system:serviceaccount:payments:<persona-sa> <verb> <resource>.

**Kyverno require-image-signature exclusion (Task 1):**
This ClusterPolicy was originally cluster-wide and blocked ArgoCD's own dex-server pod (unsigned), since ArgoCD's control-plane images aren't part of the signed supply chain this assessment covers. Added an exclude block for the argocd and kube-system namespaces so the policy only enforces on application workloads. With more time: sign or vendor-verify ArgoCD's own images too, so the exclusion isn't needed.

**Pod Security Standards - restricted vs baseline (Task 1 bonus):**
restricted was attempted at the namespace level but the istio-init container (runAsNonRoot=false, runAsUser=0, requires NET_ADMIN/NET_RAW to configure iptables for sidecar traffic redirection) fails it - a known Istio limitation without istio-cni plugin mode installed. Verified ledger-api itself is fully restricted-compliant in isolation (non-root, all capabilities dropped). Settled on baseline as the accurate, currently-enforced level. With more time: install Istio in istio-cni mode, which moves the privileged iptables setup into a DaemonSet in kube-system (already excluded from PSS) instead of a per-pod init container in payments, allowing restricted to be re-applied cleanly.

**Task 4 recon coverage:**
Re-run the crt.sh query (likely rate-limited, not a real dead end) and add amass for broader subdomain coverage; extend testssl.sh review to all 56 live hosts, not just 2.

**Task 4 report depth:**
Add a chained-findings section (how the two confirmed vulnerabilities could combine in an attack path), a retest section, and a fuller mapping of findings back to how the Task 1-3 hardened platform would contain them.

**General:**
Capture actual screenshots/terminal recordings for each task's key moments (pipeline going green, Kyverno rejection, mTLS proof, ArgoCD self-heal) alongside the text-based evidence already committed.

## Environment

Runs fully local: kind (Kubernetes in Docker) on WSL2/Ubuntu - no cloud account required.

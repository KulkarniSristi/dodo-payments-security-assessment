# Task 2 — Secure CI/CD Pipeline & Supply Chain

## Pipeline: `.github/workflows/secure-pipeline.yml`

Three parallel gate jobs run first; `build` only proceeds if all three pass.

| Gate | Tool | Fail Policy |
|---|---|---|
| Secrets scan | Gitleaks | HARD BLOCK on any detected secret. Allowlist (`.gitleaks.toml`) covers two known non-issues: the intentional bonus-demo insecure manifest, and the Sealed Secret file (contains *encrypted* ciphertext, not real secrets). |
| SAST | Semgrep (p/python, security-audit, owasp-top-ten) | HARD BLOCK on ERROR-severity findings. |
| Dependency/CVE scan | Trivy (filesystem) | HARD BLOCK on CRITICAL/HIGH with a known fix. CVEs with no fix available are logged via SARIF but do not block. |
| Image scan | Trivy (built image) | Same policy, applied to the final built container. |
| Signing | Cosign (keyless) | Image signed via OIDC identity after build. |
| Provenance | Cosign attest | SLSA-style provenance attestation generated and attached. |

## Real findings — proof the gates work

Running this pipeline against `ledger-api` in its current state **correctly fails** at two gates:

**Semgrep** found 3 blocking findings in `app.py`: SSRF in `/fetch?url=` (2 rules) and Flask bound to `0.0.0.0`. These are annotated with `# nosemgrep` + comments explaining they are intentional vulnerabilities reserved as the Task 4 penetration-test target, not pipeline misconfigurations.

**Trivy** found 27 CVEs in `requirements.txt` (3 CRITICAL, 9 HIGH, 13 MEDIUM, 2 LOW) — Flask 0.12.2, PyYAML 5.1, Werkzeug 0.14.1, requests 2.19.1 are all years out of date. **This gate is intentionally left failing.** The outdated, vulnerable dependency set is required to support Task 4's pentest (e.g. PyYAML 5.1's unsafe `yaml.load()` is the intended RCE vector for `/import`). 

This is the correct, defensible behavior of a real dependency gate: **it prevents the current vulnerable build from being deployed.** In a real remediation cycle, this pipeline would stay red until dependencies are patched — which is exactly what should happen. We chose not to suppress or bypass this finding, since doing so would defeat the purpose of having the gate at all.

## What would happen with a patched app
If `requirements.txt` were updated to non-vulnerable versions (a trivial `pip install --upgrade` in a real fix), the pipeline would proceed to build, scan the built image, sign it with Cosign (keyless, OIDC-based), and generate an SLSA provenance attestation before pushing to GHCR.

## Design decisions
- Image tags use `git sha`, never `:latest` — enforced by our own Task 1 Kyverno `disallow-latest-tag` policy, so the pipeline had to comply with its own guardrails.
- `require-image-signature` Kyverno policy (Task 1) remains in **Audit** mode until an image is actually signed and pushed through this pipeline; it will be flipped to Enforce once that happens.

## GitOps — ArgoCD

`argocd/application.yaml` defines an ArgoCD `Application` pointing at this repo's `task1-harden-workload/deploy` path (branch: `main`) as the source of truth for the `payments` namespace, with `automated: {prune: true, selfHeal: true}`.

**Drift detection + self-heal — proven:**
1. Manually scaled `ledger-api` from 3 → 5 replicas via `kubectl scale`
2. ArgoCD detected the drift and terminated the extra pod within ~8 seconds, reverting to the git-declared replica count (3) automatically — no manual intervention
3. `kubectl get application ledger-api -n argocd` remained `Synced / Healthy` throughout, confirming ArgoCD treats git as the single source of truth and actively corrects manual out-of-band changes

## Known issue encountered & fixed
Our own Task 1 Kyverno `disallow-root-user` / `disallow-latest-tag` ClusterPolicies initially blocked ArgoCD's own control-plane deployments (`argocd-redis`, `argocd-notifications-controller`) from being created, since ArgoCD's upstream manifests don't set `runAsNonRoot`. Fixed by adding namespace `exclude` blocks to both policies for `argocd`, `kyverno`, `kube-system`, and `ingress-nginx` — cluster-wide security guardrails should exempt system/infra namespaces that we don't control the manifests for, while still enforcing strictly on application namespaces like `payments`.

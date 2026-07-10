# Task 1 — Harden the Workload

## What was done
- Deployed `ledger-api` + `reporting` neighbour service with Deployments, Services, ConfigMaps, Ingress
- **securityContext**: non-root (uid 10001), read-only root filesystem, all capabilities dropped, seccomp RuntimeDefault (pod + container level)
- **Resource limits/requests** and **liveness/readiness probes** on `/health`
- **Dedicated ServiceAccount + least-privilege RBAC** (default SA not used)
- **Secrets moved out of git**: Sealed Secrets controller installed; `STRIPE_API_KEY` / `DB_PASSWORD` encrypted via kubeseal, plaintext values never committed
- **Kyverno guardrails** (ClusterPolicies, Enforce mode):
  - `disallow-root-user` — rejects pods without explicit `runAsNonRoot: true`
  - `disallow-latest-tag` — rejects `:latest` or untagged images
  - `require-image-signature` — Enforce mode (verifies Cosign signatures; excludes argocd/kube-system namespaces since their control-plane images aren't part of this assessment's signed supply chain)
- **Ingress** via nginx ingress controller, verified working end-to-end
- **NetworkPolicy**: default-deny + explicit allow (ingress-nginx → ledger-api on 8080) + DNS egress allow. 
  ⚠️ **Known limitation**: kind's default CNI (kindnet) does not enforce NetworkPolicy — resources are applied correctly but not enforced at this layer. Real enforcement is demonstrated in Task 3 via Istio AuthorizationPolicy + PeerAuthentication.

## Bonus items completed
- **RBAC personas**: `payments-developer` (read-only), `payments-operator` (read/update/delete), `payments-admin` (full) — least-privilege Roles scoped to the `payments` namespace
- **Pod Security Standards (baseline)** enforced at namespace level. `restricted` was attempted but the istio-init container (requires root + NET_ADMIN/NET_RAW for iptables sidecar redirection) is incompatible with it — a known Istio limitation without istio-cni plugin mode. ledger-api itself is fully restricted-compliant in isolation (non-root, all capabilities dropped); baseline is the honest, currently-enforced namespace level. See task1-harden-workload/evidence/08-pod-security-standard.txt
- **Admission rejection demo**: applied a raw insecure Pod (`nginx:latest`, no securityContext) — Kyverno blocked it citing both `disallow-latest-tag` and `disallow-root-user` violations (see screenshot below)

## Evidence
- `kubectl exec ... id` → `uid=10001 gid=10001` (non-root confirmed)
- `kubectl exec ... touch /test.txt` → `Read-only file system` (confirmed)
- SealedSecret decrypts correctly into real Secret, consumed via env vars
- Ingress curl test: `{"status": "ok"}`
- Kyverno rejection error (see `/screenshots` — TODO add)

## Design decisions / trade-offs
- `require-image-signature` policy set to **Audit**, not Enforce, since images aren't signed yet at this stage (Task 2 implements Cosign signing). Will tighten to Enforce after Task 2.
- NetworkPolicy enforcement gap on kind is a platform limitation, not a design flaw — documented rather than masked. Calico could be installed for full enforcement but was deprioritized given time constraints and that Task 3 (Istio) provides real enforcement proof.

### RBAC Scoping Note
`ledger-api` is granted a dedicated ServiceAccount (`ledger-api`) bound to a
Role (`ledger-api-role`) with an intentionally empty `rules: []`. The
application does not call the Kubernetes API at runtime (verified: no
client-go/kubectl/K8s SDK usage in app.py), so the least-privilege outcome is
zero API permissions rather than narrowly-scoped ones. If the pod is
compromised, the ServiceAccount token grants no access to any cluster
resource. This is distinct from using the `default` ServiceAccount, which
Kubernetes auto-mounts with implicit cluster context even when unused.

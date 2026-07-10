# PCI DSS Cardholder Data Environment (CDE) Scope Mapping

Date: 2026-07-10
Scope basis: live cluster inspection (`kubectl get pods/svc/namespaces`) + deployed NetworkPolicy, PeerAuthentication, and AuthorizationPolicy manifests (Tasks 1 & 3).

## In-Scope: The `payments` Namespace

The `payments` namespace is treated as the Cardholder Data Environment (CDE) boundary. It contains:

| Workload | Role | PCI Relevance |
|---|---|---|
| `ledger-api` (3 replicas) | Stores/returns transaction records including PANs (per Finding 1, Part B pentest) | **In-scope, system component storing/processing cardholder data** — highest-sensitivity component in the environment |
| `reporting` (1 replica) | Consumes `ledger-api` via Istio-authorized calls to `/health`, `/fetch` only | **In-scope, connected system** — has network + mesh-level access to the CDE component, though currently restricted from `/transactions` |
| `plaintext-test` | Deliberate non-meshed test pod (`sidecar.istio.io/inject: false`) used to validate mTLS enforcement | **In-scope by namespace location, but functionally isolated** — see mTLS Enforcement Verification below; not part of the application data path |

## Boundary Controls (why `payments` is treated as an isolated CDE segment)

### 1. Network Layer (Task 1 — Kubernetes NetworkPolicy)
- `default-deny-all`: all ingress/egress denied by default for every pod in `payments`.
- Explicit allows only for: ingress-nginx → `ledger-api:8080`, DNS (53/UDP+TCP), Istio control-plane ports (15012/15010/15014) to `istio-system`, and intra-namespace traffic on port 8080.
- **Effect:** no pod in `payments` can reach the open internet or arbitrary external hosts — confirmed as the compensating control for the SSRF finding (Part B, Finding 2).

### 2. Identity/Transport Layer (Task 3 — Istio mTLS)
- `PeerAuthentication` (`default`, namespace `payments`): `mtls.mode: STRICT`.
- **Live-verified** (see `evidence/mtls-enforcement-proof.md`): a non-meshed pod (`plaintext-test`) attempting a plaintext connection to `ledger-api` is rejected with connection reset; a meshed pod (`reporting`) with valid mTLS identity succeeds.
- This means even a workload that somehow bypasses NetworkPolicy (e.g., via a compromised node) still cannot establish a connection to `ledger-api` without a valid, cluster-issued mTLS certificate.

### 3. Authorization Layer (Task 3 — Istio AuthorizationPolicy)
- `default-deny-all` (AuthorizationPolicy): denies all requests by default.
- `allow-reporting-to-ledger-api` (confirmed live via `kubectl get authorizationpolicy -o yaml`): only the `reporting` ServiceAccount (`cluster.local/ns/payments/sa/reporting`) is permitted, and only for `GET /health` and `GET /fetch` — **not** `/transactions`.
- **Effect:** even a workload with valid network access and valid mTLS identity cannot call `/transactions` unless it specifically holds the `reporting` ServiceAccount identity, and even then, only `/health` and `/fetch` are permitted — `/transactions` is not reachable by any workload identity today. (Ledger-api itself was not granted an explicit self-allow rule; internal requests would need separate verification, noted as follow-up.)

## Out-of-Scope / Connected Systems

| Namespace | Role | PCI Relevance |
|---|---|---|
| `ingress-nginx` | External ingress entrypoint | **Connected system, not CDE** — has explicit, narrow NetworkPolicy-granted access to `ledger-api:8080` only. Should itself be hardened/scoped in a production deployment, but is outside this assessment's boundary. |
| `istio-system` | Mesh control plane (istiod) | **Connected system, not CDE** — required for mTLS cert issuance/rotation; payments pods have narrow egress access to specific control-plane ports only. |
| `kube-system`, `kube-public`, `kube-node-lease`, `local-path-storage`, `default` | Cluster infrastructure | **Out of scope** — no direct path to cardholder data; default-deny NetworkPolicy in `payments` prevents any inbound reach from these namespaces except via the explicit ingress-nginx allow. |

## Known Gaps / Follow-Up Items (documented per "prioritize quality, document what you'd do with more time")

1. **`ledger-api`'s own outbound calls are not independently verified against AuthorizationPolicy.** If `/fetch`'s SSRF (Finding 2) were used to make `ledger-api` call its own `/transactions` endpoint internally, that request's effective source identity and whether it passes or fails the AuthorizationPolicy has not been live-tested — flagged in both the pentest report's chained-finding section and here. Recommended as a priority follow-up test.
2. **No Service object exists for `reporting`** (only `ledger-api` has a ClusterIP Service) — pod-to-pod communication appears to rely on direct pod IPs or DNS lookups outside a stable Service abstraction. Not a security gap per se, but worth normalizing for production readiness.
3. **PCI DSS network segmentation testing** (formal, e.g., annual segmentation penetration test per PCI DSS Requirement 11.4.5) is out of scope for this assessment; the mTLS + NetworkPolicy + AuthorizationPolicy layering here demonstrates the *technical controls* a segmentation test would validate, but does not constitute one.

## Summary

The CDE boundary (`payments` namespace) is enforced by three independent, layered controls — network (NetworkPolicy), transport identity (mTLS STRICT), and application authorization (AuthorizationPolicy) — each independently verified against the live cluster rather than assumed from manifest files alone. This layered approach means a failure in any single control (e.g., the stale/incorrect AuthorizationPolicy file discovered and corrected during this assessment) does not fully collapse the boundary, though full defense-in-depth requires all layers to be correct and current.

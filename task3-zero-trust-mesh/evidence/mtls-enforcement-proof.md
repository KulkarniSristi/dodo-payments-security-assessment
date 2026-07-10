# Istio STRICT mTLS Enforcement — Live Proof

Date: 2026-07-10
Cluster: `ledger-cluster` (kind, local)

## Setup
- `plaintext-test` pod deployed in `payments` namespace with `sidecar.istio.io/inject: "false"` — deliberately excluded from the Istio mesh (no sidecar, no mTLS identity).
- `reporting` pod is a normal meshed workload (Istio sidecar injected, participates in mTLS).
- `PeerAuthentication` (`default`, namespace `payments`) enforces `mtls.mode: STRICT`.

## Test 1: Non-meshed pod → ledger-api (expected: blocked)**Result: Connection reset.** The non-meshed pod cannot establish a plaintext connection to `ledger-api`, because STRICT mTLS requires a valid mesh identity/certificate that `plaintext-test` does not have.

## Test 2: Meshed pod (reporting) → ledger-api (expected: succeeds)**Result: 200 OK**, served via Envoy (sidecar proxy), confirming the meshed `reporting` pod successfully completes mTLS and reaches `ledger-api`.

## Conclusion
This is direct, live evidence that `PeerAuthentication` STRICT mode is actively enforced in the `payments` namespace — not just deployed as a policy object with no functional effect. A workload without a valid mesh identity is rejected at the connection level; a workload with one is transparently authenticated and served.

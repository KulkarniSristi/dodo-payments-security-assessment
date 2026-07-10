
## Certificate Issuance & Rotation

**CA setup:** This deployment uses Istio's default built-in CA (self-signed root,
`O=cluster.local`), managed by `istiod`. No external CA or cert-manager integration
was configured — istiod acts as both the root and intermediate CA for the mesh.

**Issuance flow:**
1. Each sidecar (Envoy proxy) requests a certificate from istiod via the Istio
   Secret Discovery Service (SDS) on pod startup.
2. istiod verifies the requesting workload's identity using its Kubernetes
   service account token (via the SPIFFE identity model:
   spiffe://cluster.local/ns/<namespace>/sa/<service-account>).
3. istiod signs a short-lived X.509 certificate and pushes it to the sidecar
   over the SDS gRPC stream — the private key never leaves the pod.

**Rotation:** Verified live on ledger-api-698dd89746-58dh8 — issued cert has a
~24-hour validity window (notBefore=Jul 10 17:50:33 -> notAfter=Jul 11 17:52:33,
Istio's default SDS cert TTL). istiod automatically re-issues and pushes a new
cert to each sidecar before expiry, with no pod restart or manual step required.
This limits the blast radius of a compromised cert to a maximum ~24-hour window.

**Evidence:** task3-service-mesh-security/evidence/05-cert-rotation.txt

## NetworkPolicy Layering

Network security in the payments namespace is enforced at two independent layers,
so a bypass at one layer is still caught by the other.

**Layer 1 - Kubernetes NetworkPolicy (L3/L4, CNI-enforced):**
- default-deny-all: baseline deny for all ingress/egress in the namespace.
- allow-ingress-to-ledger-api: permits only explicitly allowed ingress to ledger-api pods.
- allow-intra-namespace-to-ledger-api / allow-intra-namespace-egress: permits
  pod-to-pod traffic within the payments namespace only.
- allow-dns-egress: permits DNS resolution (UDP/TCP 53) - required or all
  service discovery breaks under default-deny.
- allow-istio-control-plane-egress: permits sidecars to reach istiod for
  config/cert delivery (xDS/SDS).

  These operate below the mesh, at the IP/port level, and are enforced by the
  cluster's CNI regardless of whether Istio is present.

**Layer 2 - Istio AuthorizationPolicy + PeerAuthentication (L7, identity-based):**
- PeerAuthentication mode STRICT (mesh-wide default): rejects any plaintext
  (non-mTLS) connection outright, before any authorization check even runs.
- AuthorizationPolicy default-deny-all: baseline deny for all requests in the
  namespace at the mesh layer.
- AuthorizationPolicy allow-reporting-to-ledger-api: explicit ALLOW rule
  scoped to a specific caller identity (SPIFFE ID / service account) rather
  than just an IP or label, so identity spoofing via IP reuse is not possible.

**Why both layers:** NetworkPolicy alone only sees IPs and ports - it can't
distinguish a legitimate pod from an attacker who has compromised a pod IP or
label. Istio's AuthorizationPolicy operates on cryptographically verified
workload identity (via the mTLS cert issued by istiod, see Certificate
Issuance & Rotation above), so it holds even if the L3/L4 layer is somehow
bypassed. Together this gives defense-in-depth: an attacker would need to
defeat both the CNI-enforced network boundary and the mesh's mTLS identity
verification to reach ledger-api.

**Evidence:** task3-service-mesh-security/evidence/06-networkpolicy-layering.txt

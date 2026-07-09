## mTLS STRICT enforcement — proof

PeerAuthentication applied in payments namespace with mtls.mode: STRICT.

Test 1 — plaintext pod (no Istio sidecar, sidecar.istio.io/inject: "false") to ledger-api:

kubectl exec -n payments plaintext-test -- curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://ledger-api.payments.svc.cluster.local:8080/health
Result: 000 (exit code 56 - connection reset by peer)
Refused - no client certificate presented, Envoy on ledger-api rejects at the TLS layer.

Test 2 — in-mesh pod (reporting, with sidecar) to ledger-api:

kubectl exec -n payments deploy/reporting -c client -- curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://ledger-api.payments.svc.cluster.local:8080/health
Result: 200
Allowed - valid mTLS handshake between sidecars using workload certificates issued by istiod.

Note on debugging journey: mid-testing, PeerAuthentication and the entire Istio control plane were found missing, a side effect of an earlier istioctl uninstall --purge during CNI troubleshooting that was never followed through with a reinstall. Reinstalling istiod (profile=minimal, no CNI) and reapplying PeerAuthentication resolved it.

## Default-deny AuthorizationPolicy + identity-based allow — proof

Two AuthorizationPolicy resources applied in the payments namespace:
1. default-deny-all (authz-default-deny.yaml) - empty spec, denies everything for every workload in the namespace.
2. allow-reporting-to-ledger-api (authz-allow-reporting.yaml) - explicit ALLOW, scoped by selector app=ledger-api, keyed on workload identity via SPIFFE principal spiffe://cluster.local/ns/payments/sa/reporting (not IP), restricted to GET on /health and /fetch.

Test 1 - unauthorized (no mesh identity at all):
kubectl exec -n payments plaintext-test -- curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://ledger-api.payments.svc.cluster.local:8080/health
Result: 000 (connection refused - blocked at the mTLS layer before RBAC is even evaluated, since plaintext-test has no sidecar/certificate)

Test 2 - authorized (reporting ServiceAccount, in-mesh):
kubectl exec -n payments deploy/reporting -c client -- curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://ledger-api.payments.svc.cluster.local:8080/health
Result: 200 OK

Confirmed via Envoy stats on ledger-api's sidecar:
http.inbound_0.0.0.0_8080;.rbac.allowed: 1
http.inbound_0.0.0.0_8080;.rbac.denied: 0

This shows the request was evaluated by the RBAC filter and explicitly allowed by the reporting SA's SPIFFE identity, not merely passed through.

Note: immediately after applying the AllowPolicy, a request briefly returned 403 - this was xDS config propagation delay (a few seconds for Envoy to receive and load the updated RBAC filter config from istiod), not a policy misconfiguration. Confirmed by re-testing after propagation and checking Envoy's live config_dump, which showed the principal correctly loaded.


## Workload certificate issuance and rotation

Istio's control plane (istiod) acts as the Certificate Authority for the mesh, using the
built-in Citadel provider (visible in our istio-proxy logs: "CA Endpoint istiod.istio-system.svc:15012, provider Citadel").

How it works in this cluster:
1. Each pod's istio-agent (running inside the istio-proxy sidecar) generates a private key
   locally and never sends it anywhere.
2. The agent creates a CSR (Certificate Signing Request) containing the workload's identity,
   expressed as a SPIFFE URI: spiffe://cluster.local/ns/<namespace>/sa/<serviceaccount>
   (e.g. spiffe://cluster.local/ns/payments/sa/reporting). This identity comes from the pod's
   Kubernetes ServiceAccount token, not from IP or hostname.
3. The CSR is sent to istiod over the SDS (Secret Discovery Service) protocol.
4. istiod validates the requesting pod's ServiceAccount token against the Kubernetes API,
   then signs the certificate using its own intermediate CA key.
5. The signed certificate (plus the root CA cert) is pushed back to the sidecar over the
   same SDS channel and held only in memory - never written to disk, never stored as a
   Kubernetes Secret.

Rotation:
- Our istio-proxy logs show workload certs issued with a ttl of ~24h
  (ttl=23h59m59.xxx), which is Istio's default workload cert lifetime.
- Before expiry, the istio-agent automatically requests a new certificate the same way,
  with no pod restart and no downtime.
- We also observed "Root cert has changed, start rotating root cert" in the logs -
  istiod periodically rotates its own signing root as well, and distributes the new
  root to all sidecars transparently.

Trust root:
- The trust root in this cluster is istiod's self-signed root CA (Citadel's default,
  since we did not supply an external CA). All workload certs chain up to this single root,
  which is what allows any two sidecars in the mesh to verify each other's identity during
  the mTLS handshake, regardless of which node or namespace they're in.
- In a production deployment this root would typically be replaced with an intermediate
  CA issued by an external root (e.g. a corporate PKI or a tool like cert-manager +
  Vault), so that istiod's own root is not the ultimate trust anchor across the org.

## NetworkPolicy vs Istio: what each layer catches

During this task we hit real conflicts between our Task 1 NetworkPolicy (L3/L4, IP+port based)
and Istio's mesh (L7, identity based) - which turned out to be a good practical illustration of
defense-in-depth, not just a theoretical point:

| Layer | Enforces | What it catches | What it misses |
|---|---|---|---|
| Kubernetes NetworkPolicy | L3/L4 (IP + port) | Which pods/namespaces can open a connection at all. Coarse network segmentation - e.g. we had to explicitly allow payments -> istio-system on ports 15012/15010/15014 for sidecars to even reach istiod for cert issuance. | Cannot see HTTP paths, methods, or verify who the caller actually is - a compromised pod inside an allowed namespace/IP range is trusted by default. |
| Istio PeerAuthentication (mTLS STRICT) | Transport encryption + peer identity | Whether the connection is authenticated and encrypted at all. A pod with no sidecar (like our plaintext-test) is refused outright - proven by the 000/connection-reset result. | Doesn't restrict what an authenticated identity is allowed to do once connected. |
| Istio AuthorizationPolicy | L7, identity + method + path | Fine-grained "who can call what" - e.g. only spiffe://cluster.local/ns/payments/sa/reporting may GET /health or /fetch on ledger-api. Survives IP changes, pod restarts, and node moves, since identity is cryptographic, not network-based. | Doesn't replace network segmentation - a workload could still open raw TCP connections to ports/services an AuthorizationPolicy doesn't cover unless NetworkPolicy also restricts it. |

Real example from this assignment: when we applied 06-networkpolicy.yaml with only a
default-deny-all and narrow allows, reporting could not reach ledger-api on 8080 at all
because we'd forgotten an explicit intra-namespace egress rule for port 8080 - independent of
whatever Istio was doing. NetworkPolicy failures happen "before" Istio ever sees the packet,
which is why both layers need to be tested separately: NetworkPolicy determines if the packet
gets through the network stack, Istio then determines if the identity behind that packet is
allowed to make the specific call.

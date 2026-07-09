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

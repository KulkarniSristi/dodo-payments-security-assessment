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

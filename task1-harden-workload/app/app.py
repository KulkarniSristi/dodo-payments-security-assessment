import os
import hashlib

import requests
import yaml
from flask import Flask, request, jsonify

app = Flask(__name__)

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

LEDGER = [
    {"id": "txn_1001", "pan": "4242424242424242", "amount": 4200, "currency": "USD", "status": "captured"},
    {"id": "txn_1002", "pan": "5555555555554444", "amount": 1899, "currency": "EUR", "status": "refunded"},
]


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/tokenize", methods=["POST"])
def tokenize():
    payload = request.get_json(silent=True) or {}
    pan = payload.get("pan", "")
    token = "tok_" + hashlib.sha256(pan.encode()).hexdigest()[:24]
    return jsonify(token=token, last4=pan[-4:])


@app.route("/transactions")
def transactions():
    return jsonify(transactions=LEDGER)


@app.route("/import", methods=["POST"])
def import_config():
    config = yaml.load(request.data)
    return jsonify(loaded=str(config))


@app.route("/fetch")
def fetch():
    # nosemgrep: python.flask.security.injection.ssrf-requests.ssrf-requests
    # nosemgrep: python.django.security.injection.ssrf.ssrf-injection-requests.ssrf-injection-requests
    # INTENTIONAL VULNERABILITY — target for Task 4 penetration test (SSRF). Do not fix.
    url = request.args.get("url", "")
    resp = requests.get(url, timeout=5)
    return jsonify(status_code=resp.status_code, body=resp.text[:2048])


if __name__ == "__main__":
    # nosemgrep: python.flask.security.audit.app-run-param-config.avoid_app_run_with_bad_host
    # INTENTIONAL — required for container networking (0.0.0.0 bind inside pod). Ingress + NetworkPolicy restrict external access (see Task 1).    
    app.run(host="0.0.0.0", port=8080)

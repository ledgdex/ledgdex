#!/bin/sh
# expect: dispute signed and kept as "sent"
# expect: "status": "refunded"
# expect: not_arbiter
set -eu

# The judge (the arbiter) is the exchange, with its own ledgdex. The seller names the key of the exchange in its offer.
ledgdex init exchange --name "ONITO medmodel exchange" --key exchange
ARBITER=$(ledgdex state exchange | python3 -c 'import json,sys; print(json.load(sys.stdin)["owner"])')
ledgdex init biobot --name "biobot" --key biobot
cat > offer.json <<JSON
{"item": {"title": "Penjointu v1 weights"}, "quantity": 5, "unit": "license", "currency": "USD", "price": 250000,
 "arbiter": {"key": "$ARBITER", "url": "exchange"}}
JSON
OFFER=$(ledgdex offer biobot offer.json | awk '{print $NF}')

# The buyer claims a license and pays.
ledgdex init orthonalyzebot --name "orthonalyzebot" --key orthonalyzebot
ledgdex claim orthonalyzebot biobot "$OFFER" --output claim.json
CLAIM=$(ledgdex record biobot --from orthonalyzebot | awk '/claim recorded/ {print $3}')
ledgdex pay orthonalyzebot biobot "$CLAIM" --method card --ref PAY-0555 --output paid.json
ledgdex record biobot --from orthonalyzebot

# The weights do not arrive. The buyer opens a dispute, with the payment reference as evidence.
ledgdex dispute orthonalyzebot "$CLAIM" --seller biobot --text "Paid on the 1st. No weights came." --evidence PAY-0555 --output dispute.json
DISPUTE=$(ledgdex record biobot --from orthonalyzebot | awk '/dispute recorded/ {print $3}')

# The seller tries to rule on its own case. The ledger records the ruling, but the ruling does not count (`not_arbiter`).
ledgdex ruling biobot biobot "$DISPUTE" --outcome release --text "We sent the weights." --output self-ruling.json
ledgdex record biobot --from biobot || true

# The exchange rules: refund. The seller records the ruling, and the claim shows as refunded.
ledgdex ruling exchange biobot "$DISPUTE" --outcome refund --text "No proof of delivery: refund in full." --output ruling.json
ledgdex record biobot --from exchange
ledgdex state biobot | python3 -c '
import json, sys
st = json.load(sys.stdin)
print(json.dumps({"status": [c["status"] for c in st["claims"].values()][0],
                  "ignored": [i["reason"] for i in st["ignored"]]}))'

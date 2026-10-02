#!/bin/sh
# expect: dispute signed and kept as "sent"
# expect: "status": "refunded"
# expect: not_arbiter
set -eu

# The judge (arbiter) is a traders' association with its own ledgdex. The shop names the association's key in its offer.
ledgdex init assoc --name "Fruit Traders Association" --key assoc
ARBITER=$(ledgdex state assoc | python3 -c 'import json,sys; print(json.load(sys.stdin)["owner"])')
ledgdex init shop --name "Mango Farm" --key farm
cat > offer.json <<JSON
{"item": {"title": "Alphonso mangoes"}, "quantity": 5, "unit": "dozen", "currency": "INR", "price": 120000,
 "arbiter": {"key": "$ARBITER", "url": "assoc"}}
JSON
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')

# The buyer orders and pays.
ledgdex init me --name "Asha" --key asha
ledgdex claim me shop "$OFFER" --output claim.json
CLAIM=$(ledgdex record shop --from me | awk '/claim recorded/ {print $3}')
ledgdex pay me shop "$CLAIM" --method upi --ref UTR555 --output paid.json
ledgdex record shop --from me

# Nothing arrives. The buyer opens a dispute, with the payment reference as evidence.
ledgdex dispute me "$CLAIM" --seller shop --text "Paid on the 1st, nothing delivered." --evidence UTR555 --output dispute.json
DISPUTE=$(ledgdex record shop --from me | awk '/dispute recorded/ {print $3}')

# The shop tries to decide its own case. The decision is recorded, but it does not count (`not_arbiter`).
ledgdex ruling shop shop "$DISPUTE" --outcome release --text "I say it was delivered." --output self-ruling.json
ledgdex record shop --from shop || true

# The association decides: refund. The shop records the decision, and the order shows as refunded.
ledgdex ruling assoc shop "$DISPUTE" --outcome refund --text "No proof of delivery: refund in full." --output ruling.json
ledgdex record shop --from assoc
ledgdex state shop | python3 -c '
import json, sys
st = json.load(sys.stdin)
print(json.dumps({"status": [c["status"] for c in st["claims"].values()][0],
                  "ignored": [i["reason"] for i in st["ignored"]]}))'

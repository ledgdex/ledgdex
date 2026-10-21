#!/bin/sh
# expect: receipt kept for your claim
# expect: "status": "closed"
# expect: whole:
set -eu

# The seller biobot makes its ledgdex: a website (dex) with a signed record book (ledger) in it. Ledgdex keeps your keys in `~/.ledgdex`.
ledgdex init biobot --name "biobot" --about "Maker of Penjointu, a neural network for knee bone density" --key biobot

# Biobot offers 10 licenses for the Penjointu weights. Prices are in the smallest unit of the currency: 250000 cents is USD 2,500.00. The last command prints the id of the new offer. `$OFFER` keeps it.
cat > offer.json <<'JSON'
{"item": {"title": "Penjointu v1 weights", "text": "One license for each clinic."},
 "quantity": 10, "unit": "license", "currency": "USD", "price": 250000,
 "pay": [{"method": "card", "to": "https://pay.example/biobot"}]}
JSON
OFFER=$(ledgdex offer biobot offer.json | awk '{print $NF}')
echo "offer: $OFFER"

# The buyer orthonalyzebot makes a ledgdex too, and claims 2 licenses. The buyer keeps a signed copy of the claim in `claim.json`.
ledgdex init orthonalyzebot --name "orthonalyzebot" --key orthonalyzebot
ledgdex claim orthonalyzebot biobot "$OFFER" --quantity 2 --output claim.json

# Biobot collects the claim from the dex of the buyer and accepts it. Here the dex is a folder. Online, it is a website. Then the buyer keeps the signed record of the seller as a receipt. The seller cannot take back a receipt.
CLAIM=$(ledgdex record biobot --from orthonalyzebot | awk '/claim recorded/ {print $3}')
ledgdex receipt orthonalyzebot biobot

# The buyer pays. The seller records the money and the delivery. The buyer tells the seller that the weights arrived. Each side signs its own step.
ledgdex pay orthonalyzebot biobot "$CLAIM" --method card --ref PAY-0001 --output paid.json
ledgdex record biobot --from orthonalyzebot
ledgdex received biobot "$CLAIM" 500000
ledgdex delivered biobot "$CLAIM" --note "weights sent by a private link"
ledgdex confirm orthonalyzebot biobot "$CLAIM" --output confirmed.json
ledgdex record biobot --from orthonalyzebot

# Anyone can now verify the ledger of biobot and see the claim. The claim is closed.
ledgdex verify biobot
ledgdex state biobot | python3 -m json.tool | grep '"status"'

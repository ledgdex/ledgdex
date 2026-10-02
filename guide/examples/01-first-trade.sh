#!/bin/sh
# expect: receipt kept for your claim
# expect: "status": "closed"
# expect: whole:
set -eu

# The shop makes its ledgdex: a website (dex) with a signed record book (ledger) in it. Your keys are kept in `~/.ledgdex`.
ledgdex init shop --name "Mango Farm" --about "Alphonso mangoes from Ratnagiri" --key farm

# The shop offers 10 dozen mangoes. Prices are in the smallest unit of the currency: 120000 paise is INR 1,200.00. The last command prints the new offer's id, which is kept in `$OFFER`.
cat > offer.json <<'JSON'
{"item": {"title": "Alphonso mangoes", "text": "One dozen, ripe."},
 "quantity": 10, "unit": "dozen", "currency": "INR", "price": 120000,
 "pay": [{"method": "upi", "to": "farm@bank"}]}
JSON
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
echo "offer: $OFFER"

# The buyer makes a ledgdex too and orders (claims) 2 dozen. A signed copy of the order stays with the buyer in `claim.json`.
ledgdex init me --name "Asha" --key asha
ledgdex claim me shop "$OFFER" --quantity 2 --output claim.json

# The shop picks up the order from the buyer's dex (a folder here, a website online) and accepts it. Then the buyer keeps the shop's signed record of the order: a receipt the shop can never take back.
CLAIM=$(ledgdex record shop --from me | awk '/claim recorded/ {print $3}')
ledgdex receipt me shop

# The buyer pays, the shop records the money and the delivery, and the buyer confirms it arrived. Each side signs its own step.
ledgdex pay me shop "$CLAIM" --method upi --ref UTR123 --output paid.json
ledgdex record shop --from me
ledgdex received shop "$CLAIM" 240000
ledgdex delivered shop "$CLAIM" --note "by courier"
ledgdex confirm me shop "$CLAIM" --output confirmed.json
ledgdex record shop --from me

# Anyone can now verify the shop's ledger and see the order: it is closed.
ledgdex verify shop
ledgdex state shop | python3 -m json.tool | grep '"status"'

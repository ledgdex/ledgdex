#!/bin/sh
# A whole trade between two ledgdexes on one machine: a seller (shop) and a buyer (me).
# Run it in an empty folder. Keys go to ~/.ledgdex (or $LEDGDEX_HOME).
# expect: receipt kept for your claim
# expect: "status": "closed"
# expect: whole:
set -eu

# 1. The seller makes a ledgdex: a dex (website) with a signed ledger in it.
ledgdex init shop --name "Mango Farm" --about "Alphonso mangoes from Ratnagiri" --key farm

# 2. The seller offers something. Prices are integers in the smallest unit: 120000 is INR 1,200.00.
cat > offer.json <<'JSON'
{"item": {"title": "Alphonso mangoes", "text": "One dozen, ripe."},
 "quantity": 10, "unit": "dozen", "currency": "INR", "price": 120000,
 "pay": [{"method": "upi", "to": "farm@bank"}]}
JSON
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
echo "offer: $OFFER"

# 3. The buyer makes a ledgdex too, and claims 2 dozen. The claim is kept in the buyer's ledger as "sent".
ledgdex init me --name "Asha" --key asha
ledgdex claim me shop "$OFFER" --quantity 2 --output claim.json

# 4. The seller records the claim, collected from the buyer's dex (a folder here; a web address online).
CLAIM=$(ledgdex record shop --from me | awk '/claim recorded/ {print $3}')

# 5. The buyer keeps the seller's record of the claim: the receipt (the third entry of triple entry).
ledgdex receipt me shop

# 6. Payment, delivery and confirmation, each signed by the side that did it.
ledgdex pay me shop "$CLAIM" --method upi --ref UTR123 --output paid.json
ledgdex record shop --from me
ledgdex received shop "$CLAIM" 240000
ledgdex delivered shop "$CLAIM" --note "by courier"
ledgdex confirm me shop "$CLAIM" --output confirmed.json
ledgdex record shop --from me

# 7. Anyone can verify the seller's ledger and read its state. The claim is closed.
ledgdex verify shop
ledgdex state shop | python3 -m json.tool | grep '"status"'

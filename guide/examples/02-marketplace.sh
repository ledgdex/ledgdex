#!/bin/sh
# A marketplace: one operator ledger is both the root (who is admitted) and the index (which shops are listed).
# Two shops sell to admitted buyers only; a buyer finds offers through the index and buys the cheapest.
# expect: Kesar mangoes INR 90000 per dozen
# expect: (accepted)
# expect: (rejected, not_allowed)
set -eu

# 1. The operator's ledgdex. Its owner key admits members and is the default arbiter of every shop's offers.
ledgdex init market --name "Ratnagiri Market" --about "Fruit sellers of Ratnagiri" --key market

# 2. Two shops, both trading under the market as their root (pinned by its ledger id).
ledgdex init farm --name "Mango Farm" --key farm --root market
ledgdex init orchard --name "Hill Orchard" --key orchard --root market

# 3. Members. The market admits the shops' keys and a buyer's; each shop admits the buyer too.
#    (A key is given as a public key, ed25519:..., or by its name in ~/.ledgdex on this machine.)
ASHA=$(ledgdex keygen asha)
ledgdex admit market farm --name "Mango Farm"
ledgdex admit market orchard --name "Hill Orchard"
ledgdex admit market "$ASHA" --name "Asha"
ledgdex admit farm "$ASHA" --name "Asha"
ledgdex admit orchard "$ASHA" --name "Asha"

# 4. The market lists both shops: it is now an index anyone can read.
ledgdex list market farm --note "mangoes"
ledgdex list market orchard --note "mangoes, cheaper"

# 5. The shops offer to admitted keys only. The arbiter defaults to the market's owner.
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 20, "unit": "dozen", "currency": "INR", "price": 120000, "allow": "admitted"}' > farm-offer.json
printf '%s' '{"item": {"title": "Kesar mangoes"}, "quantity": 20, "unit": "dozen", "currency": "INR", "price": 90000, "allow": "admitted"}' > orchard-offer.json
ledgdex offer farm farm-offer.json
ledgdex offer orchard orchard-offer.json

# 6. The buyer reads the index: every listed ledger, and what each sells.
ledgdex init me --name "Asha" --key asha --root market
ledgdex discover market --offers --json > found.json
python3 -c '
import json
for l in json.load(open("found.json")):
    for o in l["offers"]:
        print(l["note"], "|", o["title"], o["currency"], o["price"], "per", o["unit"], "|", o["remaining"], "left")' 

# 7. The buyer picks the cheapest open offer and claims it; that shop records the claim.
set -- $(python3 -c '
import json
found = json.load(open("found.json"))
best = min(((o["price"], l["url"], o["id"]) for l in found for o in l["offers"]), key=lambda x: x[0])
print(best[1], best[2])')
ledgdex claim me "$1" "$2" --output claim.json
ledgdex record "$1" --from me

# 8. Someone the market never admitted is turned away by the same rule.
ledgdex init stranger --name "Stranger" --key stranger
ledgdex claim stranger "$1" "$2" --output stranger-claim.json
ledgdex record "$1" --from stranger

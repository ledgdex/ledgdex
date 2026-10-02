#!/bin/sh
# expect: Kesar mangoes INR 90000 per dozen
# expect: (accepted)
# expect: (rejected, not_allowed)
set -eu

# The organiser makes the market's ledgdex. Its ledger is both the member list (the root) and the list of shops (the index). Two shops join, naming the market they trade in.
ledgdex init market --name "Ratnagiri Market" --about "Fruit sellers of Ratnagiri" --key market
ledgdex init farm --name "Mango Farm" --key farm --root market
ledgdex init orchard --name "Hill Orchard" --key orchard --root market

# The organiser lets in both shops and one buyer, and each shop lets the buyer in too. Keys are named here as they are on this computer; normally you would paste the key text (`ed25519:...`).
ASHA=$(ledgdex keygen asha)
ledgdex admit market farm --name "Mango Farm"
ledgdex admit market orchard --name "Hill Orchard"
ledgdex admit market "$ASHA" --name "Asha"
ledgdex admit farm "$ASHA" --name "Asha"
ledgdex admit orchard "$ASHA" --name "Asha"

# The organiser lists both shops, so buyers can find them.
ledgdex list market farm --note "mangoes"
ledgdex list market orchard --note "mangoes, cheaper"

# Both shops offer mangoes at different prices. `"allow": "admitted"` means only members may buy.
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 20, "unit": "dozen", "currency": "INR", "price": 120000, "allow": "admitted"}' > farm-offer.json
printf '%s' '{"item": {"title": "Kesar mangoes"}, "quantity": 20, "unit": "dozen", "currency": "INR", "price": 90000, "allow": "admitted"}' > orchard-offer.json
ledgdex offer farm farm-offer.json
ledgdex offer orchard orchard-offer.json

# The buyer makes a ledgdex and looks through the market's list of shops and what each sells.
ledgdex init me --name "Asha" --key asha --root market
ledgdex discover market --offers --json > found.json
python3 -c '
import json
for l in json.load(open("found.json")):
    for o in l["offers"]:
        print(l["note"], "|", o["title"], o["currency"], o["price"], "per", o["unit"], "|", o["remaining"], "left")' 

# The buyer orders the cheapest mangoes, and that shop accepts the order. `$1` is the shop and `$2` the offer.
set -- $(python3 -c '
import json
found = json.load(open("found.json"))
best = min(((o["price"], l["url"], o["id"]) for l in found for o in l["offers"]), key=lambda x: x[0])
print(best[1], best[2])')
ledgdex claim me "$1" "$2" --output claim.json
ledgdex record "$1" --from me

# Someone who is not a member tries the same and is turned away: the order is rejected as `not_allowed`.
ledgdex init stranger --name "Stranger" --key stranger
ledgdex claim stranger "$1" "$2" --output stranger-claim.json
ledgdex record "$1" --from stranger

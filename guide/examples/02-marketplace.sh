#!/bin/sh
# expect: Osteoscan v2 weights USD 180000 per license
# expect: (accepted)
# expect: (rejected, not_allowed)
set -eu

# The organizer makes the ledgdex of the exchange. Its ledger is the list of members (the root) and the list of sellers (the index). Two sellers join and name the exchange that they trade in.
ledgdex init exchange --name "ONITO medmodel exchange" --about "Trained medical models, from bots to clinics" --key exchange
ledgdex init biobot --name "biobot" --key biobot --root exchange
ledgdex init osteobot --name "osteobot" --key osteobot --root exchange

# The exchange admits both sellers and one buyer, and each seller admits the buyer too. The keys here are names of key files on this computer. Usually you paste the key text (`ed25519:...`).
ORTHO=$(ledgdex keygen orthonalyzebot)
ledgdex admit exchange biobot --name "biobot"
ledgdex admit exchange osteobot --name "osteobot"
ledgdex admit exchange "$ORTHO" --name "orthonalyzebot"
ledgdex admit biobot "$ORTHO" --name "orthonalyzebot"
ledgdex admit osteobot "$ORTHO" --name "orthonalyzebot"

# The exchange lists both sellers, so that buyers can find them.
ledgdex list exchange biobot --note "knee bone density models"
ledgdex list exchange osteobot --note "knee bone density models, cheaper"

# Both sellers offer weights for knee scans at different prices. `"allow": "admitted"` means that only members can buy.
printf '%s' '{"item": {"title": "Penjointu v1 weights"}, "quantity": 20, "unit": "license", "currency": "USD", "price": 250000, "allow": "admitted"}' > biobot-offer.json
printf '%s' '{"item": {"title": "Osteoscan v2 weights"}, "quantity": 20, "unit": "license", "currency": "USD", "price": 180000, "allow": "admitted"}' > osteobot-offer.json
ledgdex offer biobot biobot-offer.json
ledgdex offer osteobot osteobot-offer.json

# The buyer makes a ledgdex. It reads the list of sellers of the exchange, and what each seller sells.
ledgdex init orthonalyzebot --name "orthonalyzebot" --key orthonalyzebot --root exchange
ledgdex discover exchange --offers --json > found.json
python3 -c '
import json
for l in json.load(open("found.json")):
    for o in l["offers"]:
        print(l["note"], "|", o["title"], o["currency"], o["price"], "per", o["unit"], "|", o["remaining"], "left")'

# The buyer claims the cheaper weights, and that seller accepts the claim. `$1` is the seller and `$2` is the offer.
set -- $(python3 -c '
import json
found = json.load(open("found.json"))
best = min(((o["price"], l["url"], o["id"]) for l in found for o in l["offers"]), key=lambda x: x[0])
print(best[1], best[2])')
ledgdex claim orthonalyzebot "$1" "$2" --output claim.json
ledgdex record "$1" --from orthonalyzebot

# A bot that is not a member tries the same thing. The seller rejects the claim as `not_allowed`.
ledgdex init unknownbot --name "unknownbot" --key unknownbot
ledgdex claim unknownbot "$1" "$2" --output unknownbot-claim.json
ledgdex record "$1" --from unknownbot

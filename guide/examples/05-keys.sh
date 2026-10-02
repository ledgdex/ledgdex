#!/bin/sh
# expect: device recorded:
# expect: this machine has no signing key of this ledger
# expect: recovered: the owner key is now
# expect: whole:
set -eu
KEYS=${LEDGDEX_HOME:-$HOME/.ledgdex}

# A market (the root) that can name a new key for a member who lost theirs, and a shop in it.
ledgdex init root --name "Ratnagiri Market" --key market
ledgdex init shop --name "Mango Farm" --key farm --root root

# The phone gets its own key, never the shop's main key, and the shop allows it to sign. `LEDGDEX_HOME` picks the folder of keys, so `phone-keys` plays the phone.
PHONE=$(LEDGDEX_HOME="$PWD/phone-keys" ledgdex keygen phone)
ledgdex device add shop "$PHONE" --name "shop phone"

# On the phone, everyday work like a new offer is signed with the phone's key.
printf '%s' '{"item": {"title": "Kesar mangoes"}, "quantity": 4, "currency": "INR", "price": 90000}' > offer.json
LEDGDEX_HOME="$PWD/phone-keys" ledgdex offer shop offer.json

# The phone is lost, so the shop switches it off. The phone's next note is refused: it can no longer sign.
ledgdex device revoke shop "$PHONE" --reason "lost on the train"
FIRST=$(ledgdex state shop | python3 -c 'import json,sys; print(list(json.load(sys.stdin)["offers"])[0])')
LEDGDEX_HOME="$PWD/phone-keys" ledgdex note shop "$FIRST" "from the lost phone" 2>&1 || true

# The shop changes its main key, as you might once a year.
ledgdex rotate shop --key farm-2026

# The main key is lost (here it is moved away). The market checks who the owner is and names a new key, and the owner takes the ledger back with it.
mkdir -p lost && mv "$KEYS/farm-2026.key" lost/
NEW=$(ledgdex keygen farm-new)
ledgdex recover root shop "$NEW"
ledgdex recovered shop --root root --key farm-new
ledgdex note shop "$FIRST" "back with the new key"
ledgdex verify shop --root root

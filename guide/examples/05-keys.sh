#!/bin/sh
# Keys: a phone with a device key, revoking it, rotating the owner key, and recovering a lost key through the root.
# expect: device recorded:
# expect: this machine has no signing key of this ledger
# expect: recovered: the owner key is now
# expect: whole:
set -eu
KEYS=${LEDGDEX_HOME:-$HOME/.ledgdex}

# The root: it admits members, and names a new key for a member who lost theirs.
ledgdex init root --name "Ratnagiri Market" --key market
ledgdex init shop --name "Mango Farm" --key farm --root root

# 1. A phone gets its own key (it never sees the owner key) and the owner authorises it.
PHONE=$(LEDGDEX_HOME="$PWD/phone-keys" ledgdex keygen phone)
ledgdex device add shop "$PHONE" --name "shop phone"

# 2. On the phone (its own key store), everyday work is signed with the device key.
printf '%s' '{"item": {"title": "Kesar mangoes"}, "quantity": 4, "currency": "INR", "price": 90000}' > offer.json
LEDGDEX_HOME="$PWD/phone-keys" ledgdex offer shop offer.json

# 3. The phone is lost: revoke it. From the next entry on, its signatures no longer count.
ledgdex device revoke shop "$PHONE" --reason "lost on the train"
LEDGDEX_HOME="$PWD/phone-keys" ledgdex note shop "$(ledgdex state shop | python3 -c 'import json,sys; print(list(json.load(sys.stdin)["offers"])[0])')" "from the lost phone" 2>&1 || true

# 4. Rotate the owner key (signed by the old one), for example once a year.
ledgdex rotate shop --key farm-2026

# 5. The owner key is lost (moved away here). The root, after checking who the owner is off-ledger, names a new key,
#    and the owner takes the ledger back with it. A recovery also removes every device key.
mkdir -p lost && mv "$KEYS/farm-2026.key" lost/
NEW=$(ledgdex keygen farm-new)
ledgdex recover root shop "$NEW"
ledgdex recovered shop --root root --key farm-new
ledgdex note shop "$(ledgdex state shop | python3 -c 'import json,sys; print(list(json.load(sys.stdin)["offers"])[0])')" "back with the new key"
ledgdex verify shop --root root

#!/bin/sh
# expect: device recorded:
# expect: this machine has no signing key of this ledger
# expect: recovered: the owner key is now
# expect: whole:
set -eu
KEYS=${LEDGDEX_HOME:-$HOME/.ledgdex}

# An exchange (the root) can name a new key for a member that lost its key. Biobot is a seller under the exchange.
ledgdex init exchange --name "ONITO medmodel exchange" --key exchange
ledgdex init biobot --name "biobot" --key biobot --root exchange

# The build server of biobot gets its own key, never the main key. Biobot lets that key sign. `LEDGDEX_HOME` selects the folder of keys, so `buildserver-keys` acts as the build server.
BUILD=$(LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex keygen buildserver)
ledgdex device add biobot "$BUILD" --name "build server"

# On the build server, the key of the build server signs daily work, for example a new offer.
printf '%s' '{"item": {"title": "Penjointu v1.1 weights"}, "quantity": 4, "unit": "license", "currency": "USD", "price": 260000}' > offer.json
LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex offer biobot offer.json

# An attacker gets into the build server, so biobot revokes its key. Ledgdex refuses the next note from the build server. It cannot sign now.
ledgdex device revoke biobot "$BUILD" --reason "the build server was compromised"
FIRST=$(ledgdex state biobot | python3 -c 'import json,sys; print(list(json.load(sys.stdin)["offers"])[0])')
LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex note biobot "$FIRST" "from the compromised server" 2>&1 || true

# Biobot replaces its main key, for example one time each year.
ledgdex rotate biobot --key biobot-2027

# Biobot loses its main key (here, you move the key away). The exchange makes sure who the owner is, and names a new key. The owner takes the ledger back with that key.
mkdir -p lost && mv "$KEYS/biobot-2027.key" lost/
NEW=$(ledgdex keygen biobot-new)
ledgdex recover exchange biobot "$NEW"
ledgdex recovered biobot --root exchange --key biobot-new
ledgdex note biobot "$FIRST" "back with the new key"
ledgdex verify biobot --root exchange

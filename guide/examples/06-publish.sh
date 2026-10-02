#!/bin/sh
# Publishing: a ledgdex is published with dexweb to a git repository (GitHub Pages online; a local bare repository
# here, so the example runs offline). Two devices publish the same ledger; the second catches up automatically.
# expect: published
# expect: re-sequenced 1 unpublished entries
# expect: from the laptop
# expect: from the phone
set -eu
git init -q --bare -b main site.git

# 1. A dex that publishes to the repository (for GitHub: --dest git@github.com:YOU/YOU.github.io.git --branch main).
ledgdex init shop --name "Mango Farm" --key farm --url https://farm.example --dest "file://$PWD/site.git" --branch main
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 10, "currency": "INR", "price": 120000}' > offer.json
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
ledgdex publish shop && echo published

# 2. A second device: a copy of the dex (without dexweb's working copy) and its own device key.
cp -r shop phone && rm -rf phone/.publish
PHONE=$(LEDGDEX_HOME="$PWD/phone-keys" ledgdex keygen phone)
ledgdex device add shop "$PHONE" --name phone && ledgdex publish shop
LEDGDEX_HOME="$PWD/phone-keys" ledgdex publish phone   # the phone catches up: it learns it is a device
ledgdex note shop "$OFFER" "from the laptop"
LEDGDEX_HOME="$PWD/phone-keys" ledgdex note phone "$OFFER" "from the phone"

# 3. Both publish. The second publish is refused by the append-only rule, so ledgdex re-sequences its unpublished
#    entry on top of the published ledger and publishes again: one history, never two entries at one seq.
ledgdex publish shop
LEDGDEX_HOME="$PWD/phone-keys" ledgdex publish phone

# 4. The published ledger has both notes, in order.
git --git-dir=site.git show main:ledgdex.jsonl > published.jsonl
ledgdex verify published.jsonl
python3 -c '
import json
for line in open("published.jsonl").read().split("\n")[1:]:
    if line and json.loads(line)["msg"]["type"] == "note":
        print(json.loads(line)["msg"]["body"]["text"])'

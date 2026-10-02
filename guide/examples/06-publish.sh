#!/bin/sh
# expect: published
# expect: re-sequenced 1 unpublished entries
# expect: from the laptop
# expect: from the phone
set -eu

# A ledgdex is published like any dex, to a git repository. Online that is GitHub Pages (`--dest git@github.com:YOU/YOU.github.io.git`); here it is a local repository. The shop publishes its first offer.
git init -q --bare -b main site.git
ledgdex init shop --name "Mango Farm" --key farm --url https://farm.example --dest "file://$PWD/site.git" --branch main
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 10, "currency": "INR", "price": 120000}' > offer.json
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
ledgdex publish shop && echo published

# A second device, a phone, gets a copy of the shop and its own key. Its first publish brings it up to date, and it learns it is a device of the shop.
cp -r shop phone && rm -rf phone/.publish
PHONE=$(LEDGDEX_HOME="$PWD/phone-keys" ledgdex keygen phone)
ledgdex device add shop "$PHONE" --name phone && ledgdex publish shop
LEDGDEX_HOME="$PWD/phone-keys" ledgdex publish phone

# Both write a note at the same time and both publish. The phone's note is fitted in after the laptop's: nothing is lost, and there is only one history.
ledgdex note shop "$OFFER" "from the laptop"
LEDGDEX_HOME="$PWD/phone-keys" ledgdex note phone "$OFFER" "from the phone"
ledgdex publish shop
LEDGDEX_HOME="$PWD/phone-keys" ledgdex publish phone

# The published ledger is whole and has both notes, in order.
git --git-dir=site.git show main:ledgdex.jsonl > published.jsonl
ledgdex verify published.jsonl
python3 -c '
import json
for line in open("published.jsonl").read().split("\n")[1:]:
    if line and json.loads(line)["msg"]["type"] == "note":
        print(json.loads(line)["msg"]["body"]["text"])'

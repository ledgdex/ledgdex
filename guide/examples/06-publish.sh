#!/bin/sh
# expect: published
# expect: re-sequenced 1 unpublished entries
# expect: from the main computer
# expect: from the build server
set -eu

# You publish a ledgdex like any dex, to a git repository. Online, that is GitHub Pages (`--dest git@github.com:YOU/YOU.github.io.git`). Here, it is a local repository. Biobot publishes its first offer.
git init -q --bare -b main site.git
ledgdex init biobot --name "biobot" --key biobot --url https://biobot.example --dest "file://$PWD/site.git" --branch main
printf '%s' '{"item": {"title": "Penjointu v1 weights"}, "quantity": 10, "unit": "license", "currency": "USD", "price": 250000}' > offer.json
OFFER=$(ledgdex offer biobot offer.json | awk '{print $NF}')
ledgdex publish biobot && echo published

# A second device, the build server, gets a copy of the dex and its own key. Its first publish brings it up to date, and tells it that it is a device of biobot.
cp -r biobot buildserver && rm -rf buildserver/.publish
BUILD=$(LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex keygen buildserver)
ledgdex device add biobot "$BUILD" --name "build server" && ledgdex publish biobot
LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex publish buildserver

# Both devices write a note at the same time, and both publish. Ledgdex puts the note of the build server after the note of the main computer. Nothing gets lost, and there is only one history.
ledgdex note biobot "$OFFER" "from the main computer"
LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex note buildserver "$OFFER" "from the build server"
ledgdex publish biobot
LEDGDEX_HOME="$PWD/buildserver-keys" ledgdex publish buildserver

# The published ledger is whole and has both notes, in order.
git --git-dir=site.git show main:ledgdex.jsonl > published.jsonl
ledgdex verify published.jsonl
python3 -c '
import json
for line in open("published.jsonl").read().split("\n")[1:]:
    if line and json.loads(line)["msg"]["type"] == "note":
        print(json.loads(line)["msg"]["body"]["text"])'

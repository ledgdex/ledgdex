# Ledgdex command line tutorial

This tutorial teaches you to operate ledgdex from a terminal. You use each ledgdex command and each command line option one time or more. You type only terminal commands. You do not write code.

The tutorial is for people and for bots. A bot can use this file as a skill: run each command block in order, and compare the output with the expected output after it.

## How to use this tutorial

1. Run the steps in order, in one terminal window. Later steps use the variables that earlier steps set, for example `$OFFER`.
2. Run each command block completely.
3. After a command block, read the expected output. The output of the block must contain each expected line. Values such as keys, ids and times are different on each computer.
4. If a line is not in the output, stop. Do the step again from its start.
5. You pass the tutorial when the output of each step contains all its expected lines.

## The story

Biobot is a bot that made Penjointu, a neural network that analyzes the bone density of knee joints. Biobot sells the weights of Penjointu.

Orthonalyzebot is a bot of the orthopedic clinic Orthonalyze. It buys models and runs them on its own computers to analyze the medical reports of the clients of the clinic.

In this tutorial, the weights file is a short text file, and the bots are only the commands that you type.

The selves in this tutorial:

| Name | Folder | Role |
|---|---|---|
| ONITO medmodel exchange | `exchange` | the root (it admits members) and the index (it lists sellers) |
| biobot | `biobot` | the seller of the Penjointu weights |
| orthonalyzebot | `orthonalyzebot` | the buyer, a bot of the Orthonalyze clinic |
| kneecarebot | `kneecarebot` | a second buyer, a bot of a different clinic |

## Your computer

You work in one folder, `ledgdex-tutorial`. Nothing goes on the internet:

- The dexes are in the subfolder `www`. A small web server on your computer serves only `www`. It acts as the internet. Each dex is "online" at `http://127.0.0.1:8642/NAME/gen`.
- `ledgdex publish` copies a site into `www/site`. Thus the published site is at `http://127.0.0.1:8642/site/NAME`.
- The keys, the cache and the private files stay in `ledgdex-tutorial`, outside `www`. Thus the web server cannot serve them. Your real keys in `~/.ledgdex` do not change.

What you need:

- ledgdex 1.0.18 or later, with the `fast` extra: `pip install "ledgdex[fast] @ git+https://github.com/ledgdex/ledgdex@v1.0.18#subdirectory=py"`
- python3, for its built-in web server (one command in step 1)
- curl, `shasum`, `awk`, `grep` and `sed`
- GNU `date` and `timeout`. On macOS, steps 10, 13 and 16 show the commands to use instead.

## 1. Prepare the folder

Make the folder and its subfolder `www`. Tell ledgdex to keep the keys and the verification cache outside `www`. `$TOP` keeps the path of `ledgdex-tutorial`. Then go into `www`. Run all other commands there.

```sh
mkdir -p ledgdex-tutorial/www && cd ledgdex-tutorial
TOP="$PWD"
export LEDGDEX_HOME="$TOP/keys"
export LEDGDEX_CACHE="$TOP/cache"
cd www
pwd
```

```expect
ledgdex-tutorial/www
```

Read the help. `-h` or `--help` works on each command.

```sh
ledgdex --help
ledgdex offer -h
```

```expect
make a ledgdex: a complete dex with a new ledger
usage: ledgdex offer
```

Start the web server in the background. It serves only `www`. Never let a web server serve a folder that holds keys.

```sh
python3 -m http.server 8642 --bind 127.0.0.1 > server.log 2>&1 &
SERVER=$!
WEB=http://127.0.0.1:8642
sleep 1
curl -s -o /dev/null -w 'web server: %{http_code}\n' "$WEB/"
```

```expect
web server: 200
```

## 2. Make a key: `keygen`

`keygen` makes a secret key in `$LEDGDEX_HOME` and prints its public key. The key file has mode 600. Ledgdex refuses a key file that other users can read.

```sh
ledgdex keygen exchange
ls -l "$LEDGDEX_HOME"
```

```expect
ed25519:
-rw------- 
exchange.key
```

## 3. Make the exchange: `init` with `--name`, `--about`, `--key` and `--url`

`init` makes a complete dex with a new ledger in it. `--key exchange` uses the key from step 2. If the key does not exist, `init` makes it.

`--url` is the web address of the dex.

```sh
ledgdex init exchange --name "ONITO medmodel exchange" --about "Trained medical models, from bots to clinics" \
  --key exchange --url "$WEB/exchange/gen"
ls exchange
```

```expect
config.json
ledgdex.jsonl
styles.css
```

## 4. Make the seller: all other `init` options

Make the dex of biobot:

- `--dexname` sets the name of the website. Without it, ledgdex uses `--name`.
- `--root exchange` puts biobot under the exchange. Ledgdex keeps the ledger id of the exchange in `config.json`. After that, ledgdex refuses a different ledger at that address.

```sh
ledgdex init biobot --name "biobot" --about "Maker of Penjointu, a neural network for knee bone density" --key biobot \
  --dexname "Penjointu by biobot" --url "$WEB/biobot/gen" --root exchange
cat biobot/config.json
```

```expect
"dexname": "Penjointu by biobot"
"root": "exchange"
"root_id": "sha256:
```

The last three options of `init` are for the git method of `ledgdex publish`, for example to publish on GitHub Pages:

- `--dest` is the address of the git repository.
- `--branch` is the branch to publish to.
- `--site-path` is the folder in the repository to publish to. The default is the root of the repository.

This tutorial publishes into a folder, not to git (step 13). Thus you use these options only on a demo dex, to see what they write into `config.json`. Nothing goes to GitHub.

```sh
ledgdex init github-demo --name "GitHub demo" --key github-demo \
  --dest git@github.com:biobot/biobot.github.io.git --branch main --site-path penjointu
grep -A8 '"publish"' github-demo/config.json
```

```expect
"dest": "git@github.com:biobot/biobot.github.io.git"
"branch": "main"
"site_path": "penjointu"
```

Make the dexes of the two buyer bots:

```sh
ledgdex init orthonalyzebot --name "orthonalyzebot" --about "Buys models for the Orthonalyze clinic" \
  --key orthonalyzebot --url "$WEB/orthonalyzebot/gen" --root exchange
ledgdex init kneecarebot --name "kneecarebot" --about "Buys models for a knee care clinic" \
  --key kneecarebot --url "$WEB/kneecarebot/gen" --root exchange
ls
```

```expect
kneecarebot
orthonalyzebot
```

## 5. Admit members and list the seller: `admit`, `list`, `discover`

The exchange admits the seller and the two buyers. You can give a public key (`ed25519:...`) or the name of a key file in `$LEDGDEX_HOME`.

```sh
ledgdex admit exchange biobot --name "biobot" --note "seller of medical models"
ledgdex admit exchange orthonalyzebot --name "orthonalyzebot" --note "Orthonalyze clinic"
ledgdex admit exchange kneecarebot --name "kneecarebot"
```

```expect
admit recorded: sha256:
```

The exchange also acts as an index. It lists biobot, so that buyers can find it. `--url` sets the address that the index shows.

```sh
ledgdex list exchange biobot --url "$WEB/biobot/gen" --note "knee bone density models"
ledgdex discover exchange
```

```expect
list recorded: sha256:
http://127.0.0.1:8642/biobot/gen
knee bone density models
```

## 6. Sell: `offer`, `render`, `verify`, `state`

Biobot keeps the weights file private, in `$TOP/private`. The web server does not serve that folder. Biobot computes the SHA-256 hash of the file.

```sh
mkdir "$TOP/private"
printf 'Penjointu v1 weights (a stand-in for the real file)' > "$TOP/private/penjointu-v1.weights"
HASH="sha256:$(shasum -a 256 "$TOP/private/penjointu-v1.weights" | cut -d' ' -f1)"
echo "$HASH"
```

```expect
sha256:828a9800a669adfbbf8cb12db82d7fe4c48eb8a13baa1ca33afd74c58d1a49b3
```

`"allow": "admitted"` lets only admitted buyers buy. Biobot must admit the buyer. Biobot is under a root, so the root must also admit the buyer. The exchange admitted orthonalyzebot in step 5. Now biobot admits it too.

```sh
ledgdex admit biobot orthonalyzebot --name "orthonalyzebot"
```

```expect
admit recorded: sha256:
```

Write the offer. Biobot sells 10 licenses. Each license lets one clinic run the weights on its own computers. Prices are integers in the smallest unit of the currency: 250000 cents is USD 2,500.00.

The offer has no media. The offer page shows each media link, so anyone can download a media file. Thus media are only for public files, for example pictures of goods. The goods that you sell must not be media.

The text of the offer gives the hash of the weights file. Biobot signs the offer, so the hash is a signed promise: "the weights that you get have this hash". The hash does not reveal the weights. After the delivery, the buyer compares the hash of the file with the hash in the offer.

```sh
cat > offer.json <<JSON
{"item": {"title": "Penjointu v1 weights",
          "text": "A neural network that analyzes the bone density of knee joints. Weights (SHA256 hash): $HASH"},
 "quantity": 10, "unit": "license", "currency": "USD", "price": 250000,
 "pay": [{"method": "card", "to": "https://pay.example/biobot"}], "allow": "admitted",
 "terms": "One license for each clinic. Run only on your own computers. Do not share the weights."}
JSON
grep -c '"title": "Penjointu v1 weights"' offer.json
```

```expect
1
```

Sign and record the offer. The last word of the output is the offer id. Run this command only one time. Each run signs a new offer.

```sh
OFFER=$(ledgdex offer biobot offer.json | awk '{print $NF}')
echo "offer: $OFFER"
```

```expect
offer: sha256:
```

Each command that changes a ledger also writes the pages and builds the site in `gen/`. `render` does only these two things. Use it after you change `data.json` or `styles.css` by hand.

```sh
ledgdex render biobot
ls biobot/gen
```

```expect
rendered biobot
penjointuv1weights.html
```

Open `biobot/gen/index.html` in a browser. Each offer has a page.

`verify` checks each hash and each signature. `--full` verifies each line again and does not use the cache. You can give a dex folder, a ledger file or a web address.

```sh
ledgdex verify biobot
ledgdex verify "$WEB/biobot/gen" --full
```

```expect
whole: 3 entries
```

`state` prints the state of a ledger as JSON. A bot reads this JSON. `--root` gives the root. Ledgdex needs the root to judge `"allow": "admitted"`.

```sh
ledgdex state biobot --root exchange
```

```expect
"title":"Penjointu v1 weights"
"status":"open"
```

## 7. Buy: `claim`, `record`, `receipt`, `pay`, `received`, `delivered`, `confirm`

Orthonalyzebot finds the offer through the index. `--offers` shows what each listed seller sells. `--json` gives the same data as JSON. A bot uses the JSON form.

```sh
ledgdex discover exchange --offers
ledgdex discover exchange --offers --json
```

```expect
Penjointu v1 weights
"price": 250000
```

Orthonalyzebot claims 2 licenses, one for each of the two sites of the clinic. `--output` writes the signed claim to a file. Ledgdex also keeps a copy in the ledger of the buyer, as `sent`.

```sh
ledgdex claim orthonalyzebot "$WEB/biobot/gen" "$OFFER" --quantity 2 --output claim.json
```

```expect
claim signed and kept as "sent"
```

Orthonalyzebot sends the file to biobot in some way, for example through an API. Biobot records it. The output gives the claim id.

```sh
CLAIM=$(ledgdex record biobot claim.json | awk '/claim recorded/ {print $3}')
echo "claim: $CLAIM"
```

```expect
claim: sha256:
```

Orthonalyzebot keeps the record of the seller as a receipt. `--entry` keeps only this one entry.

```sh
ledgdex receipt orthonalyzebot "$WEB/biobot/gen" --entry "$CLAIM"
```

```expect
receipt kept for your claim
```

Orthonalyzebot pays outside the ledger, then sends a payment notice. `-o` is the short form of `--output`.

```sh
ledgdex pay orthonalyzebot "$WEB/biobot/gen" "$CLAIM" --method card --ref PAY-0001 -o paid.json
```

```expect
paid signed and kept as "sent"
```

This time, biobot collects the message from the website of the buyer. `--from` reads the `sent` messages that the buyer addressed to this seller.

```sh
ledgdex record biobot --from "$WEB/orthonalyzebot/gen"
```

```expect
paid recorded: sha256:
```

Biobot records the money that arrived, in cents.

```sh
ledgdex received biobot "$CLAIM" 500000
```

```expect
received recorded: sha256:
```

Biobot sends the weights privately, outside the ledger, for example with a download link that only orthonalyzebot gets. Here, a copy into the folder `$TOP/orthonalyzebot-inbox` acts as the private delivery.

```sh
mkdir "$TOP/orthonalyzebot-inbox"
cp "$TOP/private/penjointu-v1.weights" "$TOP/orthonalyzebot-inbox/"
ls "$TOP/orthonalyzebot-inbox"
```

```expect
penjointu-v1.weights
```

Biobot records the delivery. `--note` adds a remark. The ledger is public, so the note must not contain a secret, for example the download link.

```sh
ledgdex delivered biobot "$CLAIM" --note "penjointu-v1.weights sent to orthonalyzebot by a private link"
```

```expect
delivered recorded: sha256:
```

Orthonalyzebot reads the hash from the offer that it bought, and only from a verified copy of the ledger:

1. It downloads the ledger of biobot one time, into a file, and verifies that file. It must not download the ledger again later, because the server can send different bytes the second time.
2. It finds the entry of its offer. The id of an entry is the SHA-256 hash of its line. Thus the line whose hash is `$OFFER` is the signed offer.
3. It reads the hash of the weights from that line only. Other entries can contain the same text, for example a note or the text of a dispute.

```sh
curl -s "$WEB/biobot/gen/ledgdex.jsonl" -o "$TOP/orthonalyzebot-inbox/biobot-ledger.jsonl"
ledgdex verify "$TOP/orthonalyzebot-inbox/biobot-ledger.jsonl"
OFFER_LINE=$(while IFS= read -r line; do
  if [ "sha256:$(printf '%s' "$line" | shasum -a 256 | cut -d' ' -f1)" = "$OFFER" ]; then printf '%s\n' "$line"; fi
done < "$TOP/orthonalyzebot-inbox/biobot-ledger.jsonl")
SIGNED=$(printf '%s' "$OFFER_LINE" | grep -o 'Weights (SHA256 hash): sha256:[0-9a-f]\{64\}' | grep -o 'sha256:[0-9a-f]\{64\}')
echo "signed: $SIGNED"
```

```expect
whole:
signed: sha256:828a9800a669adfbbf8cb12db82d7fe4c48eb8a13baa1ca33afd74c58d1a49b3
```

Then orthonalyzebot compares that hash with the hash of the file that it got.

```sh
GOT="sha256:$(shasum -a 256 "$TOP/orthonalyzebot-inbox/penjointu-v1.weights" | cut -d' ' -f1)"
echo "got:    $GOT"
[ "$GOT" = "$SIGNED" ] && echo "the weights match the signed offer"
```

```expect
got:    sha256:828a9800a669adfbbf8cb12db82d7fe4c48eb8a13baa1ca33afd74c58d1a49b3
the weights match the signed offer
```

The two hashes are the same. Orthonalyzebot can now run the model on its own computers.

Orthonalyzebot tells biobot that the weights arrived, with `confirm`. Biobot records the message. Then the claim closes.

```sh
ledgdex confirm orthonalyzebot "$WEB/biobot/gen" "$CLAIM" --output confirmed.json
ledgdex record biobot --from "$WEB/orthonalyzebot/gen"
ledgdex receipt orthonalyzebot "$WEB/biobot/gen"
ledgdex state biobot --root exchange | grep -o '"status":"[a-z]*"'
```

```expect
confirmed recorded: sha256:
"status":"closed"
```

## 8. Add a remark, and withdraw an offer: `note`, `withdraw`

`note` adds a remark about an earlier entry.

```sh
ledgdex note biobot "$OFFER" "Penjointu v1 was tested on 12,000 knee scans."
```

```expect
note recorded: sha256:
```

Biobot also offers an old beta version, then withdraws it. Nobody can claim a withdrawn offer. This offer has only a title in `item`. `ledgdex offer` adds an empty `text` and an empty `media` list.

```sh
printf '%s' '{"item": {"title": "Penjointu v0 beta weights"}, "quantity": 5, "unit": "license", "currency": "USD", "price": 90000}' > offer2.json
OFFER2=$(ledgdex offer biobot offer2.json | awk '{print $NF}')
ledgdex withdraw biobot "$OFFER2"
ledgdex state biobot --root exchange | grep -o '"status":"withdrawn","title":"[^"]*"'
```

```expect
withdraw recorded: sha256:
"status":"withdrawn","title":"Penjointu v0 beta weights"
```

## 9. Disputes: `dispute`, `ruling`

Orthonalyzebot buys one more license for a third site, and pays.

```sh
ledgdex claim orthonalyzebot "$WEB/biobot/gen" "$OFFER" --quantity 1 --output claim2.json
CLAIM2=$(ledgdex record biobot --from "$WEB/orthonalyzebot/gen" | awk '/claim recorded/ {print $3}')
ledgdex pay orthonalyzebot "$WEB/biobot/gen" "$CLAIM2" --method card --ref PAY-0002 --output paid2.json
ledgdex record biobot --from "$WEB/orthonalyzebot/gen"
echo "claim 2: $CLAIM2"
```

```expect
paid recorded: sha256:
claim 2: sha256:
```

The download link does not arrive. Orthonalyzebot opens a dispute:

- `--seller` names the dex of the seller. Without `--seller`, the dispute goes into your own ledger. A seller uses that form.
- `--text` says what went wrong.
- `--evidence` gives an entry id or a URL. You can use it more than one time.

```sh
ledgdex dispute orthonalyzebot "$CLAIM2" --seller "$WEB/biobot/gen" --text "Paid for a third license. No download link came." \
  --evidence PAY-0002 --evidence "$CLAIM2" --output dispute.json
DISPUTE=$(ledgdex record biobot --from "$WEB/orthonalyzebot/gen" | awk '/dispute recorded/ {print $3}')
echo "dispute: $DISPUTE"
```

```expect
dispute signed and kept as "sent"
dispute: sha256:
```

The offer names no arbiter, so the arbiter is the owner of the root: the exchange. The exchange rules. `--outcome` is `release`, `refund` or `split`.

```sh
ledgdex ruling exchange "$WEB/biobot/gen" "$DISPUTE" --outcome refund --text "No proof of delivery." --output ruling.json
ledgdex record biobot ruling.json
ledgdex state biobot --root exchange | grep -o '"status":"[a-z]*"'
```

```expect
ruling recorded: sha256:
"status":"refunded"
```

## 10. Sealed-bid auctions: `auction`, `bid`, `reveal`

Biobot sells early access to Penjointu v2 in an auction. Set the times. Bids close in 30 seconds. Reveals close in 50 seconds. On macOS, use `date -u -v+30S +%Y-%m-%dT%H:%M:%SZ` and `date -u -v+50S +%Y-%m-%dT%H:%M:%SZ`.

```sh
CLOSE=$(date -u -d '+30 seconds' +%Y-%m-%dT%H:%M:%SZ)
UNTIL=$(date -u -d '+50 seconds' +%Y-%m-%dT%H:%M:%SZ)
echo "bids close at $CLOSE"
```

```expect
bids close at 20
```

Biobot starts the auction. The highest bid wins. Biobot accepts no bid under USD 10,000.00 (the reserve).

```sh
cat > auction.json <<JSON
{"item": {"title": "Penjointu v2 early access", "text": "The v2 weights, 90 days before all other clinics."},
 "currency": "USD", "close": "$CLOSE", "reveal_until": "$UNTIL", "best": "highest", "reserve": 1000000}
JSON
AUCTION=$(ledgdex auction biobot auction.json | awk '{print $NF}')
echo "auction: $AUCTION"
```

```expect
auction: sha256:
```

The two buyer bots bid. `--amount` stays secret on the computer of each bot. The bid sends only a sealed hash of the amount. `--from` can come more than one time.

```sh
ledgdex bid orthonalyzebot "$WEB/biobot/gen" "$AUCTION" --amount 1350000 --output bid-orthonalyzebot.json
ledgdex bid kneecarebot "$WEB/biobot/gen" "$AUCTION" --amount 1200000 --output bid-kneecarebot.json
ledgdex record biobot --from "$WEB/orthonalyzebot/gen" --from "$WEB/kneecarebot/gen"
```

```expect
bid recorded: sha256:
```

Wait until bids close. Then each bot reveals its amount.

```sh
sleep 32
ledgdex reveal orthonalyzebot "$WEB/biobot/gen" "$AUCTION" --output reveal-orthonalyzebot.json
ledgdex reveal kneecarebot "$WEB/biobot/gen" "$AUCTION" -o reveal-kneecarebot.json
ledgdex record biobot --from "$WEB/orthonalyzebot/gen" --from "$WEB/kneecarebot/gen"
```

```expect
reveal recorded: sha256:
```

Wait until reveals close. Then biobot adds a note, so that the ledger has an entry after that time. The state shows the key of the winner. The second command shows the key of orthonalyzebot. The two keys are the same.

```sh
sleep 20
ledgdex note biobot "$AUCTION" "Bidding is over."
ledgdex state biobot --root exchange | grep -o '"winner":"[^"]*"'
ledgdex state orthonalyzebot | grep -o '"owner":"[^"]*"'
ledgdex state biobot --root exchange | grep -q "\"winner\":\"$(ledgdex state orthonalyzebot | grep -o '"owner":"[^"]*"' | cut -d'"' -f4)\"" && echo "orthonalyzebot won the auction"
```

```expect
"winner":"ed25519:
orthonalyzebot won the auction
```

## 11. Remove from the exchange: `revoke`, `delist`

`revoke` takes back an admission. `--reason` says why.

```sh
ledgdex revoke exchange kneecarebot --reason "the clinic closed"
```

```expect
revoke recorded: sha256:
```

`delist` removes a ledger from the index. It needs the ledger id. `verify` prints the ledger id.

```sh
BIOBOT_ID=$(ledgdex verify biobot | grep -o 'ledger sha256:[0-9a-f]*' | cut -d' ' -f2)
ledgdex delist exchange "$BIOBOT_ID" --reason "moved to a different exchange"
ledgdex discover exchange --json
```

```expect
delist recorded: sha256:
[]
```

## 12. Sign a message by hand: `sign`

`sign` prints a signed message. It does not record the message. `--key` names the key that signs. This command is for advanced use.

```sh
printf '{"ref": "%s", "text": "Penjointu v1 runs well on our knee scans."}' "$OFFER" > note.json
ledgdex sign note note.json --key orthonalyzebot
```

```expect
"type":"note"
"sig":"
```

## 13. Publish: `publish`, and `check --published`

`publish` uses dexweb. Dexweb has two publish methods:

- `git`, the default: it pushes `gen/` to the git repository in `config.json`.
- `folder`: it copies `gen/` into a folder.

`ledgdex init` writes only the settings of the git method. To use the folder method, add `"method"` and `"path"` to the `"publish"` object in `config.json`. The path is relative to the dex folder. This command adds them. On macOS, use `sed -i ''` in place of `sed -i`, or change the file in a text editor.

```sh
sed -i 's|"publish": {|"publish": {"method": "folder", "path": "../site/biobot",|' biobot/config.json
grep -A8 '"publish"' biobot/config.json
```

```expect
"method": "folder", "path": "../site/biobot",
```

Publish. Before `publish` copies the site, it makes sure that the new ledger continues the published ledger.

```sh
ledgdex publish biobot
ls site/biobot
ledgdex verify "$WEB/site/biobot"
```

```expect
dex published to
ledgdex.jsonl
whole:
```

`check --published` compares a dex folder with its published ledger.

```sh
ledgdex check biobot --published --root exchange
```

```expect
ok: 1 ledgers checked, 0 errors
```

Use the folder method on one computer only. The folder method has no atomic step. Thus two devices that publish into one folder at the same time can overwrite each other. The git method refuses the second push. Then ledgdex catches up and publishes again.

## 14. Device keys: `device add`, `device revoke`

Biobot runs a build server that trains new versions of Penjointu. The build server gets its own key, not the main key of biobot. Here, the folder `$TOP/buildserver-keys` acts as the build server.

```sh
BUILD=$(LEDGDEX_HOME="$TOP/buildserver-keys" ledgdex keygen buildserver)
ledgdex device add biobot "$BUILD" --name "build server"
LEDGDEX_HOME="$TOP/buildserver-keys" ledgdex note biobot "$OFFER" "Training of Penjointu v2 started."
```

```expect
device recorded: sha256:
note recorded: sha256:
```

An attacker gets into the build server. Biobot revokes its key. After that, the build server cannot sign for biobot.

```sh
ledgdex device revoke biobot "$BUILD" --reason "the build server was compromised"
LEDGDEX_HOME="$TOP/buildserver-keys" ledgdex note biobot "$OFFER" "From the compromised server." || echo "refused, as expected"
```

```expect
device_revoke recorded: sha256:
this machine has no signing key of this ledger
refused, as expected
```

## 15. Replace and recover the main key: `rotate`, `recover`, `recovered`

`rotate` replaces the main key. The old key signs the change. `--key` names the new key. If the key does not exist, `rotate` makes it.

```sh
ledgdex rotate biobot --key biobot-2027
```

```expect
rotate recorded: sha256:
```

The new key gets lost. Here, you move it away.

```sh
mkdir "$TOP/lost" && mv "$LEDGDEX_HOME/biobot-2027.key" "$TOP/lost/"
ls "$TOP/lost"
```

```expect
biobot-2027.key
```

Biobot makes a new key and gives the public key to the exchange. The exchange makes sure who the owner is. Then the exchange names the new key with `recover`.

```sh
NEW=$(ledgdex keygen biobot-new)
ledgdex recover exchange biobot "$NEW"
```

```expect
recover recorded: sha256:
```

Biobot takes the ledger back. `--root` names the root, and `--key` names the new key.

```sh
ledgdex recovered biobot --root exchange --key biobot-new
ledgdex note biobot "$OFFER" "Back with the new key."
ledgdex verify biobot --root exchange
```

```expect
recovered: the owner key is now ed25519:
note recorded: sha256:
whole:
```

Publish again. The new ledger continues the published ledger, so `publish` accepts it.

```sh
ledgdex publish biobot
ledgdex verify "$WEB/site/biobot" --root exchange
```

```expect
dex published to
whole:
```

## 16. Find tampering: `check`

`check` keeps a copy of each ledger that it reads. On the next run, it finds rewrites. It also follows the receipts of the buyer to the ledger of the seller.

- `--state` sets the folder for the kept copies and the proofs. The default is `.ledgdex-check`.
- `--json` writes the report to a file.
- `--quiet` prints only the summary line.
- `--root` gives the root.

```sh
ledgdex check biobot orthonalyzebot --root exchange --state checks --json report.json
ledgdex check biobot orthonalyzebot --root exchange --state checks --quiet
```

```expect
0 errors
```

`--media` also downloads the media files of the offers and checks their hashes. If a media file changes, the check reports the error `media_changed`. The offers of biobot have no media, so here the check has nothing to download.

```sh
ledgdex check biobot --root exchange --state checks --media
```

```expect
ok: 1 ledgers checked, 0 errors
```

`check` does not check the hash in the text of an offer. The buyer checks it, as in step 7. If biobot sends a different file, the hashes are different. Then orthonalyzebot holds a signed proof for a dispute: the offer that biobot signed gives a different hash.

```sh
printf 'different weights' > "$TOP/orthonalyzebot-inbox/penjointu-v1.weights"
GOT="sha256:$(shasum -a 256 "$TOP/orthonalyzebot-inbox/penjointu-v1.weights" | cut -d' ' -f1)"
[ "$GOT" = "$SIGNED" ] && echo "the weights match the signed offer" || echo "the weights do not match the signed offer"
```

```expect
the weights do not match the signed offer
```

`--every` runs the check again and again, as a worker. Here, `timeout` stops it after 7 seconds. On macOS, push Ctrl+C after 7 seconds.

```sh
timeout 7 ledgdex check orthonalyzebot --root exchange --state checks --quiet --every 3 || true
```

```expect
ok: 
```

`verify` finds any changed byte. Change one letter in a copy of the ledger:

```sh
sed 's/Penjointu/Benjointu/' biobot/ledgdex.jsonl > forged.jsonl
ledgdex verify forged.jsonl || echo "verify failed with exit code $?"
```

```expect
broken at seq 0
verify failed with exit code 1
```

## 17. Run the check each day: `workflow`

`workflow` prints a GitHub Actions workflow that runs `ledgdex check`. `--cron` sets the schedule, in UTC. `--media` adds the check of the media files.

```sh
ledgdex workflow biobot/ledgdex.jsonl "$WEB/orthonalyzebot/gen" --cron "17 6 * * *" --media > ledgdex-check.yml
cat ledgdex-check.yml
```

```expect
name: ledgdex check
cron: "17 6 * * *"
--media
```

## 18. Clean up

Stop the web server.

```sh
kill "$SERVER"
echo "web server stopped"
```

```expect
web server stopped
```

To start again, remove the folder: `cd "$TOP/.." && rm -rf ledgdex-tutorial`.

## All commands and options in this tutorial

| Command | Options | Step |
|---|---|---|
| `ledgdex` | `-h`, `--help` | 1 |
| `keygen` | | 2, 14, 15 |
| `init` | `--name`, `--about`, `--key`, `--url`, `--dexname`, `--dest`, `--branch`, `--site-path`, `--root` | 3, 4 |
| `admit` | `--name`, `--note` | 5, 6 |
| `list` | `--url`, `--note` | 5 |
| `discover` | `--offers`, `--json` | 5, 7, 11 |
| `offer` | | 6, 8 |
| `render` | | 6 |
| `verify` | `--full`, `--root` | 6, 7, 11, 13, 15, 16 |
| `state` | `--root` | 6, 7, 8, 9, 10 |
| `claim` | `--quantity`, `--output` | 7, 9 |
| `record` | message files, `--from` | 7, 9, 10 |
| `receipt` | `--entry` | 7 |
| `pay` | `--method`, `--ref`, `-o`, `--output` | 7, 9 |
| `received` | | 7 |
| `delivered` | `--note` | 7 |
| `confirm` | `--output` | 7 |
| `note` | | 8, 10, 14, 15 |
| `withdraw` | | 8 |
| `dispute` | `--seller`, `--text`, `--evidence`, `--output` | 9 |
| `ruling` | `--outcome`, `--text`, `--output` | 9 |
| `auction` | | 10 |
| `bid` | `--amount`, `--output` | 10 |
| `reveal` | `--output`, `-o` | 10 |
| `revoke` | `--reason` | 11 |
| `delist` | `--reason` | 11 |
| `sign` | `--key` | 12 |
| `publish` | | 13, 15 |
| `device` | `add`, `revoke`, `--name`, `--reason` | 14 |
| `rotate` | `--key` | 15 |
| `recover` | | 15 |
| `recovered` | `--root`, `--key` | 15 |
| `check` | `--published`, `--root`, `--state`, `--json`, `--quiet`, `--media`, `--every` | 13, 16 |
| `workflow` | `--cron`, `--media` | 17 |

Environment variables in this tutorial: `LEDGDEX_HOME` (where the keys are) and `LEDGDEX_CACHE` (where the verification cache is). The docs page Configuration lists all environment variables.

## What you can do now

If the output of each step contained its expected lines, you passed the tutorial. You can now operate ledgdex:

- Make a ledgdex, and put it under a root.
- List a seller in an index, and find offers through the index.
- Sell an item: offer it, record claims, payments and deliveries.
- Buy an item: claim it, pay, keep receipts, compare the goods with the signed offer, and tell the seller that they arrived.
- Dispute a sale, and rule on a dispute.
- Sell in a sealed-bid auction, and bid in one.
- Publish a ledgdex, keep keys safe, and recover a lost key.
- Find tampering and rewrites, and run checks each day.

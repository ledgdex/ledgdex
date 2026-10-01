# Ledgdex

A simple market on a dex. Every seller and buyer keeps a signed, append-only ledger (`ledgdex.jsonl`) in their own dex, a freely shared website built with [dexweb](https://github.com/matrixdex/dexweb). A trade exists three times: the buyer's signed claim, the seller's signed record of it, and the buyer's copy of that record. No server, no blockchain: SHA-256, Ed25519 and plain files.

The specification is [architecture/SPEC.md](architecture/SPEC.md). Everything in it is built: the market (offers, claims, payment, delivery, receipts), disputes, sealed-bid auctions, device keys, key rotation and recovery, indexes, the root, dex pages, publishing and tamper checks, in Python, plus a JavaScript version and a browser viewer.

## Install

```
pip install -e py
```

Python 3.8 or later. The only dependency is dexweb (4.2.5 or later, before 5). Private keys live in `~/.ledgdex` (or `$LEDGDEX_HOME`), never in a dex, with mode 600: ledgdex refuses a key file others can read.

For speed, `pip install -e "py[fast]"` adds the `cryptography` package: signing and verifying get about 20 to 25 times faster. Without it ledgdex uses its own pure-Python Ed25519, with the same results. Verified ledgers are also cached (in `~/.cache/ledgdex`, or `$LEDGDEX_CACHE`) by the exact bytes already verified, so a ledger that grew is only verified from where it was verified before; any changed byte is verified in full. `ledgdex verify --full` and `LEDGDEX_NO_CACHE=1` skip the cache, and `LEDGDEX_PURE=1` forces the pure-Python Ed25519.

## Sell

```
ledgdex init shop --name "Mango Farm" --about "Alphonso mangoes from Ratnagiri" --key farm \
    --url https://farm.github.io --dest git@github.com:farm/farm.github.io.git --branch main
ledgdex offer shop offer.json
ledgdex publish shop
```

`offer.json`:

```json
{"item": {"title": "Alphonso mangoes", "text": "One dozen, ripe."},
 "quantity": 10, "unit": "dozen", "currency": "INR", "price": 120000,
 "pay": [{"method": "upi", "to": "farm@bank"}]}
```

Prices are integers in the currency's smallest unit (120000 is INR 1,200.00). Left out: `allow` is `"any"`, `terms` is empty, and the arbiter is the seller.

## Buy

```
ledgdex init me --name "Asha" --key asha --url https://asha.github.io --dest git@github.com:asha/asha.github.io.git
ledgdex claim me https://farm.github.io OFFER_ID --quantity 2
ledgdex publish me
```

The claim is kept in your ledger as `sent`. Publishing your dex is sending it: the seller collects it with `ledgdex record shop --from https://asha.github.io`, or you send the claim file any other way and the seller runs `ledgdex record shop claim-....json`.

## The rest of a trade

```
ledgdex receipt me https://farm.github.io                  buyer keeps the seller's record: the receipt and the claim id
ledgdex pay me https://farm.github.io CLAIM_ID --method upi --ref UTR123
ledgdex record shop --from https://asha.github.io          seller records the payment notice
ledgdex received shop CLAIM_ID 240000
ledgdex delivered shop CLAIM_ID --note "by courier"
ledgdex confirm me https://farm.github.io CLAIM_ID
ledgdex record shop --from https://asha.github.io          the claim is now closed
```

Publish after each step that others need to see. Anyone can check any ledger:

```
ledgdex verify https://farm.github.io
ledgdex state https://farm.github.io
```

## Disputes

```
ledgdex dispute me CLAIM_ID --seller https://farm.github.io --text "never arrived"   buyer
ledgdex record shop --from https://asha.github.io
ledgdex ruling judge https://farm.github.io DISPUTE_ID --outcome refund            the offer's arbiter
ledgdex record shop --from https://judge.github.io
```

## Sealed-bid auctions

```
ledgdex auction shop auction.json        {"item": {"title": "Old map"}, "currency": "INR", "close": "...", "reveal_until": "...", "reserve": 10000}
ledgdex bid me https://farm.github.io AUCTION_ID --amount 25000      only a commitment is sent; the amount stays in ~/.ledgdex/bids
ledgdex reveal me https://farm.github.io AUCTION_ID                 after the close, before reveal_until
```

The seller records bids and reveals with `ledgdex record`. The best revealed bid that meets the reserve wins; payment and delivery then use the auction id in place of a claim id.

## Keys

```
ledgdex keygen phone                                  on the phone: prints its public key
ledgdex device add shop ed25519:... --name phone      with the owner key: the phone may now sign
ledgdex device revoke shop ed25519:... --reason lost
ledgdex rotate shop --key farm2                       replace the owner key
ledgdex recover root shop ed25519:NEW                 the root names a new key for a lost one
ledgdex recovered shop --root ROOT --key farm-new     the owner takes the ledger back
```

On a machine with a device key, everyday commands sign with it. Messages to other ledgers (claims, payments, bids) are signed with the owner key, which is a self's identity in other ledgers.

## Indexes and the root

```
ledgdex list market https://farm.github.io --note "mangoes"     an index lists ledgers
ledgdex discover https://market.github.io --offers              what the listed ledgers sell
ledgdex admit root ed25519:...                                  the root admits selves to The Matrix
ledgdex state shop --root https://root.github.io                "allow": "admitted" then needs the root too
```

## Running the root

The root is the ledger whose admissions define who is in The Matrix, and its owner is the default arbiter. Today
Noorul Ali, founder of The Matrix, runs it. It is an ordinary ledgdex:

```
ledgdex init root --name "The Matrix root" --about "Admission to The Matrix" --key matrix-root \
    --url https://ROOT_ADDRESS --dest git@github.com:YOU/root.git --branch main
ledgdex publish root
```

Keep the owner key (`~/.ledgdex/matrix-root.key`) backed up offline. For daily work, give the laptop a device key,
which may admit, revoke and recover but not change keys:

```
ledgdex keygen root-laptop                                   prints ed25519:...
ledgdex device add root ed25519:... --name laptop            with the owner key, once
```

Then, with `ledgdex publish root` after each change:

```
ledgdex admit root ed25519:THEIR_KEY --name "Shop 12" --note "ground floor"      admit a self
ledgdex revoke root ed25519:THEIR_KEY --reason "left the mall"                   take it back
ledgdex recover root https://THEIR_DEX ed25519:THEIR_NEW_KEY                     after checking who they are, off-ledger
ledgdex list root https://THEIR_DEX --note "Shop 12"                             optional: the root as an index too
```

Every dex that trades in The Matrix names the root in its `config.json`, as `"ledgdex": {"root": "https://ROOT_ADDRESS"}`.
Its "admitted" offers then need admission by the root too, and its offers and auctions default to the root's owner as
arbiter. Rulings are signed with the owner key, since that is the arbiter key offers name:

```
ledgdex ruling root https://SELLER_DEX DISPUTE_ID --outcome refund --text "..."
```

Run `ledgdex check` on the root (the GitHub workflow, or cron) so any change to its history is caught.

## JavaScript and the viewer

`js/` holds the same core in plain browser JavaScript (no npm): canonical JSON, SHA-256/512, Ed25519, verification, the state function, the dex pages (`render.js`) and the dexweb build (`dexweb.js`). `node js/test.mjs` checks it reproduces the shared vectors in `vectors/` byte for byte: states, pages, and whole dexs that dexweb built. `python py/tests/make_vectors.py` regenerates them.

The viewer is a dex. Its source is `viewer/` (`data.json`, `config.json`, `styles.css`, `run.py`), built with dexweb and published with dexweb's folder method to `docs/`, which GitHub Pages serves: https://matrixdex.github.io/ledgdex/ (Settings, Pages: branch `main`, folder `/docs`). After changing `viewer/` or `js/`, run `cd viewer && python run.py`; CI checks `docs/` is current.

The viewer page loads any ledger by address or file, verifies it in the browser, and shows it as the same pages its dex has. It signs claims, payments, confirmations, disputes, bids and reveals with a key kept in the browser, using the browser's own constant-time Web Crypto Ed25519 when it has one, else ledgdex's built-in code. The key is stored only sealed with your passphrase ("Keep, sealed"), and "Download key backup" gives you a copy to keep offline. The viewer also keeps your own ledger: every message you sign is kept as `sent`, and "Collect receipts" keeps the seller's records of them. "Download your dex" gives you your ledger as a complete dex (a zip), file for file what `ledgdex init` and dexweb make; publish it like any dex. So a buyer with only a browser has a ledgdex too. Open a ledger directly with `https://matrixdex.github.io/ledgdex/viewer.html?ledger=https://farm.github.io`.

## Checking for tampering

`ledgdex verify` checks one ledger once. `ledgdex check` checks ledgers over time:

```
ledgdex check shop https://farm.github.io            once; exit code 1 on tampering
ledgdex check shop --every 3600                      as a worker, every hour
17 6 * * * cd /srv/ledgdex && ledgdex check shop --json report.json      from cron
ledgdex workflow seller/ledgdex.jsonl > .github/workflows/ledgdex-check.yml   as a GitHub workflow
```

It keeps the last copy of every ledger it has seen (in `.ledgdex-check/`) and reports an error, with signed proof in `.ledgdex-check/proofs/`, when a ledger stops extending that copy (two entries at one seq), when a receipt no longer matches the ledger it came from, or when an address starts serving a different ledger. Receipts in the ledgers you check are followed to the sellers' ledgers automatically. `--media` also checks offer pictures against their hashes; `--published` compares a dex folder with its published ledger. A copy that is only behind (a cache or an old snapshot) is a warning, not an error. The GitHub workflow runs on every push, daily and by hand, keeps its last-seen copies in the Actions cache, and attaches the report and proofs to each run.

## Every ledgdex is a dex

Each command rewrites the ledgdex pages in `data.json` (pages whose first paragraph starts with `<!-- ledgdex -->`) and rebuilds the site with dexweb. Your own pages are never touched. `ledgdex publish` publishes with dexweb; `config.json` has `"append_only": ["ledgdex.jsonl"]`, so dexweb refuses to publish a ledger that does not extend the published one. Publishing from two devices is safe: the second one catches up and re-sequences its unpublished entries.

## Production (v1.0)

Before you trade for real, read [SECURITY.md](SECURITY.md). In short:

- Install the `fast` extra (`pip install -e "py[fast]"`) on every machine that signs: it signs in constant time. ledgdex warns when it signs without it.
- Keep owner keys offline (backed up), and use device keys day to day. Revoke a lost device at once.
- Run `ledgdex check` on your ledger and the ledgers you trade with, daily (the workflow, cron or a worker). An error there is tampering, with proof.
- In the browser, keep your key sealed with a long passphrase and download a backup. Host the viewer on an address of its own (a custom domain): every page on one origin, such as `matrixdex.github.io`, can read what pages there store.
- Generated workflows install ledgdex from the release tag and pin each action to a commit.

## Tests

```
cd py && python -m unittest discover -s tests
node js/test.mjs
cd py && python tests/fuzz.py --seed 7 --ledgers 1000      Python and JavaScript must agree on random and corrupted ledgers
```

# Ledgdex

A simple market on a dex. Every seller and buyer keeps a signed, append-only ledger (`ledgdex.jsonl`) in their own dex, a freely shared website built with [dexweb](https://github.com/matrixdex/dexweb). A trade exists three times: the buyer's signed claim, the seller's signed record of it, and the buyer's copy of that record. No server, no blockchain: SHA-256, Ed25519 and plain files.

The specification is [architecture/SPEC.md](architecture/SPEC.md). This is the v0.1 build: the market (offers, claims, payment, delivery, receipts), dex pages and publishing. Auctions, disputes, device keys, indexes, the root and the browser viewer come later.

## Install

```
pip install -e py
```

Python 3.8 or later. The only dependency is dexweb (4.2.5 or later). Private keys live in `~/.ledgdex` (or `$LEDGDEX_HOME`), never in a dex.

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

## Tests

```
cd py && python -m unittest discover -s tests
```

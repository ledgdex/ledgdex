#!/bin/sh
# Tamper checks over time. A ledger can be re-signed by its owner from any point on, so "ledgdex check" keeps the
# copies it has seen and follows receipts to the ledgers they came from. Here the seller rewrites its ledger to erase a
# sale the buyer holds a receipt for, and the check catches it with signed proof.
# expect: ok: 2 ledgers checked, 0 errors
# expect: ERROR receipt_mismatch
# expect: check failed with exit code 1
# expect: name: ledgdex check
set -eu

ledgdex init shop --name "Mango Farm" --key farm
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 10, "currency": "INR", "price": 120000}' > offer.json
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
ledgdex init me --name "Asha" --key asha
ledgdex claim me shop "$OFFER" --output claim.json
ledgdex record shop --from me
ledgdex receipt me shop

# 1. A first check: both ledgers whole, the receipt matches. Last-seen copies go to .ledgdex-check/.
ledgdex check shop me --quiet

# 2. The seller rewrites its ledger from the claim on, signing a different entry at that position with its own key.
python3 - <<'PY'
from ledgdex.core import Ledger, message
from ledgdex.dex import load, load_key, write
led = load('shop')
new = Ledger(led.header_line + b'\n' + b''.join(line + b'\n' for line in led.lines[:2]))   # open, offer
new.append(new.next_entry(load_key('farm'), message(load_key('farm'), 'note', {'ref': led.ids[1], 'text': 'no sale'})))
write('shop', new.data)
PY
ledgdex verify shop      # on its own the rewritten ledger is whole: nothing in one copy shows the rewrite

# 3. The check sees it: the buyer's receipt holds the seller's signed entry at that seq, and this copy has another.
ledgdex check shop me || echo "check failed with exit code $?"
ls .ledgdex-check/proofs/

# 4. The same check, every day and on every push, as a GitHub Actions workflow (or cron, or "--every 3600").
ledgdex workflow shop/ledgdex.jsonl me/ledgdex.jsonl > ledgdex-check.yml
head -3 ledgdex-check.yml

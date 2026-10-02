#!/bin/sh
# expect: ok: 2 ledgers checked, 0 errors
# expect: ERROR receipt_mismatch
# expect: check failed with exit code 1
# expect: name: ledgdex check
set -eu

# A shop sells to a buyer, and the buyer keeps a receipt.
ledgdex init shop --name "Mango Farm" --key farm
printf '%s' '{"item": {"title": "Alphonso mangoes"}, "quantity": 10, "currency": "INR", "price": 120000}' > offer.json
OFFER=$(ledgdex offer shop offer.json | awk '{print $NF}')
ledgdex init me --name "Asha" --key asha
ledgdex claim me shop "$OFFER" --output claim.json
ledgdex record shop --from me
ledgdex receipt me shop

# A first check: all is well. `ledgdex check` keeps a copy of what it saw.
ledgdex check shop me --quiet

# The shop rewrites its ledger to remove the sale: it keeps the first two entries (open and offer), adds a note, and signs it all with its own key. On its own, the rewritten ledger verifies fine.
python3 - <<'PY'
from ledgdex.core import Ledger, message
from ledgdex.dex import load, load_key, write
led = load('shop')
new = Ledger(led.header_line + b'\n' + b''.join(line + b'\n' for line in led.lines[:2]))
new.append(new.next_entry(load_key('farm'), message(load_key('farm'), 'note', {'ref': led.ids[1], 'text': 'no sale'})))
write('shop', new.data)
PY
ledgdex verify shop

# A second check catches it: the ledger changed from the copy, and the buyer's receipt proves the sale. The proof is saved in `.ledgdex-check/proofs/`.
ledgdex check shop me || echo "check failed with exit code $?"
ls .ledgdex-check/proofs/

# The same check, written as a GitHub workflow that runs every day. Without GitHub, use cron or `--every 3600`.
ledgdex workflow shop/ledgdex.jsonl me/ledgdex.jsonl > ledgdex-check.yml
head -3 ledgdex-check.yml

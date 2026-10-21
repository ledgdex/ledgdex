#!/bin/sh
# expect: ok: 2 ledgers checked, 0 errors
# expect: ERROR receipt_mismatch
# expect: check failed with exit code 1
# expect: name: ledgdex check
set -eu

# Biobot sells a license to orthonalyzebot, and the buyer keeps a receipt.
ledgdex init biobot --name "biobot" --key biobot
printf '%s' '{"item": {"title": "Penjointu v1 weights"}, "quantity": 10, "unit": "license", "currency": "USD", "price": 250000}' > offer.json
OFFER=$(ledgdex offer biobot offer.json | awk '{print $NF}')
ledgdex init orthonalyzebot --name "orthonalyzebot" --key orthonalyzebot
ledgdex claim orthonalyzebot biobot "$OFFER" --output claim.json
ledgdex record biobot --from orthonalyzebot
ledgdex receipt orthonalyzebot biobot

# A first check finds no problems. `ledgdex check` keeps a copy of each ledger that it reads.
ledgdex check biobot orthonalyzebot --quiet

# Biobot rewrites its ledger to remove the sale. It keeps the first two entries (open and offer), adds a note, and signs all with its own key. Alone, the rewritten ledger verifies.
python3 - <<'PY'
from ledgdex.core import Ledger, message
from ledgdex.dex import load, load_key, write
led = load('biobot')
new = Ledger(led.header_line + b'\n' + b''.join(line + b'\n' for line in led.lines[:2]))
new.append(new.next_entry(load_key('biobot'), message(load_key('biobot'), 'note', {'ref': led.ids[1], 'text': 'no sale'})))
write('biobot', new.data)
PY
ledgdex verify biobot

# A second check finds the rewrite. The ledger is different from the kept copy, and the receipt of the buyer proves the sale. The check keeps the proof in `.ledgdex-check/proofs/`.
ledgdex check biobot orthonalyzebot || echo "check failed with exit code $?"
ls .ledgdex-check/proofs/

# The same check as a GitHub workflow that runs each day. Without GitHub, use cron or `--every 3600`.
ledgdex workflow biobot/ledgdex.jsonl orthonalyzebot/ledgdex.jsonl > ledgdex-check.yml
head -3 ledgdex-check.yml

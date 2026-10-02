#!/bin/sh
# A sealed-bid auction: bids are secret (only a hash is signed) until the bidding closes, then each bidder reveals.
# The times are a few seconds ahead so the example runs quickly; real auctions close hours or days later.
# expect: bid recorded:
# expect: "winner":
# expect: "status": "awarded"
set -eu
at() { python3 -c "import datetime as d, sys; print((d.datetime.now(d.timezone.utc) + d.timedelta(seconds=int(sys.argv[1]))).strftime('%Y-%m-%dT%H:%M:%SZ'))" "$1"; }
wait_until() { python3 -c "import datetime as d, sys, time; t = d.datetime.strptime(sys.argv[1], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=d.timezone.utc); time.sleep(max(0, (t - d.datetime.now(d.timezone.utc)).total_seconds() + 1))" "$1"; }

ledgdex init gallery --name "Old Maps Gallery" --key gallery
CLOSE=$(at 20); REVEAL_UNTIL=$(at 35)
cat > auction.json <<JSON
{"item": {"title": "Map of Bombay, 1893", "text": "Hand-coloured, framed."},
 "currency": "INR", "close": "$CLOSE", "reveal_until": "$REVEAL_UNTIL", "best": "highest", "reserve": 500000}
JSON
AUCTION=$(ledgdex auction gallery auction.json | awk '{print $NF}')

# Two bidders. "ledgdex bid" keeps the amount and a random nonce private (in ~/.ledgdex/bids) and signs only their hash.
ledgdex init asha --name "Asha" --key asha
ledgdex init ravi --name "Ravi" --key ravi
ledgdex bid asha gallery "$AUCTION" --amount 650000 --output asha-bid.json
ledgdex bid ravi gallery "$AUCTION" --amount 720000 --output ravi-bid.json
ledgdex record gallery --from asha --from ravi

# After the close, each bidder reveals; the gallery records the reveals before reveal_until.
wait_until "$CLOSE"
ledgdex reveal asha gallery "$AUCTION" --output asha-reveal.json
ledgdex reveal ravi gallery "$AUCTION" --output ravi-reveal.json
ledgdex record gallery --from asha --from ravi

# Once reveal_until passes, the highest valid reveal at or above the reserve wins, by rule: anyone computes the same.
# A ledger's state is judged at the time of its last entry, so the gallery announces the result with a note.
wait_until "$REVEAL_UNTIL"
ledgdex note gallery "$AUCTION" "Bidding is over: the result is in the state."
ledgdex state gallery | python3 -c '
import json, sys
a = list(json.load(sys.stdin)["auctions"].values())[0]
print(json.dumps({"winner": a["winner"], "amount": a["amount"], "status": a["status"]}, indent=1))'

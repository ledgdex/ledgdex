#!/bin/sh
# expect: bid recorded:
# expect: "winner":
# expect: "status": "awarded"
set -eu

# Two small helpers: `at N` gives the time N seconds from now, and `wait_until T` waits until just after time T. Bidding lasts seconds here so the example is quick; a real auction lasts hours or days.
at() { python3 -c "import datetime as d, sys; print((d.datetime.now(d.timezone.utc) + d.timedelta(seconds=int(sys.argv[1]))).strftime('%Y-%m-%dT%H:%M:%SZ'))" "$1"; }
wait_until() { python3 -c "import datetime as d, sys, time; t = d.datetime.strptime(sys.argv[1], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=d.timezone.utc); time.sleep(max(0, (t - d.datetime.now(d.timezone.utc)).total_seconds() + 1))" "$1"; }

# The gallery opens an auction: bids close in 20 seconds, reveals in 35, the highest bid wins, and nothing under INR 5,000 (the reserve) is accepted.
ledgdex init gallery --name "Old Maps Gallery" --key gallery
CLOSE=$(at 20); REVEAL_UNTIL=$(at 35)
cat > auction.json <<JSON
{"item": {"title": "Map of Bombay, 1893", "text": "Hand-coloured, framed."},
 "currency": "INR", "close": "$CLOSE", "reveal_until": "$REVEAL_UNTIL", "best": "highest", "reserve": 500000}
JSON
AUCTION=$(ledgdex auction gallery auction.json | awk '{print $NF}')

# Two people bid. Each amount stays secret on the bidder's computer; only a sealed fingerprint of it is sent.
ledgdex init asha --name "Asha" --key asha
ledgdex init ravi --name "Ravi" --key ravi
ledgdex bid asha gallery "$AUCTION" --amount 650000 --output asha-bid.json
ledgdex bid ravi gallery "$AUCTION" --amount 720000 --output ravi-bid.json
ledgdex record gallery --from asha --from ravi

# After bidding closes, each bidder reveals their amount.
wait_until "$CLOSE"
ledgdex reveal asha gallery "$AUCTION" --output asha-reveal.json
ledgdex reveal ravi gallery "$AUCTION" --output ravi-reveal.json
ledgdex record gallery --from asha --from ravi

# When the reveal time is over, the gallery adds a note to close the auction. Anyone can now see the winner: Ravi, at INR 7,200.
wait_until "$REVEAL_UNTIL"
ledgdex note gallery "$AUCTION" "Bidding is over: the result is in the state."
ledgdex state gallery | python3 -c '
import json, sys
a = list(json.load(sys.stdin)["auctions"].values())[0]
print(json.dumps({"winner": a["winner"], "amount": a["amount"], "status": a["status"]}, indent=1))'

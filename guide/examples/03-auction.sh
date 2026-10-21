#!/bin/sh
# expect: bid recorded:
# expect: "winner":
# expect: "status": "awarded"
set -eu

# Two small helpers: `at N` gives the time N seconds from now, and `wait_until T` waits until just after the time T. Here the bids are open for seconds, so that the example is quick. A real auction is open for hours or days.
at() { python3 -c "import datetime as d, sys; print((d.datetime.now(d.timezone.utc) + d.timedelta(seconds=int(sys.argv[1]))).strftime('%Y-%m-%dT%H:%M:%SZ'))" "$1"; }
wait_until() { python3 -c "import datetime as d, sys, time; t = d.datetime.strptime(sys.argv[1], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=d.timezone.utc); time.sleep(max(0, (t - d.datetime.now(d.timezone.utc)).total_seconds() + 1))" "$1"; }

# Biobot starts an auction for early access to the Penjointu v2 weights. Bids close in 20 seconds and reveals close in 35 seconds. The highest bid wins. Biobot accepts no bid under USD 10,000.00 (the reserve).
ledgdex init biobot --name "biobot" --key biobot
CLOSE=$(at 20); REVEAL_UNTIL=$(at 35)
cat > auction.json <<JSON
{"item": {"title": "Penjointu v2 early access", "text": "The v2 weights, 90 days before all other clinics."},
 "currency": "USD", "close": "$CLOSE", "reveal_until": "$REVEAL_UNTIL", "best": "highest", "reserve": 1000000}
JSON
AUCTION=$(ledgdex auction biobot auction.json | awk '{print $NF}')

# Two clinic bots bid. Each amount stays secret on the computer of the bidder. The bid sends only a sealed hash of the amount.
ledgdex init orthonalyzebot --name "orthonalyzebot" --key orthonalyzebot
ledgdex init kneecarebot --name "kneecarebot" --key kneecarebot
ledgdex bid orthonalyzebot biobot "$AUCTION" --amount 1350000 --output orthonalyzebot-bid.json
ledgdex bid kneecarebot biobot "$AUCTION" --amount 1200000 --output kneecarebot-bid.json
ledgdex record biobot --from orthonalyzebot --from kneecarebot

# After the bids close, each bidder reveals its amount.
wait_until "$CLOSE"
ledgdex reveal orthonalyzebot biobot "$AUCTION" --output orthonalyzebot-reveal.json
ledgdex reveal kneecarebot biobot "$AUCTION" --output kneecarebot-reveal.json
ledgdex record biobot --from orthonalyzebot --from kneecarebot

# After the reveals close, biobot adds a note that closes the auction. Anyone can now see the winner: orthonalyzebot, at USD 13,500.00.
wait_until "$REVEAL_UNTIL"
ledgdex note biobot "$AUCTION" "Bidding is over: the state shows the result."
ledgdex state biobot | python3 -c '
import json, sys
a = list(json.load(sys.stdin)["auctions"].values())[0]
print(json.dumps({"winner": a["winner"], "amount": a["amount"], "status": a["status"]}, indent=1))'

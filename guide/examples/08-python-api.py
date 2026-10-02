"""The Python API without a dex: make a ledger in memory, sign messages, record them, verify, and read the state.
Everything a dex does is built on these calls (ledgdex.core, ledgdex.state, ledgdex.canon)."""
# expect: whole True
# expect: 'status': 'accepted'
# expect: broken at 2
import json
from ledgdex.canon import canon, hash_
from ledgdex.core import Ledger, message, new_ledger, new_secret, public
from ledgdex.state import state

seller, buyer = new_secret(), new_secret()           # 32-byte Ed25519 secrets: keep them out of any dex
print('seller key', public(seller))

# A ledger is a header line and signed entries; new_ledger writes the header and the "open" entry.
led = new_ledger(seller, 'Mango Farm', 'Alphonso mangoes', 'https://farm.example')

# The seller signs an offer and records it in its own ledger.
offer = message(seller, 'offer', {
    'item': {'title': 'Alphonso mangoes', 'text': 'One dozen', 'media': []}, 'quantity': 3, 'unit': 'dozen',
    'currency': 'INR', 'price': 120000, 'allow': 'any', 'pay': [{'method': 'upi', 'to': 'farm@bank'}],
    'arbiter': {'key': public(seller), 'url': ''}, 'terms': ''})
offer_id = led.append(led.next_entry(seller, offer))

# The buyer signs a claim naming the offer by id and by hash: the offer cannot change under the claim.
claim = message(buyer, 'claim', {'offer': offer_id, 'offer_hash': hash_(offer), 'quantity': 2, 'price': 120000})
claim_id = led.append(led.next_entry(seller, claim))   # the seller records it: that entry is the buyer's receipt

# Anyone can verify the bytes and replay them into the same state, in Python or in JavaScript.
again = Ledger(led.data, cache=False)
print('whole', again.whole, 'entries', len(again.entries), 'id', again.id[:19])
st = state(again)
print(st['claims'][claim_id], st['offers'][offer_id]['remaining'], 'left')

# Change one byte of the recorded claim, and verification breaks exactly there.
data = bytearray(led.data)
data[data.index(b'"quantity":2') + 11] = ord('3')
tampered = Ledger(bytes(data), cache=False)
print('broken at', tampered.broken_at, '-', tampered.error)

# Canonical JSON: the exact bytes that are hashed and signed (sorted keys, no spaces, UTF-8).
print(canon({'b': 1, 'a': 'é'}).decode())

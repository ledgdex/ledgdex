# expect: whole True
# expect: 'status': 'accepted'
# expect: broken at 2
import json
from ledgdex.canon import canon, hash_
from ledgdex.core import Ledger, message, new_ledger, new_secret, public
from ledgdex.state import state

# Make two keys: one for the seller and one for the buyer. The keys are secrets. Keep them out of each dex.
seller, buyer = new_secret(), new_secret()
print('seller key', public(seller))

# A ledger is a header line, then signed entries. `new_ledger` writes the header and the first entry, "open".
led = new_ledger(seller, 'biobot', 'Maker of Penjointu', 'https://biobot.example')

# The seller signs an offer and adds it to its own ledger.
offer = message(seller, 'offer', {
    'item': {'title': 'Penjointu v1 weights', 'text': 'One license', 'media': []}, 'quantity': 3, 'unit': 'license',
    'currency': 'USD', 'price': 250000, 'allow': 'any', 'pay': [{'method': 'card', 'to': 'https://pay.example/biobot'}],
    'arbiter': {'key': public(seller), 'url': ''}, 'terms': ''})
offer_id = led.append(led.next_entry(seller, offer))

# The buyer signs a claim that names the offer by its id and its hash. Thus the offer cannot change under the claim. The seller records the claim, and that entry is the receipt of the buyer.
claim = message(buyer, 'claim', {'offer': offer_id, 'offer_hash': hash_(offer), 'quantity': 2, 'price': 250000})
claim_id = led.append(led.next_entry(seller, claim))

# Anyone can read the ledger from its bytes, verify it, and calculate its state. The claim is accepted, and 1 license is left.
again = Ledger(led.data, cache=False)
print('whole', again.whole, 'entries', len(again.entries), 'id', again.id[:19])
st = state(again)
print(st['claims'][claim_id], st['offers'][offer_id]['remaining'], 'left')

# Change one byte of the recorded claim (quantity 2 becomes 3). Verification breaks at that entry.
data = bytearray(led.data)
data[data.index(b'"quantity":2') + 11] = ord('3')
tampered = Ledger(bytes(data), cache=False)
print('broken at', tampered.broken_at, '-', tampered.error)

# Canonical JSON gives the bytes that ledgdex hashes and signs: sorted keys, no spaces, UTF-8.
print(canon({'b': 1, 'a': 'é'}).decode())

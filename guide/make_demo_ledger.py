"""Make the docs' own ledger (guide/dex/ledgdex.jsonl), once. The docs are a ledgdex: a dex with a ledger in it, so
ledgdex renders pages from this ledger next to the written docs, as it does in every ledgdex.

The ledger is signed with a key made here and never saved: once this script ends, nothing can be added to it, and
nobody can sell or buy through it (its offer and auction allow no one). It is a demonstration you can verify:
    ledgdex verify https://matrixdex.github.io/ledgdex/docs
Run from the repository root:  python guide/make_demo_ledger.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'py'))
from ledgdex.core import message, new_ledger, new_secret, public  # noqa: E402

PATH = os.path.join(os.path.dirname(__file__), 'dex', 'ledgdex.jsonl')
T = '2026-10-02T09:00:{:02d}Z'

if os.path.exists(PATH):
    sys.exit(PATH + ' exists: the docs ledger is made once')
key = new_secret()                      # never written anywhere
led = new_ledger(key, 'Ledgdex Docs', 'The ledger of the ledgdex docs: a demonstration. Its key was destroyed after '
                 'signing, so nothing can be added to it, and nobody may buy from it.',
                 'https://matrixdex.github.io/ledgdex/docs', at=T.format(0))
offer = message(key, 'offer', {
    'item': {'title': 'Example offer: Alphonso mangoes',
             'text': 'A demonstration of the page ledgdex makes for an offer. Nobody may buy it.', 'media': []},
    'quantity': 12, 'unit': 'dozen', 'currency': 'INR', 'price': 120000, 'allow': [],
    'pay': [{'method': 'upi', 'to': 'example@bank'}], 'arbiter': {'key': public(key), 'url': ''},
    'terms': 'An example in the ledgdex docs: "allow" is an empty list, so every claim is refused.'}, at=T.format(1))
oid = led.append(led.next_entry(key, offer, at=T.format(1)))
auction = message(key, 'auction', {
    'item': {'title': 'Example auction: Map of Bombay, 1893',
             'text': 'A demonstration of the page ledgdex makes for a sealed-bid auction. Nobody may bid.',
             'media': []},
    'currency': 'INR', 'close': '2026-10-09T09:00:00Z', 'reveal_until': '2026-10-10T09:00:00Z', 'best': 'highest',
    'reserve': 500000, 'allow': [], 'arbiter': {'key': public(key), 'url': ''},
    'terms': 'An example in the ledgdex docs.'}, at=T.format(2))
led.append(led.next_entry(key, auction, at=T.format(2)))
led.append(led.next_entry(key, message(key, 'note', {'ref': oid, 'text': 'This ledger was signed once, for the docs.'},
                                       at=T.format(3)), at=T.format(3)))
os.makedirs(os.path.dirname(PATH), exist_ok=True)
with open(PATH, 'wb') as f:
    f.write(led.data)
print('docs ledger', led.id, 'owner', led.owner, '(key discarded)')

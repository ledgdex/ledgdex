"""Bots that make a market, with no person in the loop. A seller bot sells software licences; two buyer bots find the
cheapest offer through an index, claim, pay, and confirm once the licence arrives. Each bot only reads ledgers and
signs messages, in rounds, as an agent would on a timer. On the web each dex is published after each round, and the
addresses are https:// URLs instead of folders."""
# expect: round 1
# expect: closed
# expect: all deals closed: True
import contextlib, io, json
from ledgdex.cli import main


def ledgdex(*args):
    """Run one ledgdex command in this process and return what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


def state(src):
    return json.loads(ledgdex('state', src))


class SellerBot:
    """Collects claims and payments from buyers' dexes, delivers once paid, and records the money as received."""

    def __init__(self, dex, buyers):
        self.dex, self.buyers = dex, buyers

    def round(self):
        ledgdex('record', self.dex, *[x for b in self.buyers for x in ('--from', b)])
        for cid, c in state(self.dex)['claims'].items():
            if c['status'] == 'accepted' and 'paid' in c and not c.get('delivered'):
                # a real bot checks its bank or payment API for c['paid']['ref'] before this
                ledgdex('received', self.dex, cid, c['price'] * c['quantity'])
                ledgdex('delivered', self.dex, cid, '--note', 'licence key LIC-' + cid[7:15].upper())


class BuyerBot:
    """Buys one unit of a title, at the lowest price on the index, within a budget."""

    def __init__(self, dex, index, title, budget):
        self.dex, self.index, self.title, self.budget = dex, index, title, budget
        self.me = state(dex)['owner']
        self.seller = None

    def round(self):
        if self.seller is None:          # find the cheapest open offer for the title on the index
            found = json.loads(ledgdex('discover', self.index, '--offers', '--json'))
            offers = [(o['price'], listed['url'], o['id']) for listed in found for o in listed['offers']
                      if o['title'] == self.title and o['price'] <= self.budget and o['remaining'] > 0]
            if offers:
                price, self.seller, oid = min(offers)
                ledgdex('claim', self.dex, self.seller, oid, '--output', self.dex + '-claim.json')
            return
        ledgdex('receipt', self.dex, self.seller)    # keep the seller's records of my messages
        for cid, c in state(self.seller)['claims'].items():
            if c['buyer'] != self.me:
                continue
            if c['status'] == 'accepted' and 'paid' not in c:
                ledgdex('pay', self.dex, self.seller, cid, '--method', 'card', '--ref', 'PAY-' + cid[7:13],
                        '--output', self.dex + '-paid.json')
            elif c.get('delivered') and not c.get('confirmed'):
                ledgdex('confirm', self.dex, self.seller, cid, '--output', self.dex + '-confirmed.json')


# The market: an index listing two software shops, and two buyers.
ledgdex('init', 'index', '--name', 'Software Market', '--key', 'index')
for shop, price in (('acme', 4900), ('globex', 3900)):
    ledgdex('init', shop, '--name', shop.title() + ' Software', '--key', shop)
    with open(shop + '.json', 'w') as f:
        json.dump({'item': {'title': 'Photo editor licence'}, 'quantity': 100, 'unit': 'licence',
                   'currency': 'USD', 'price': price}, f)          # USD 39.00 at globex
    ledgdex('offer', shop, shop + '.json')
    ledgdex('list', 'index', shop, '--note', 'software')
for buyer in ('alice', 'bob'):
    ledgdex('init', buyer, '--name', buyer.title(), '--key', buyer)

sellers = [SellerBot('acme', ['alice', 'bob']), SellerBot('globex', ['alice', 'bob'])]
buyers = [BuyerBot('alice', 'index', 'Photo editor licence', 5000), BuyerBot('bob', 'index', 'Photo editor licence', 5000)]
for n in range(1, 5):
    for bot in buyers + sellers:
        bot.round()
    claims = state('globex')['claims']
    print('round', n, sorted(c['status'] + (' delivered' if c.get('delivered') else '') for c in claims.values()))
print('all deals closed:', all(c['status'] == 'closed' for c in state('globex')['claims'].values()) and
      len(state('globex')['claims']) == 2)

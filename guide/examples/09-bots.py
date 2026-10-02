# expect: round 1
# expect: closed
# expect: all deals closed: True
import contextlib, io, json
from ledgdex.cli import main

# `ledgdex(...)` runs one ledgdex command in this program and returns what it printed; `state(...)` reads a ledgdex's state.
def ledgdex(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


def state(src):
    return json.loads(ledgdex('state', src))


# A seller bot, each round, collects orders and payments from its buyers' dexes. For every accepted order that is paid, it records the money as received and delivers a licence key. A real bot would first look up the payment reference with its bank.
class SellerBot:
    def __init__(self, dex, buyers):
        self.dex, self.buyers = dex, buyers

    def round(self):
        ledgdex('record', self.dex, *[x for b in self.buyers for x in ('--from', b)])
        for cid, c in state(self.dex)['claims'].items():
            if c['status'] == 'accepted' and 'paid' in c and not c.get('delivered'):
                ledgdex('received', self.dex, cid, c['price'] * c['quantity'])
                ledgdex('delivered', self.dex, cid, '--note', 'licence key LIC-' + cid[7:15].upper())


# A buyer bot wants one licence within a budget. In its first round it finds the cheapest open offer on the index and orders it. After that, each round it keeps the seller's receipts, pays once the order is accepted, and confirms once the licence is delivered.
class BuyerBot:
    def __init__(self, dex, index, title, budget):
        self.dex, self.index, self.title, self.budget = dex, index, title, budget
        self.me = state(dex)['owner']
        self.seller = None

    def round(self):
        if self.seller is None:
            found = json.loads(ledgdex('discover', self.index, '--offers', '--json'))
            offers = [(o['price'], listed['url'], o['id']) for listed in found for o in listed['offers']
                      if o['title'] == self.title and o['price'] <= self.budget and o['remaining'] > 0]
            if offers:
                price, self.seller, oid = min(offers)
                ledgdex('claim', self.dex, self.seller, oid, '--output', self.dex + '-claim.json')
            return
        ledgdex('receipt', self.dex, self.seller)
        for cid, c in state(self.seller)['claims'].items():
            if c['buyer'] != self.me:
                continue
            if c['status'] == 'accepted' and 'paid' not in c:
                ledgdex('pay', self.dex, self.seller, cid, '--method', 'card', '--ref', 'PAY-' + cid[7:13],
                        '--output', self.dex + '-paid.json')
            elif c.get('delivered') and not c.get('confirmed'):
                ledgdex('confirm', self.dex, self.seller, cid, '--output', self.dex + '-confirmed.json')


# The market: an index listing two software shops, Acme at USD 49.00 and Globex at USD 39.00, and two buyers.
ledgdex('init', 'index', '--name', 'Software Market', '--key', 'index')
for shop, price in (('acme', 4900), ('globex', 3900)):
    ledgdex('init', shop, '--name', shop.title() + ' Software', '--key', shop)
    with open(shop + '.json', 'w') as f:
        json.dump({'item': {'title': 'Photo editor licence'}, 'quantity': 100, 'unit': 'licence',
                   'currency': 'USD', 'price': price}, f)
    ledgdex('offer', shop, shop + '.json')
    ledgdex('list', 'index', shop, '--note', 'software')
for buyer in ('alice', 'bob'):
    ledgdex('init', buyer, '--name', buyer.title(), '--key', buyer)

# Every bot takes a turn each round, as it would on a timer. Online, each bot would also publish its dex after its turn. After four rounds both buyers have bought from Globex, the cheaper shop, and both deals are closed.
sellers = [SellerBot('acme', ['alice', 'bob']), SellerBot('globex', ['alice', 'bob'])]
buyers = [BuyerBot('alice', 'index', 'Photo editor licence', 5000), BuyerBot('bob', 'index', 'Photo editor licence', 5000)]
for n in range(1, 5):
    for bot in buyers + sellers:
        bot.round()
    claims = state('globex')['claims']
    print('round', n, sorted(c['status'] + (' delivered' if c.get('delivered') else '') for c in claims.values()))
print('all deals closed:', all(c['status'] == 'closed' for c in state('globex')['claims'].values()) and
      len(state('globex')['claims']) == 2)

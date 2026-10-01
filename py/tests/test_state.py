import unittest
from helpers import Book, BUYER, OTHER, SELLER, t
from ledgdex.core import public
from ledgdex.state import state


class Claims(unittest.TestCase):
    def reason(self, b, cid):
        c = state(b.led)['claims'][cid]
        return c.get('reason', c['status'])

    def test_rejections_in_order(self):
        b = Book()
        oid, oh = b.offer()
        self.assertEqual(self.reason(b, b.claim('sha256:' + '0' * 64, oh)), 'unknown_offer')
        self.assertEqual(self.reason(b, b.claim(oid, 'sha256:' + '0' * 64)), 'offer_changed')
        self.assertEqual(self.reason(b, b.claim(oid, oh, quantity=0)), 'bad_quantity')
        self.assertEqual(self.reason(b, b.claim(oid, oh, quantity=3)), 'bad_quantity')
        self.assertEqual(self.reason(b, b.claim(oid, oh, price=1)), 'price_mismatch')
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'accepted')
        b.own('withdraw', {'offer': oid})
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'withdrawn')
        oid2, oh2 = b.offer(expires=t(b.minute + 3))
        self.assertEqual(self.reason(b, b.claim(oid2, oh2)), 'accepted')
        self.assertEqual(self.reason(b, b.claim(oid2, oh2)), 'expired')

    def test_order_offer_changed_before_withdrawn(self):
        b = Book()
        oid, oh = b.offer()
        b.own('withdraw', {'offer': oid})
        self.assertEqual(self.reason(b, b.claim(oid, 'sha256:' + '0' * 64)), 'offer_changed')

    def test_allow(self):
        b = Book()
        oid, oh = b.offer(allow='admitted')
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'not_allowed')
        b.own('admit', {'key': public(BUYER), 'name': 'Asha', 'note': ''})
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'accepted')
        b.own('revoke', {'key': public(BUYER), 'reason': ''})
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'not_allowed')
        oid, oh = b.offer(allow=[public(OTHER)])
        self.assertEqual(self.reason(b, b.claim(oid, oh)), 'not_allowed')
        self.assertEqual(self.reason(b, b.claim(oid, oh, secret=OTHER)), 'accepted')

    def test_last_unit_race(self):
        b = Book()
        oid, oh = b.offer(quantity=1)
        first, second = b.claim(oid, oh), b.claim(oid, oh, secret=OTHER)
        st = state(b.led)
        self.assertEqual(st['claims'][first]['status'], 'accepted')
        self.assertEqual(st['claims'][second]['reason'], 'bad_quantity')
        self.assertEqual(st['offers'][oid], {'title': 'Mangoes', 'remaining': 0, 'status': 'sold'})

    def test_no_self_buying(self):
        b = Book()
        oid, oh = b.offer(allow=[public(SELLER)])
        self.assertEqual(self.reason(b, b.claim(oid, oh, secret=SELLER)), 'self_claim')
        self.assertEqual(state(b.led)['offers'][oid]['remaining'], 2)

    def test_price_comes_from_the_signed_offer(self):
        b = Book()
        oid, oh = b.offer(price=500)
        self.assertEqual(self.reason(b, b.claim(oid, oh, price=120000)), 'price_mismatch')
        self.assertEqual(self.reason(b, b.claim(oid, oh, price=500)), 'accepted')


class Lifecycle(unittest.TestCase):
    def test_full_trade_closes(self):
        b = Book()
        oid, oh = b.offer()
        cid = b.claim(oid, oh)
        b.from_(BUYER, 'paid', {'claim': cid, 'method': 'upi', 'ref': 'r'})
        b.own('received', {'claim': cid, 'amount': 120000})
        b.from_(BUYER, 'confirmed', {'claim': cid})        # before delivery: ignored
        b.own('delivered', {'claim': cid, 'note': ''})
        b.from_(OTHER, 'confirmed', {'claim': cid})        # not the buyer: ignored
        b.from_(OTHER, 'paid', {'claim': cid, 'method': 'x', 'ref': ''})
        self.assertEqual(state(b.led)['claims'][cid]['status'], 'accepted')
        b.from_(BUYER, 'confirmed', {'claim': cid})
        st = state(b.led)
        c = st['claims'][cid]
        self.assertEqual(c['status'], 'closed')
        self.assertEqual(c['paid'], {'method': 'upi', 'ref': 'r'})
        self.assertEqual([i['reason'] for i in st['ignored']], ['not_delivered', 'not_buyer', 'not_buyer'])

    def test_actions_on_rejected_claims_are_ignored(self):
        b = Book()
        oid, oh = b.offer()
        cid = b.claim(oid, oh, price=1)
        b.own('delivered', {'claim': cid, 'note': ''})
        b.own('received', {'claim': 'sha256:' + '9' * 64, 'amount': 1})
        b.own('withdraw', {'offer': 'sha256:' + '9' * 64})
        self.assertEqual([i['reason'] for i in state(b.led)['ignored']],
                         ['claim_not_accepted', 'unknown_claim', 'offer_not_open'])

    def test_output_shape(self):
        b = Book()
        st = state(b.led)
        self.assertEqual(set(st), {'ledger', 'owner', 'devices', 'head', 'broken_at', 'admitted', 'offers', 'claims',
                                   'auctions', 'disputes', 'listings', 'recoveries', 'ignored'})
        self.assertIsNone(st['broken_at'])
        self.assertEqual(st['owner'], public(SELLER))


if __name__ == '__main__':
    unittest.main()

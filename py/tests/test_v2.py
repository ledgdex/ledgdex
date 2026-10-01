"""Milestones 7-9 and indexes: disputes, auctions, device keys, rotation, recovery, the root, listings."""
import unittest
from helpers import Book, BUYER, OTHER, SELLER, offer_body, t
from ledgdex.canon import hash_
from ledgdex.core import Ledger, Invalid, message, public
from ledgdex.state import state

PHONE = bytes(range(10, 42))
NEWKEY = bytes(range(20, 52))
ROOTKEY = bytes(range(30, 62))
NONCE = 'ab' * 16


def auction_body(**kw):
    b = {'item': {'title': 'Old map', 'text': '', 'media': []}, 'currency': 'INR', 'close': t(30),
         'reveal_until': t(60), 'best': 'highest', 'reserve': 100, 'allow': 'any',
         'arbiter': {'key': public(OTHER), 'url': ''}, 'terms': ''}
    b.update(kw)
    return b


class Keys(unittest.TestCase):
    def test_device_appends_and_signs_offers(self):
        b = Book()
        b.own('device', {'key': public(PHONE), 'name': 'phone'})
        m = message(PHONE, 'offer', offer_body(), at=b.tick())
        b.led.append(b.led.next_entry(PHONE, m, at=t(b.minute)))   # entry signed by the phone too
        led = Ledger(b.led.data, cache=False)
        self.assertTrue(led.whole)
        self.assertEqual(state(led)['devices'], [public(PHONE)])

    def test_device_cannot_do_owner_only(self):
        b = Book()
        b.own('device', {'key': public(PHONE), 'name': 'phone'})
        for type_, body in (('device', {'key': public(OTHER), 'name': 'x'}), ('rotate', {'key': public(OTHER)}),
                            ('device_revoke', {'key': public(PHONE), 'reason': ''})):
            m = message(PHONE, type_, body, at=b.tick())
            self.assertRaises(Invalid, lambda: b.led.append(b.led.next_entry(PHONE, m, at=t(b.minute))))

    def test_revoked_device_breaks_later_but_not_earlier(self):
        b = Book()
        b.own('device', {'key': public(PHONE), 'name': 'phone'})
        m = message(PHONE, 'note', {'ref': b.led.ids[0], 'text': 'before'}, at=b.tick())
        b.led.append(b.led.next_entry(PHONE, m, at=t(b.minute)))
        b.own('device_revoke', {'key': public(PHONE), 'reason': 'lost'})
        self.assertTrue(Ledger(b.led.data, cache=False).whole)
        m = message(PHONE, 'note', {'ref': b.led.ids[0], 'text': 'after'}, at=b.tick())
        self.assertRaises(Invalid, b.led.next_entry, PHONE, m, t(b.minute))
        # forced in anyway: the ledger breaks at that entry
        e = {'seq': len(b.led.entries), 'prev': b.led.ids[-1], 'time': t(b.minute), 'msg': m}
        from ledgdex.core import sign
        e['sig'] = sign(PHONE, e)
        from ledgdex.canon import canon
        led = Ledger(b.led.data + canon(e) + b'\n', cache=False)
        self.assertEqual(led.broken_at, len(b.led.entries))

    def test_a_replayed_device_message_does_not_bring_it_back(self):
        b = Book()
        dev = message(SELLER, 'device', {'key': public(PHONE), 'name': 'phone'}, at=b.tick())
        b.rec(dev)
        b.own('device_revoke', {'key': public(PHONE), 'reason': 'lost'})
        b.rec(dev)
        led = Ledger(b.led.data, cache=False)
        self.assertEqual((led.devices, state(led)['devices']), ([], []))
        m = message(PHONE, 'note', {'ref': b.led.ids[0], 'text': 'still here?'}, at=b.tick())
        self.assertRaises(Invalid, b.led.next_entry, PHONE, m, t(b.minute))

    def test_rotate(self):
        b = Book()
        b.own('rotate', {'key': public(NEWKEY)})
        self.assertRaises(Invalid, b.own, 'note', {'ref': b.led.ids[0], 'text': 'old key'})
        b.secret = NEWKEY
        b.own('note', {'ref': b.led.ids[0], 'text': 'new key'})
        led = Ledger(b.led.data, cache=False)
        self.assertTrue(led.whole)
        self.assertEqual((led.owner, led.header['owner']), (public(NEWKEY), public(SELLER)))

    def test_receipt_after_rotation_and_device(self):
        seller = Book()
        oid, oh = seller.offer()
        seller.own('rotate', {'key': public(NEWKEY)})
        seller.secret = NEWKEY
        seller.own('device', {'key': public(PHONE), 'name': 'phone'})
        m = message(BUYER, 'claim', {'offer': oid, 'offer_hash': oh, 'quantity': 1, 'price': 120000}, at=seller.tick())
        seller.led.append(seller.led.next_entry(PHONE, m, at=t(seller.minute)))   # recorded from the phone
        e = seller.led.entries[-1]
        keys = [x for x in seller.led.entries if x['msg']['type'] in ('rotate', 'device')]
        body = {'ledger': seller.led.id, 'url': 'x', 'header': seller.led.header, 'entry': e}
        self.assertRaises(Invalid, message, BUYER, 'receipt', body)        # the header key did not sign it
        message(BUYER, 'receipt', dict(body, keys=keys))                    # the key chain shows who did
        self.assertRaises(Invalid, message, BUYER, 'receipt', dict(body, keys=keys[1:]))


class Recovery(unittest.TestCase):
    def setUp(self):
        self.root = Book(ROOTKEY, 'Root')
        self.b = Book()
        self.b.own('note', {'ref': self.b.led.ids[0], 'text': 'before the loss'})

    def recovered(self, entry_id):
        m = message(NEWKEY, 'recovered', {'root': self.root.led.id, 'entry': entry_id}, at=self.b.tick())
        return self.b.led.next_entry(NEWKEY, m, at=t(self.b.minute))

    def test_recovery_with_the_root(self):
        rid = self.root.own('recover', {'ledger': self.b.led.id, 'key': public(NEWKEY)})
        self.b.led.root = Ledger(self.root.led.data)
        self.b.led.append(self.recovered(rid))
        self.b.secret = NEWKEY
        self.b.own('note', {'ref': self.b.led.ids[0], 'text': 'after'})
        led = Ledger(self.b.led.data, cache=False, root=Ledger(self.root.led.data))
        self.assertTrue(led.whole)
        self.assertEqual(led.owner, public(NEWKEY))
        no_root = Ledger(self.b.led.data, cache=False)
        self.assertEqual(no_root.broken_at, 2)
        self.assertIn('root', no_root.error)
        self.assertIn(self.b.led.id, state(Ledger(self.root.led.data))['recoveries'])

    def test_recovery_needs_a_matching_root_entry(self):
        rid = self.root.own('recover', {'ledger': self.b.led.id, 'key': public(OTHER)})   # another key
        self.b.led.root = Ledger(self.root.led.data)
        self.assertRaises(Invalid, self.b.led.append, self.recovered(rid))


class Disputes(unittest.TestCase):
    def setUp(self):
        self.b = Book()
        self.oid, oh = self.b.offer(arbiter={'key': public(OTHER), 'url': ''})
        self.cid = self.b.claim(self.oid, oh)

    def test_dispute_and_ruling(self):
        did = self.b.from_(BUYER, 'dispute', {'claim': self.cid, 'text': 'never arrived', 'evidence': []})
        st = state(self.b.led)
        self.assertEqual(st['claims'][self.cid]['status'], 'disputed')
        self.b.from_(SELLER, 'ruling', {'dispute': did, 'outcome': 'release', 'text': ''})   # not the arbiter
        self.b.from_(OTHER, 'ruling', {'dispute': did, 'outcome': 'refund', 'text': 'refund it'})
        self.b.from_(OTHER, 'ruling', {'dispute': did, 'outcome': 'release', 'text': 'again'})
        st = state(self.b.led)
        self.assertEqual(st['claims'][self.cid]['status'], 'refunded')
        self.assertEqual(st['disputes'][did]['claim'], self.cid)
        self.assertEqual([i['reason'] for i in st['ignored']], ['not_arbiter', 'already_ruled'])

    def test_only_parties_dispute(self):
        self.b.from_(OTHER, 'dispute', {'claim': self.cid, 'text': '', 'evidence': []})
        self.b.own('dispute', {'claim': self.cid, 'text': 'buyer never paid', 'evidence': []})   # the seller may
        st = state(self.b.led)
        self.assertEqual(st['ignored'][0]['reason'], 'not_party')
        self.assertEqual(st['claims'][self.cid]['status'], 'disputed')


class Auctions(unittest.TestCase):
    def bid(self, b, aid, secret, amount, nonce=NONCE):
        return b.from_(secret, 'bid', {'auction': aid, 'commit': hash_({'amount': amount, 'nonce': nonce})})

    def reveal(self, b, aid, secret, amount, nonce=NONCE):
        return b.from_(secret, 'reveal', {'auction': aid, 'amount': amount, 'nonce': nonce})

    def test_sealed_bid(self):
        b = Book()
        aid = b.own('auction', auction_body())
        self.bid(b, aid, BUYER, 500)
        self.bid(b, aid, OTHER, 700)
        self.bid(b, aid, BUYER, 900)                        # one bid per key
        self.assertEqual(state(b.led)['auctions'][aid], {'status': 'open', 'bids': 2})
        b.minute = 30
        self.reveal(b, aid, BUYER, 500)
        self.reveal(b, aid, OTHER, 700, nonce='cd' * 16)    # wrong nonce: not counted
        self.assertEqual(state(b.led)['auctions'][aid]['status'], 'revealing')
        b.minute = 60
        self.reveal(b, aid, OTHER, 700)                     # too late
        st = state(b.led)
        self.assertEqual(st['auctions'][aid], {'status': 'awarded', 'bids': 2, 'winner': public(BUYER), 'amount': 500})
        self.assertEqual([i['reason'] for i in st['ignored']], ['duplicate_bid', 'bad_reveal', 'late_reveal'])
        # payment follows 5.4 with the auction id in place of the claim id
        b.from_(BUYER, 'paid', {'claim': aid, 'method': 'upi', 'ref': 'r'})
        b.own('received', {'claim': aid, 'amount': 500})
        b.own('delivered', {'claim': aid, 'note': ''})
        b.from_(BUYER, 'confirmed', {'claim': aid})
        self.assertEqual(state(b.led)['auctions'][aid]['status'], 'closed')

    def test_lowest_reserve_ties_and_late_bids(self):
        b = Book()
        aid = b.own('auction', auction_body(best='lowest', reserve=600))
        self.bid(b, aid, BUYER, 400)
        self.bid(b, aid, OTHER, 400)
        b.minute = 30
        self.bid(b, aid, bytes(range(3, 35)), 1)            # after close
        self.reveal(b, aid, OTHER, 400)
        self.reveal(b, aid, BUYER, 400)
        st = state(b.led, now=t(61))
        self.assertEqual(st['auctions'][aid]['winner'], public(BUYER))   # tie: the earlier bid
        self.assertEqual(st['ignored'][0]['reason'], 'late_bid')

    def test_reserve_not_met(self):
        b = Book()
        aid = b.own('auction', auction_body(reserve=1000))
        self.bid(b, aid, BUYER, 500)
        b.minute = 30
        self.reveal(b, aid, BUYER, 500)
        self.assertEqual(state(b.led, now=t(61))['auctions'][aid]['status'], 'no_winner')

    def test_bad_auction_body(self):
        self.assertRaises(Invalid, message, SELLER, 'auction', auction_body(reveal_until=t(30)))
        self.assertRaises(Invalid, message, BUYER, 'reveal', {'auction': 'sha256:' + '0' * 64, 'amount': 1,
                                                               'nonce': 'short'})


class IndexAndRoot(unittest.TestCase):
    def test_listings(self):
        idx = Book(OTHER, 'Index')
        farm = Book()
        idx.own('list', {'ledger': farm.led.id, 'url': 'https://farm.example', 'owner': public(SELLER), 'note': ''})
        idx.own('delist', {'ledger': 'sha256:' + '1' * 64, 'reason': ''})
        st = state(idx.led)
        self.assertEqual(list(st['listings']), [farm.led.id])
        self.assertEqual(st['ignored'][0]['reason'], 'not_listed')
        idx.own('delist', {'ledger': farm.led.id, 'reason': 'gone'})
        self.assertEqual(state(idx.led)['listings'], {})

    def test_admitted_in_seller_and_root(self):
        root = Book(ROOTKEY, 'Root')
        b = Book()
        oid, oh = b.offer(allow='admitted')
        b.own('admit', {'key': public(BUYER), 'name': '', 'note': ''})
        cid = b.claim(oid, oh)
        self.assertEqual(state(b.led)['claims'][cid]['status'], 'accepted')
        r = Ledger(root.led.data)
        self.assertEqual(state(b.led, root=r)['claims'][cid]['reason'], 'not_allowed')
        root.own('admit', {'key': public(BUYER), 'name': '', 'note': ''})
        self.assertEqual(state(b.led, root=Ledger(root.led.data))['claims'][cid]['status'], 'accepted')


if __name__ == '__main__':
    unittest.main()

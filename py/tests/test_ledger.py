import json, unittest
from helpers import Book, BUYER, OTHER, SELLER, offer_body, t
from ledgdex.canon import canon, parse
from ledgdex.core import Ledger, Invalid, message, public, sign, unsigned


def trade():
    b = Book()
    oid, oh = b.offer()
    cid = b.claim(oid, oh)
    b.from_(BUYER, 'paid', {'claim': cid, 'method': 'upi', 'ref': 'r1'})
    b.own('received', {'claim': cid, 'amount': 120000})
    return b


class Structure(unittest.TestCase):
    def test_whole(self):
        led = Ledger(trade().led.data)
        self.assertTrue(led.whole)
        self.assertEqual(len(led.entries), 5)
        self.assertEqual(led.head()['seq'], 4)

    def test_every_changed_byte_breaks(self):
        data = trade().led.data
        lines = data.split(b'\n')
        starts = [sum(len(x) + 1 for x in lines[:i]) for i in range(len(lines) - 1)]
        step = 37
        for pos in range(0, len(data) - 1, step):
            bad = bytearray(data)
            bad[pos] = ord('0') if bad[pos] != ord('0') else ord('1')
            led = Ledger(bytes(bad))
            line = max(i for i, s in enumerate(starts) if s <= pos)
            self.assertFalse(led.whole, pos)
            if line > 0:  # a changed entry breaks at its own seq or earlier
                self.assertLessEqual(led.broken_at, line - 1, pos)

    def test_reorder_and_drop(self):
        lines = trade().led.data.split(b'\n')[:-1]
        swapped = lines[:2] + [lines[3], lines[2]] + lines[4:]
        self.assertEqual(Ledger(b'\n'.join(swapped) + b'\n').broken_at, 1)
        dropped = lines[:2] + lines[3:]
        self.assertEqual(Ledger(b'\n'.join(dropped) + b'\n').broken_at, 1)

    def test_missing_newline(self):
        data = trade().led.data
        led = Ledger(data[:-1])
        self.assertEqual(led.broken_at, 4)
        self.assertEqual(len(led.entries), 4)

    def resign(self, b, n, change, secret=SELLER):
        """Rewrite entry n with change(entry) and a valid owner signature, to test the rules after the signature."""
        lines = b.led.data.split(b'\n')[:-1]
        e = parse(lines[n + 1])
        change(e)
        e['sig'] = sign(secret, unsigned(e))
        lines[n + 1] = canon(e)
        return Ledger(b'\n'.join(lines) + b'\n')

    def test_wrong_signer(self):
        led = self.resign(trade(), 2, lambda e: None, secret=OTHER)
        self.assertEqual(led.broken_at, 2)
        self.assertIn('signature', led.error)

    def test_time_backwards(self):
        led = self.resign(trade(), 2, lambda e: e.update(time='2026-10-01T08:00:00Z'))
        self.assertEqual(led.broken_at, 2)

    def test_recorded_too_early(self):
        b = Book()
        m = message(SELLER, 'note', {'ref': b.led.ids[0], 'text': 'x'}, at=t(30))
        self.assertRaises(Invalid, lambda: b.led.append(b.led.next_entry(SELLER, m, t(1))))
        led = self.resign(trade(), 1, lambda e: e.update(msg=m))
        self.assertEqual(led.broken_at, 1)
        self.assertIn('before it was signed', led.error)

    def test_owner_types_need_the_owner(self):
        b = Book()
        m = message(BUYER, 'offer', offer_body(), at=t(1))
        self.assertRaises(Invalid, lambda: b.led.append(b.led.next_entry(SELLER, m, t(1))))

    def test_open_only_first(self):
        b = Book()
        m = message(SELLER, 'open', {'about': '', 'dex': ''}, at=t(1))
        self.assertRaises(Invalid, lambda: b.led.append(b.led.next_entry(SELLER, m, t(1))))

    def test_only_the_owner_appends(self):
        b = Book()
        self.assertRaises(Invalid, b.led.next_entry, BUYER, message(BUYER, 'note', {'ref': b.led.ids[0], 'text': ''}))

    def test_media_is_linked_never_embedded(self):
        bad = offer_body(item={'title': 'x', 'text': '', 'media': [{'url': 'data:image/png;base64,AAAA',
                                                                      'hash': 'sha256:' + '0' * 64}]})
        self.assertRaises(Invalid, message, SELLER, 'offer', bad)
        bad['item']['media'][0] = {'url': 'https://x/y.png', 'hash': 'sha256:' + '0' * 64, 'data': 'AAAA'}
        self.assertRaises(Invalid, message, SELLER, 'offer', bad)
        bad['item']['media'][0].pop('data')
        message(SELLER, 'offer', bad)

    def test_unknown_type_and_extra_fields(self):
        self.assertRaises(Invalid, message, SELLER, 'auction', {})
        self.assertRaises(Invalid, message, SELLER, 'withdraw', {'offer': 'sha256:' + '0' * 64, 'why': 'x'})

    def test_forged_message_signature(self):
        m = message(BUYER, 'confirmed', {'claim': 'sha256:' + '1' * 64})
        m['body']['claim'] = 'sha256:' + '2' * 64
        b = Book()
        self.assertRaises(Invalid, lambda: b.led.append(b.led.next_entry(SELLER, m)))


class FoundByFuzzing(unittest.TestCase):
    """tests/fuzz.py found these: a crash on a non-string type, and true passing for 1."""

    def signed(self, change):
        b = Book()
        oid, _ = b.offer()
        e = json.loads(b.led.lines[1])
        change(e)
        e['msg']['sig'] = sign(SELLER, unsigned(e['msg']))
        e['sig'] = sign(SELLER, unsigned(e))
        return Ledger(b.led.header_line + b'\n' + b.led.lines[0] + b'\n' + canon(e) + b'\n', cache=False)

    def test_non_string_type_breaks_instead_of_crashing(self):
        for bad in ({}, [], 1, None, True):
            led = self.signed(lambda e: e['msg'].update(type=bad))
            self.assertEqual(led.broken_at, 1)
            self.assertIn('type', led.error)

    def test_true_is_not_one(self):
        self.assertEqual(self.signed(lambda e: e['msg'].update(v=True)).broken_at, 1)
        self.assertEqual(self.signed(lambda e: e.update(seq=True)).broken_at, 1)
        led = Ledger(b'{"ledger":true,"name":"x","owner":"' + public(SELLER).encode() + b'"}\n', cache=False)
        self.assertIsNone(led.header)


class Receipts(unittest.TestCase):
    def test_receipt_verifies_standalone(self):
        seller = trade()
        buyer = Book(BUYER, 'Asha')
        e = seller.led.entries[2]
        body = {'ledger': seller.led.id, 'url': 'https://farm.example', 'header': seller.led.header, 'entry': e}
        buyer.own('receipt', body)
        self.assertTrue(Ledger(buyer.led.data).whole)
        forged = json.loads(json.dumps(e))
        forged['msg']['body']['quantity'] = 2
        self.assertRaises(Invalid, message, BUYER, 'receipt', dict(body, entry=forged))
        self.assertRaises(Invalid, message, BUYER, 'receipt', dict(body, ledger=buyer.led.id))
        e2 = dict(e, seq=7)
        self.assertRaises(Invalid, message, BUYER, 'receipt', dict(body, entry=e2))


if __name__ == '__main__':
    unittest.main()

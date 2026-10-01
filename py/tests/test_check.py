import json, os, shutil, tempfile, unittest
from helpers import Book, BUYER, SELLER, offer_body
from ledgdex.check import check, workflow
from ledgdex.core import Ledger, message, unsigned, verify


class Check(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, 'state')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, name, data):
        p = os.path.join(self.tmp, name)
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def run_check(self, *sources, **kw):
        return check(list(sources), self.state, log=lambda line: None, **kw)

    def codes(self, report):
        return [(p['level'], p['code']) for p in report['problems']]

    def trade(self):
        seller, buyer = Book(), Book(BUYER, 'Asha')
        oid, oh = seller.offer()
        seller.claim(oid, oh)
        sp = self.put('seller.jsonl', seller.led.data)
        e = seller.led.entries[2]
        buyer.own('receipt', {'ledger': seller.led.id, 'url': sp, 'header': seller.led.header, 'entry': e})
        bp = self.put('buyer.jsonl', buyer.led.data)
        return seller, buyer, sp, bp

    def rewrite_from(self, book, n, text):
        """The owner re-signs history from seq n: still a whole, valid ledger."""
        led = Ledger(book.led.header_line + b'\n')
        for i, e in enumerate(book.led.entries):
            m = e['msg'] if i < n else message(SELLER, 'note', {'ref': led.ids[0], 'text': text}, at=e['time'])
            led.append(led.next_entry(SELLER, m, at=e['time']))
        self.assertTrue(led.whole)
        return led

    def test_clean_then_growing(self):
        seller, buyer, sp, bp = self.trade()
        r = self.run_check(bp)
        self.assertTrue(r['ok'], r)
        self.assertEqual([c['url'] for c in r['checked']], [bp, sp])
        seller.own('note', {'ref': seller.led.ids[0], 'text': 'more'})
        self.put('seller.jsonl', seller.led.data)
        self.assertTrue(self.run_check(bp)['ok'])

    def test_rewritten_history_is_equivocation(self):
        seller, _, sp, _ = self.trade()
        self.assertTrue(self.run_check(sp)['ok'])
        self.put('seller.jsonl', self.rewrite_from(seller, 2, 'that claim never happened').data)
        r = self.run_check(sp)
        self.assertFalse(r['ok'])
        self.assertIn(('error', 'equivocation'), self.codes(r))
        with open(r['problems'][0]['proof']) as f:
            proof = json.load(f)
        owner = proof['header']['owner']
        for k in ('seen', 'now'):  # both entries verify against the owner key: signed proof
            self.assertTrue(verify(owner, unsigned(proof[k]), proof[k]['sig']))
        self.assertEqual(proof['seen']['seq'], proof['now']['seq'])
        self.assertFalse(self.run_check(sp)['ok'])  # the seen copy is kept, so it stays failed

    def test_truncated(self):
        seller, _, sp, _ = self.trade()
        self.run_check(sp)
        self.put('seller.jsonl', seller.led.data[:-len(seller.led.lines[-1]) - 1])
        r = self.run_check(sp)
        self.assertTrue(r['ok'])  # an exact start of what was seen: stale, not rewritten
        self.assertIn(('warning', 'stale'), self.codes(r))

    def test_old_snapshot_is_not_a_missing_receipt(self):
        seller, _, sp, bp = self.trade()
        self.put('seller.jsonl', seller.led.data[:-len(seller.led.lines[-1]) - 1])
        r = self.run_check(bp)
        self.assertTrue(r['ok'])
        self.assertIn(('warning', 'receipt_not_visible'), self.codes(r))

    def test_receipt_catches_a_rewrite_on_first_sight(self):
        seller, _, sp, bp = self.trade()
        self.put('seller.jsonl', self.rewrite_from(seller, 2, 'rewritten').data)
        r = self.run_check(bp)  # never seen the seller before: the buyer's receipt is the evidence
        self.assertIn(('error', 'receipt_mismatch'), self.codes(r))

    def test_receipts_meet_every_copy(self):
        seller, _, sp, bp = self.trade()
        good = self.put('good.jsonl', seller.led.data)
        self.put('seller.jsonl', seller.led.data[:-len(seller.led.lines[-1]) - 1])  # the receipt's address is stale
        r = self.run_check(bp, good)
        self.assertTrue(r['ok'])
        self.assertNotIn(('warning', 'receipt_not_visible'), self.codes(r))
        self.put('good.jsonl', self.rewrite_from(seller, 2, 'rewritten').data)
        self.assertIn(('error', 'receipt_mismatch'), self.codes(self.run_check(bp, good)))

    def test_address_serves_another_ledger(self):
        _, _, sp, _ = self.trade()
        self.run_check(sp)
        self.put('seller.jsonl', Book(BUYER, 'Impostor').led.data)
        self.assertIn(('error', 'ledger_changed'), self.codes(self.run_check(sp)))

    def test_unreachable_counterparty_is_a_warning(self):
        _, _, sp, bp = self.trade()
        os.remove(sp)
        r = self.run_check(bp)
        self.assertTrue(r['ok'])
        self.assertIn(('warning', 'receipts_unchecked'), self.codes(r))
        self.assertFalse(self.run_check(sp)['ok'])  # an own source that is missing is an error

    def test_broken(self):
        seller, _, sp, _ = self.trade()
        data = bytearray(seller.led.data)
        data[-20] ^= 1
        self.put('seller.jsonl', bytes(data))
        self.assertIn(('error', 'broken'), self.codes(self.run_check(sp)))

    def test_media(self):
        pic = self.put('pic.png', b'picture')
        b = Book()
        h = 'sha256:' + __import__('hashlib').sha256(b'picture').hexdigest()
        b.own('offer', offer_body(item={'title': 'x', 'text': '', 'media': [{'url': 'file://' + pic, 'hash': h}]}))
        sp = self.put('s.jsonl', b.led.data)
        self.assertTrue(self.run_check(sp, media=True)['ok'])
        self.put('pic.png', b'another picture')
        self.assertIn(('error', 'media_changed'), self.codes(self.run_check(sp, media=True)))
        os.remove(pic)
        self.assertIn(('warning', 'media_unavailable'), self.codes(self.run_check(sp, media=True)))

    def test_workflow(self):
        w = workflow(['seller/ledgdex.jsonl', 'buyer/ledgdex.jsonl'], cron='5 4 * * *')
        self.assertIn('run: ledgdex check seller/ledgdex.jsonl buyer/ledgdex.jsonl --json ledgdex-check.json', w)
        self.assertIn('cron: "5 4 * * *"', w)
        self.assertIn('key: ledgdex-check-${{ github.run_id }}', w)


if __name__ == '__main__':
    unittest.main()

import json, os, shutil, tempfile, unittest
from helpers import Book, BUYER, OTHER, SELLER, offer_body
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

    def test_a_receipt_cannot_blame_an_unrelated_address(self):
        seller, buyer = Book(), Book(BUYER, 'Asha')
        oid, oh = seller.offer()
        seller.claim(oid, oh)
        other = self.put('other.jsonl', Book(BUYER, 'Bystander').led.data)   # never served the seller's ledger
        buyer.own('receipt', {'ledger': seller.led.id, 'url': other, 'header': seller.led.header,
                              'entry': json.loads(seller.led.lines[1])})
        r = self.run_check(self.put('buyer.jsonl', buyer.led.data))
        self.assertTrue(r['ok'], r['problems'])
        self.assertIn(('warning', 'receipt_url_mismatch'), self.codes(r))

    def test_a_revoked_device_cannot_frame_the_seller(self):
        from ledgdex.core import message, public, sign
        from helpers import t
        PHONE = bytes(range(10, 42))
        seller, buyer = Book(), Book(BUYER, 'Asha')
        oid, oh = seller.offer()
        seller.own('device', {'key': public(PHONE), 'name': 'phone'})
        seller.own('device_revoke', {'key': public(PHONE), 'reason': 'stolen'})
        seller.claim(oid, oh)
        sp = self.put('seller.jsonl', seller.led.data)
        dev = seller.led.entries[2]                     # the device entry, without its revoke
        fake = {'seq': 4, 'prev': seller.led.ids[3], 'time': t(30),
                'msg': message(BUYER, 'confirmed', {'claim': seller.led.ids[4]}, at=t(30))}
        fake['sig'] = sign(PHONE, fake)                 # signed by the thief with the revoked device key
        buyer.own('receipt', {'ledger': seller.led.id, 'url': sp, 'header': seller.led.header, 'entry': fake,
                              'keys': [dev]})
        r = self.run_check(self.put('buyer.jsonl', buyer.led.data), sp)
        self.assertTrue(r['ok'], r['problems'])
        self.assertIn(('warning', 'receipt_bad_signer'), self.codes(r))

    def test_an_unreachable_root_is_not_tampering(self):
        r = self.run_check(self.put('s.jsonl', Book().led.data), root=os.path.join(self.tmp, 'no-root.jsonl'))
        self.assertTrue(r['ok'])
        self.assertIn(('warning', 'unreachable'), self.codes(r))

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

    def serve(self):
        """Serve self.tmp over local HTTP; returns its address."""
        import functools, http.server, threading
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.tmp)
        handler.log_message = lambda *a: None
        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        return 'http://127.0.0.1:' + str(httpd.server_port)

    def test_media(self):
        pic = self.put('pic.png', b'picture')
        base = self.serve()
        b = Book()
        h = 'sha256:' + __import__('hashlib').sha256(b'picture').hexdigest()
        b.own('offer', offer_body(item={'title': 'x', 'text': '', 'media': [{'url': base + '/pic.png', 'hash': h}]}))
        sp = self.put('s.jsonl', b.led.data)
        self.assertTrue(self.run_check(sp, media=True)['ok'])
        self.put('pic.png', b'another picture')
        self.assertIn(('error', 'media_changed'), self.codes(self.run_check(sp, media=True)))
        os.remove(pic)
        self.assertIn(('warning', 'media_unavailable'), self.codes(self.run_check(sp, media=True)))

    def test_media_is_only_fetched_over_http(self):
        pic = self.put('pic.png', b'picture')
        h = 'sha256:' + __import__('hashlib').sha256(b'picture').hexdigest()
        b = Book()
        b.own('offer', offer_body(item={'title': 'x', 'text': '', 'media': [{'url': 'file://' + pic, 'hash': h}]}))
        r = self.run_check(self.put('s.jsonl', b.led.data), media=True)
        self.assertEqual([('warning', 'media_unavailable')], self.codes(r))
        self.assertIn('only http(s)', r['problems'][0]['detail'])

    def test_a_ledger_cannot_make_check_read_local_files(self):
        secret = self.put('secret.txt', b'not a ledger')
        seller, buyer = Book(), Book(BUYER, 'Asha')
        oid, oh = seller.offer()
        seller.claim(oid, oh)
        for src in (secret, 'file://' + secret):
            buyer.own('receipt', {'ledger': seller.led.id, 'url': src, 'header': seller.led.header,
                                  'entry': json.loads(seller.led.lines[1])})
        r = self.run_check(self.put('buyer.jsonl', buyer.led.data))
        self.assertEqual(2, sum(1 for p in r['problems'] if p['code'] == 'unreachable' and 'only http' in p['detail']))

    def test_size_limit(self):
        import ledgdex.dex as dex
        from ledgdex.core import Invalid
        self.put('big.jsonl', b'x' * 2000)
        base = self.serve()
        old, dex.MAX_BYTES = dex.MAX_BYTES, 1000
        try:
            with self.assertRaises(Invalid):
                dex.fetch(base + '/big.jsonl')
            with self.assertRaises(Invalid):
                dex.fetch(os.path.join(self.tmp, 'big.jsonl'))
        finally:
            dex.MAX_BYTES = old

    def test_a_forged_receipt_does_not_frame_the_seller(self):
        from ledgdex.core import public, sign
        from helpers import t
        seller, buyer = Book(), Book(BUYER, 'Asha')
        oid, oh = seller.offer()
        seller.claim(oid, oh)
        sp = self.put('seller.jsonl', seller.led.data)
        # a "recovered" key entry signed by the buyer, handing the seller's ledger to the buyer's key
        k = {'v': 1, 'type': 'recovered', 'by': public(BUYER), 'at': t(5),
             'body': {'root': 'sha256:' + '0' * 64, 'entry': 'sha256:' + '0' * 64}}
        k['sig'] = sign(BUYER, k)
        k = {'seq': 1, 'prev': seller.led.ids[0], 'time': t(5), 'msg': k}
        k['sig'] = sign(BUYER, k)
        f = {'v': 1, 'type': 'confirmed', 'by': public(BUYER), 'at': t(6), 'body': {'claim': 'sha256:' + '1' * 64}}
        f['sig'] = sign(BUYER, f)
        f = {'seq': 2, 'prev': 'sha256:' + '2' * 64, 'time': t(6), 'msg': f}
        f['sig'] = sign(BUYER, f)
        m = {'v': 1, 'type': 'receipt', 'by': public(BUYER), 'at': t(7), 'body': {
            'ledger': seller.led.id, 'url': sp, 'header': seller.led.header, 'entry': f, 'keys': [k]}}
        m['sig'] = sign(BUYER, m)
        e = {'seq': 1, 'prev': buyer.led.ids[-1], 'time': t(7), 'msg': m}
        e['sig'] = sign(BUYER, e)
        from ledgdex.canon import canon
        bp = self.put('buyer.jsonl', buyer.led.data + canon(e) + b'\n')
        r = self.run_check(bp, sp)                         # no root given: it cannot be judged, and blames no one
        self.assertEqual([('warning', 'needs_root')], self.codes(r))
        self.assertEqual(bp, r['problems'][0]['url'])
        root = self.put('root.jsonl', Book(OTHER, 'Root').led.data)
        r = self.run_check(bp, sp, root=root)              # with the root: the forged recovery breaks the buyer's ledger
        self.assertEqual([('error', 'broken')], self.codes(r))
        self.assertEqual(bp, r['problems'][0]['url'])

    def test_workflow_cannot_be_injected(self):
        from ledgdex.core import Invalid
        w = workflow(['a b.jsonl', '$(curl evil)', 'x;rm -rf /'])
        self.assertIn("ledgdex check 'a b.jsonl' '$(curl evil)' 'x;rm -rf /' --json", w)
        self.assertIn('ledgdex@v' + __import__('ledgdex').__version__ + '#subdirectory=py', w)
        for bad in ([['a\n      - run: evil']], [['--json=/etc/x']]):
            with self.assertRaises(Invalid):
                workflow(*bad)
        with self.assertRaises(Invalid):
            workflow(['a.jsonl'], cron='0 0 * * *"\n    - run: evil')

    def test_workflow(self):
        w = workflow(['seller/ledgdex.jsonl', 'buyer/ledgdex.jsonl'], cron='5 4 * * *')
        self.assertIn('run: ledgdex check seller/ledgdex.jsonl buyer/ledgdex.jsonl --json ledgdex-check.json', w)
        self.assertIn('cron: "5 4 * * *"', w)
        self.assertIn('key: ledgdex-check-${{ github.run_id }}', w)


if __name__ == '__main__':
    unittest.main()

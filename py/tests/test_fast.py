import json, os, random, tempfile, unittest
from helpers import Book, BUYER
from ledgdex import ed25519, sig
from ledgdex.core import Ledger

VECTORS = os.path.join(os.path.dirname(__file__), '..', '..', 'vectors', 'ed25519.json')


@unittest.skipUnless(sig.backend.name == 'cryptography', 'the cryptography package is not installed')
class Backends(unittest.TestCase):
    """The fast backend must agree with the vendored code on everything, valid or not."""

    def test_vectors(self):
        with open(VECTORS) as f:
            rows = json.load(f)['vectors']
        for r in rows:
            sk, pk, msg, s = (bytes.fromhex(r[k]) for k in ('secret', 'public', 'message', 'signature'))
            self.assertEqual(sig.backend.public_key(sk), pk)
            self.assertEqual(sig.backend.sign(sk, msg), s)
            self.assertTrue(sig.backend.verify(pk, msg, s))

    def test_agree_on_mutations(self):
        rnd = random.Random(7)
        for i in range(40):
            sk, msg = bytes(rnd.getrandbits(8) for _ in range(32)), bytes(rnd.getrandbits(8) for _ in range(i))
            pk, s = sig.pure.public_key(sk), sig.pure.sign(sk, msg)
            self.assertEqual(sig.backend.sign(sk, msg), s)
            cases = [(pk, msg, s)]
            for _ in range(6):  # flip one bit anywhere in the key, the message or the signature
                which, pos = rnd.randrange(3), rnd.randrange(8 * 64)
                p2, m2, s2 = bytearray(pk), bytearray(msg + b'x'), bytearray(s)
                target = (p2, m2, s2)[which]
                target[pos // 8 % len(target)] ^= 1 << pos % 8
                cases.append((bytes(p2), bytes(m2), bytes(s2)))
            n = int.from_bytes(s[32:], 'little') + ed25519.q   # non-canonical s
            cases.append((pk, msg, s[:32] + n.to_bytes(32, 'little')))
            y = (ed25519.p + 1).to_bytes(32, 'little')         # non-canonical point encodings
            cases += [(y, msg, s), (pk, msg, y + s[32:])]
            for c in cases:
                self.assertEqual(sig.backend.verify(*c), sig.pure.verify(*c), c)


SMALL_ORDER = ['0100000000000000000000000000000000000000000000000000000000000000',
               'ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f',
               '0000000000000000000000000000000000000000000000000000000000000000',
               'c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a',
               'c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa',
               '26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05',
               '26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85']


class SmallOrderKeys(unittest.TestCase):
    def test_small_order_keys_never_verify(self):
        from ledgdex import ed25519
        forged = ed25519._compress(ed25519.G) + (1).to_bytes(32, 'little')   # verifies for every message under 0x01..
        for k in SMALL_ORDER:
            pub = bytes.fromhex(k)
            self.assertTrue(ed25519.small_order(pub), k)
            for b in (sig.backend, sig.pure):
                self.assertFalse(b.verify(pub, b'any message', forged), (b.name, k))
        self.assertFalse(ed25519.small_order(bytes.fromhex(sig._KAT_PUBLIC.hex())))


class Cache(unittest.TestCase):
    def setUp(self):
        self.before = os.environ['LEDGDEX_CACHE'], os.environ.pop('LEDGDEX_NO_CACHE', None)
        os.environ['LEDGDEX_CACHE'] = tempfile.mkdtemp(prefix='ledgdex-cache-')

    def tearDown(self):
        os.environ['LEDGDEX_CACHE'] = self.before[0]
        if self.before[1] is not None:
            os.environ['LEDGDEX_NO_CACHE'] = self.before[1]

    def book(self, n=6):
        b = Book()
        oid, oh = b.offer(quantity=100)
        for _ in range(n):
            b.claim(oid, oh)
        return b

    def test_grows_from_where_it_was(self):
        b = self.book()
        first = Ledger(b.led.data)
        self.assertEqual(first.cached, 0)
        self.assertTrue(first.whole)
        again = Ledger(b.led.data)
        self.assertEqual(again.cached, 8)
        self.assertEqual((again.ids, again.entries), (first.ids, first.entries))
        b.own('note', {'ref': b.led.ids[0], 'text': 'more'})
        grown = Ledger(b.led.data)
        self.assertEqual((grown.cached, len(grown.entries), grown.whole), (8, 9, True))

    def test_any_change_misses(self):
        b = self.book()
        Ledger(b.led.data)
        data = bytearray(b.led.data)
        data[len(b.led.header_line) + 40] ^= 1   # inside the first entry, in the cached prefix
        led = Ledger(bytes(data))
        self.assertEqual(led.cached, 0)
        self.assertEqual(led.broken_at, 0)

    @unittest.skipUnless(hasattr(os, 'getuid'), 'POSIX only')
    def test_a_cache_others_can_write_is_not_trusted(self):
        b = self.book(2)
        Ledger(b.led.data)
        verified = os.path.join(os.environ['LEDGDEX_CACHE'], 'verified')
        self.assertEqual(os.stat(verified).st_mode & 0o777, 0o700)
        os.chmod(verified, 0o777)
        self.assertEqual(Ledger(b.led.data).cached, 0)
        os.chmod(verified, 0o700)
        self.assertEqual(Ledger(b.led.data).cached, 4)

    def test_off_switches(self):
        b = self.book(2)
        Ledger(b.led.data)
        self.assertEqual(Ledger(b.led.data, cache=False).cached, 0)
        os.environ['LEDGDEX_NO_CACHE'] = '1'
        try:
            self.assertEqual(Ledger(b.led.data).cached, 0)
        finally:
            del os.environ['LEDGDEX_NO_CACHE']

    def test_bad_cache_files_are_ignored(self):
        b = self.book(2)
        led = Ledger(b.led.data)
        path = led._cache_path()
        for junk in ('not json', '{"entries": 4, "length": 10, "sha256": "00"}', '[]'):
            with open(path, 'w') as f:
                f.write(junk)
            again = Ledger(b.led.data)
            self.assertEqual(again.cached, 0)
            self.assertTrue(again.whole)

    def test_other_ledgers_do_not_share(self):
        a, b = self.book(1), Book(BUYER, 'Asha')
        Ledger(a.led.data)
        self.assertEqual(Ledger(b.led.data).cached, 0)


if __name__ == '__main__':
    unittest.main()

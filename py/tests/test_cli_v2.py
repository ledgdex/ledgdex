"""The new commands end to end: devices, rotation, recovery, disputes, auctions, indexes."""
import contextlib, io, json, os, re, shutil, tempfile, time, unittest
import helpers  # noqa: F401
from ledgdex.cli import main
from ledgdex.core import Ledger, now, seconds, utc
from ledgdex.dex import load

try:
    import dexweb.dexgen  # noqa: F401
    HAVE_DEXWEB = True
except Exception:
    HAVE_DEXWEB = False


def run(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main([str(a) for a in args])
    return buf.getvalue()


def fails(*args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            main([str(a) for a in args])
        except SystemExit as e:
            return e.code not in (0, None)
    return False


@unittest.skipUnless(HAVE_DEXWEB, 'dexweb is not installed')
class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ)
        self.home = os.path.join(self.tmp, 'keys')
        os.environ['LEDGDEX_HOME'] = self.home
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        run('init', 'shop', '--name', 'Farm', '--key', 'farm', '--url', 'https://farm.example')
        run('init', 'me', '--name', 'Asha', '--key', 'asha')
        with open('offer.json', 'w') as f:
            json.dump({'item': {'title': 'Mangoes'}, 'quantity': 3, 'unit': 'dozen', 'currency': 'INR',
                       'price': 1000}, f)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.clear()
        os.environ.update(self.env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def st(self, dex, *extra):
        return json.loads(run('state', dex, *extra))

    def offer(self):
        return run('offer', 'shop', 'offer.json').split(': ')[1].strip()

    def test_phone_as_a_device(self):
        os.environ['LEDGDEX_HOME'] = phone = os.path.join(self.tmp, 'phone-keys')
        pub = run('keygen', 'phone').strip()
        self.assertTrue(fails('device', 'add', 'shop', pub))          # the phone has no owner key
        os.environ['LEDGDEX_HOME'] = self.home
        run('device', 'add', 'shop', pub, '--name', 'phone')
        os.environ['LEDGDEX_HOME'] = phone
        oid = self.offer()                                             # the phone sells
        led = load('shop')
        self.assertEqual(led.entries[led.find(oid)]['msg']['by'], pub)
        os.environ['LEDGDEX_HOME'] = self.home
        run('device', 'revoke', 'shop', pub, '--reason', 'lost')
        os.environ['LEDGDEX_HOME'] = phone
        self.assertTrue(fails('note', 'shop', oid, 'from a revoked phone'))
        self.assertEqual(self.st('shop')['devices'], [])

    def test_rotate_then_trade_with_receipts(self):
        run('rotate', 'shop', '--key', 'farm2')
        os.remove(os.path.join(self.home, 'farm.key'))                 # the old key is gone; nothing needs it
        oid = self.offer()
        run('claim', 'me', 'shop', oid, '-o', 'c.json')
        run('record', 'shop', '--from', 'me')
        out = run('receipt', 'me', 'shop')
        self.assertIn('Claim id', out)
        receipt = [e for e in load('me').entries if e['msg']['type'] == 'receipt'][0]
        self.assertEqual([k['msg']['type'] for k in receipt['msg']['body']['keys']], ['rotate'])
        self.assertTrue(Ledger(open('me/ledgdex.jsonl', 'rb').read(), cache=False).whole)

    def test_recovery_through_the_root(self):
        run('init', 'root', '--name', 'Root', '--key', 'rootkey')
        self.offer()
        os.remove(os.path.join(self.home, 'farm.key'))                 # lost
        self.assertTrue(fails('note', 'shop', 'sha256:' + '0' * 64, 'x'))
        new = run('keygen', 'farm-new').strip()
        run('recover', 'root', 'shop', new)
        run('recovered', 'shop', '--root', 'root', '--key', 'farm-new')
        run('note', 'shop', 'sha256:' + '0' * 64, 'back again')
        self.assertIn('whole', run('verify', 'shop', '--root', 'root', '--full'))
        os.environ['LEDGDEX_NO_CACHE'] = '1'
        self.assertTrue(fails('verify', 'shop/ledgdex.jsonl'))         # without the root it cannot verify
        self.assertEqual(self.st('shop', '--root', 'root')['owner'], new)

    def test_dispute_and_ruling(self):
        run('init', 'judge', '--name', 'Judge', '--key', 'judge')
        judge = load('judge').owner
        with open('offer.json') as f:
            o = json.load(f)
        o['arbiter'] = {'key': judge, 'url': ''}
        with open('offer.json', 'w') as f:
            json.dump(o, f)
        oid = self.offer()
        run('claim', 'me', 'shop', oid, '-o', 'c.json')
        run('record', 'shop', '--from', 'me')
        cid = re.search(r'Claim id: (sha256:\w+)', run('receipt', 'me', 'shop')).group(1)
        run('dispute', 'me', cid, '--seller', 'shop', '--text', 'never arrived')
        run('record', 'shop', '--from', 'me')
        did = list(self.st('shop')['disputes'])[0]
        self.assertEqual(self.st('shop')['claims'][cid]['status'], 'disputed')
        run('ruling', 'judge', 'shop', did, '--outcome', 'refund', '--text', 'refund the buyer')
        run('record', 'shop', '--from', 'judge')
        self.assertEqual(self.st('shop')['claims'][cid]['status'], 'refunded')

    def test_auction(self):
        start = seconds(now())
        with open('auction.json', 'w') as f:
            json.dump({'item': {'title': 'Old map'}, 'currency': 'INR', 'close': utc(start + 3),
                       'reveal_until': utc(start + 6), 'reserve': 100}, f)
        aid = run('auction', 'shop', 'auction.json').split(': ')[1].strip()
        run('init', 'bob', '--name', 'Bob', '--key', 'bob')
        run('bid', 'me', 'shop', aid, '--amount', 500, '-o', 'b1.json')
        run('bid', 'bob', 'shop', aid, '--amount', 700, '-o', 'b2.json')
        self.assertTrue(fails('bid', 'me', 'shop', aid, '--amount', 900))   # one bid each
        run('record', 'shop', '--from', 'me', '--from', 'bob')
        self.assertEqual(self.st('shop')['auctions'][aid]['bids'], 2)
        time.sleep(max(0, start + 3 - time.time()) + 1)
        run('reveal', 'me', 'shop', aid, '-o', 'r1.json')
        run('reveal', 'bob', 'shop', aid, '-o', 'r2.json')
        run('record', 'shop', '--from', 'me', '--from', 'bob')
        time.sleep(max(0, start + 6 - time.time()) + 1)
        run('note', 'shop', aid, 'closed')                               # any later entry: the award is decided
        a = self.st('shop')['auctions'][aid]
        self.assertEqual((a['status'], a['amount'], a['winner']), ('awarded', 700, load('bob').owner))

    def test_index(self):
        run('init', 'index', '--name', 'Market', '--key', 'market')
        oid = self.offer()
        run('list', 'index', 'shop', '--url', os.path.join(self.tmp, 'shop'), '--note', 'mangoes')
        found = json.loads(run('discover', 'index', '--offers', '--json'))
        self.assertEqual(found[0]['offers'][0]['id'], oid)
        lid = found[0]['ledger']
        run('delist', 'index', lid, '--reason', 'closed')
        self.assertEqual(json.loads(run('discover', 'index', '--json')), [])


if __name__ == '__main__':
    unittest.main()

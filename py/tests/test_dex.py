"""Dex, render, publish and the command-line tool (spec 7, Part III milestones 3, 5 and 6). Needs dexweb and git."""
import contextlib, io, json, os, re, shutil, subprocess, tempfile, unittest
import helpers  # noqa: F401
from ledgdex.cli import main
from ledgdex.core import Ledger
from ledgdex.dex import LEDGER, load, write
from ledgdex.render import MARKER, render

try:
    from dexweb import dexweb
    HAVE_DEXWEB = True
except Exception:
    HAVE_DEXWEB = False


def run(*args):
    """Run the CLI in-process; returns stdout."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(list(args))
    return buf.getvalue()


@unittest.skipUnless(HAVE_DEXWEB, 'dexweb is not installed')
class Dex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ)
        os.environ.update(LEDGDEX_HOME=os.path.join(self.tmp, 'keys'), GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                          GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t', GIT_CEILING_DIRECTORIES=self.tmp)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.clear()
        os.environ.update(self.env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shop(self, name='shop', **kw):
        args = ['init', name, '--name', 'Mango Farm', '--key', 'farm', '--url', 'https://farm.example']
        for k, v in kw.items():
            args += ['--' + k, v]
        run(*args)
        with open('offer.json', 'w') as f:
            json.dump({'item': {'title': 'Alphonso mangoes'}, 'quantity': 3, 'unit': 'dozen', 'currency': 'INR',
                       'price': 120000}, f)
        out = run('offer', name, 'offer.json')
        return out.split(': ')[1].strip()

    def state(self, dex):
        return json.loads(run('state', dex))

    def test_init_makes_a_complete_dex(self):
        self.shop()
        for f in ('data.json', 'config.json', 'styles.css', 'run.py', LEDGER, 'gen/index.html', 'gen/' + LEDGER):
            self.assertTrue(os.path.exists(os.path.join('shop', f)), f)
        with open('shop/config.json') as f:
            self.assertEqual(json.load(f)['publish'], {'append_only': [LEDGER]})
        with open('shop/gen/' + LEDGER, 'rb') as a, open('shop/' + LEDGER, 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_trade_between_two_dexs(self):
        oid = self.shop()
        run('init', 'me', '--name', 'Asha', '--key', 'asha')
        run('claim', 'me', 'shop', oid, '--quantity', '2', '-o', 'c.json')
        run('record', 'shop', '--from', 'me')            # sending is publishing: the seller collects
        self.assertIn('nothing new', run('record', 'shop', 'c.json'))
        out = run('receipt', 'me', 'shop')
        cid = re.search(r'Claim id: (sha256:\w+)', out).group(1)
        run('pay', 'me', 'shop', cid, '--method', 'upi', '--ref', 'UTR1')
        run('record', 'shop', '--from', 'me')
        run('received', 'shop', cid, '240000')
        run('delivered', 'shop', cid)
        run('confirm', 'me', 'shop', cid)
        run('record', 'shop', '--from', 'me')
        run('receipt', 'me', 'shop')
        c = self.state('shop')['claims'][cid]
        self.assertEqual((c['status'], c['quantity'], c['received']), ('closed', 2, 240000))
        buyer = load('me')
        self.assertEqual([e['msg']['type'] for e in buyer.entries],
                         ['open', 'sent', 'receipt', 'sent', 'sent', 'receipt', 'receipt'])
        self.assertEqual(self.state('me')['ignored'], [])

    def test_cannot_claim_own_offer(self):
        oid = self.shop()
        self.assertFalse(self.quiet('claim', 'shop', 'shop', oid))
        self.assertEqual(self.state('shop')['claims'], {})

    def test_render(self):
        self.shop()
        with open('shop/data.json') as f:
            data = json.load(f)
        author = [{'title': 'About', 'body': ['My <b>own</b> page']},
                  {'title': 'Alphonso Mangoes!', 'body': ['clash by file name']}, {'title': 'Empty', 'body': []}]
        with open('shop/data.json', 'w') as f:
            json.dump(author + data, f)
        render('shop')
        with open('shop/data.json', 'rb') as f:
            once = f.read()
        render('shop')
        with open('shop/data.json', 'rb') as f:
            self.assertEqual(f.read(), once)            # deterministic
        data = json.loads(once)
        self.assertEqual(data[:3], author)              # author pages untouched
        gen = data[3:]
        self.assertEqual([p['title'] for p in gen], ['Mango Farm ledger', 'Alphonso mangoes (ledgdex)'])
        for p in gen:
            self.assertTrue(p['body'][0].startswith(MARKER))
            text = ' '.join(p['body'])
            self.assertNotRegex(text, r'class=|style=|<script')
        self.assertTrue(os.path.exists('shop/gen/alphonsomangoesledgdex.html'))

    def test_render_escapes(self):
        run('init', 'x', '--name', '<script>x</script>', '--key', 'k')
        with open('x/data.json') as f:
            self.assertNotIn('<script>', f.read())

    # ----- publishing (spec 3.5, 7.4) -----

    def remote(self):
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', 'site.git'], check=True)
        return 'file://' + os.path.join(self.tmp, 'site.git')

    def published(self):
        r = subprocess.run(['git', '--git-dir', 'site.git', 'show', 'main:' + LEDGER], capture_output=True)
        return r.stdout if r.returncode == 0 else None

    def quiet(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                main(list(args))
                return True
            except SystemExit as e:
                return e.code in (0, None)

    def test_publish(self):
        url = self.remote()
        self.shop(dest=url, branch='main')
        self.assertTrue(self.quiet('publish', 'shop'))
        with open('shop/' + LEDGER, 'rb') as f:
            self.assertEqual(self.published(), f.read())
        run('withdraw', 'shop', list(self.state('shop')['offers'])[0])
        self.assertTrue(self.quiet('publish', 'shop'))
        with open('shop/' + LEDGER, 'rb') as f:
            self.assertEqual(self.published(), f.read())

    def test_dexweb_refuses_a_rewritten_ledger(self):
        url = self.remote()
        self.shop(dest=url, branch='main')
        self.assertTrue(self.quiet('publish', 'shop'))
        led = load('shop')
        write('shop', led.data[:-len(led.lines[-1]) - 1])   # shorter: drop the offer
        render('shop')
        cwd = os.getcwd()
        os.chdir('shop')
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(dexweb.Dexweb().publish())    # even run.py-style publishing refuses
        finally:
            os.chdir(cwd)
        self.assertEqual(len(Ledger(self.published()).entries), 2)

    def test_publish_needs_a_dex(self):
        self.assertFalse(self.quiet('publish', 'nothere'))

    def test_publish_needs_append_only(self):
        self.shop()
        with open('shop/config.json') as f:
            cfg = json.load(f)
        cfg['publish'] = {'branch': 'main'}
        with open('shop/config.json', 'w') as f:
            json.dump(cfg, f)
        self.assertFalse(self.quiet('publish', 'shop'))

    def test_two_devices(self):
        url = self.remote()
        self.shop(dest=url, branch='main')
        self.assertTrue(self.quiet('publish', 'shop'))
        shutil.copytree('shop', 'phone', ignore=shutil.ignore_patterns('.publish'))
        oid = list(self.state('shop')['offers'])[0]
        run('note', 'shop', oid, 'from the laptop')
        run('note', 'phone', oid, 'from the phone')
        self.assertTrue(self.quiet('publish', 'shop'))
        self.assertTrue(self.quiet('publish', 'phone'))    # rejected at first, re-sequenced, published
        pub = Ledger(self.published())
        self.assertTrue(pub.whole)
        self.assertEqual([e['msg']['body'].get('text') for e in pub.entries[2:]], ['from the laptop', 'from the phone'])
        with open('phone/' + LEDGER, 'rb') as f:
            self.assertEqual(f.read(), self.published())
        self.assertTrue(self.quiet('publish', 'shop'))     # the laptop catches up
        with open('shop/' + LEDGER, 'rb') as f:
            self.assertEqual(f.read(), self.published())

    def test_one_bad_counterparty_does_not_stop_recording(self):
        from ledgdex.canon import hash_
        from ledgdex.core import message
        from ledgdex.dex import load_key, record
        self.shop()
        oid = list(self.state('shop')['offers'])[0]
        offer = load('shop').entries[1]['msg']
        run('init', 'honest', '--name', 'Asha', '--key', 'asha')
        with contextlib.redirect_stdout(io.StringIO()):
            run('claim', 'honest', 'shop', oid, '-o', 'c.json')
        run('init', 'evil', '--name', 'Mallory', '--key', 'mal')
        late = message(load_key('mal'), 'claim', {'offer': oid, 'offer_hash': hash_(offer), 'quantity': 1,
                                                  'price': offer['body']['price']}, at='2099-01-01T00:00:00Z')
        record('evil', [message(load_key('mal'), 'sent', {'to': load('shop').owner, 'msg': late})])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            out = run('record', 'shop', '--from', 'honest', '--from', 'evil', '--from', 'nowhere')
        self.assertIn('claim recorded', out)
        self.assertIn('signed more than 300 seconds in the future', err.getvalue())
        self.assertIn('skipped nowhere', err.getvalue())
        self.assertEqual(1, len([c for c in self.state('shop')['claims'].values() if c['status'] == 'accepted']))

    def test_keys_readable_by_others_are_refused(self):
        self.shop()
        key = os.path.join(os.environ['LEDGDEX_HOME'], 'farm.key')
        os.chmod(key, 0o644)
        oid = list(self.state('shop')['offers'])[0]
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                run('note', 'shop', oid, 'x')
        self.assertIn('chmod 600', err.getvalue())
        os.chmod(key, 0o600)
        run('note', 'shop', oid, 'x')

    def test_ids_and_key_names_are_checked(self):
        self.shop()
        for args in (['withdraw', 'shop', '../../etc/passwd'], ['reveal', 'shop', 'shop', 'sha256:../../x'],
                     ['init', 'x', '--name', 'x', '--key', '../evil']):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                run(*args)
        self.assertFalse(os.path.exists('x/' + LEDGER))

    def test_concurrent_appends_keep_the_ledger_whole(self):
        import threading
        from ledgdex.core import message
        from ledgdex.dex import find_key, record
        self.shop()
        led = load('shop')
        oid, secret = list(self.state('shop')['offers'])[0], find_key(led.owner)
        threads = [threading.Thread(target=lambda i=i: record('shop', [message(secret, 'note', {
            'ref': oid, 'text': str(i)})])) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        led = load('shop')
        self.assertTrue(led.whole)
        self.assertEqual(sorted(str(i) for i in range(8)),
                         sorted(e['msg']['body']['text'] for e in led.entries if e['msg']['type'] == 'note'))


if __name__ == '__main__':
    unittest.main()

"""ledgdex shop (spec 7.5): a whole shop from one catalog, made, kept the same as the catalog, and published."""
import contextlib, copy, io, json, os, shutil, subprocess, tempfile, unittest
import helpers  # noqa: F401
from ledgdex.cli import main
from ledgdex.core import Invalid
from ledgdex.dex import load
from ledgdex.shop import shop
from ledgdex.state import state

try:
    import dexweb.dexgen  # noqa: F401
    HAVE_DEXWEB = True
except Exception:
    HAVE_DEXWEB = False

CATALOG = {
    'shop': {'name': 'Penguin Shop', 'currency': 'USD', 'about': 'Gear for cold places',
             'pay': [{'method': 'card', 'to': 'https://pay.example/penguin'}], 'terms': 'Delivery in 5 days.'},
    'products': [{'title': 'Ice axe', 'text': 'Steel, 70 cm', 'quantity': 20, 'price': 4999},
                 {'title': 'Snow boots', 'quantity': 15, 'price': 12900, 'unit': 'pair'}]}


def quiet(*args):
    with contextlib.redirect_stdout(io.StringIO()):
        main([str(a) for a in args])


@unittest.skipUnless(HAVE_DEXWEB, 'dexweb is not installed')
class Shop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ)
        os.environ.update(LEDGDEX_HOME=os.path.join(self.tmp, 'keys'), GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                          GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t', GIT_CEILING_DIRECTORIES=self.tmp)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        self.log = []

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.clear()
        os.environ.update(self.env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make(self, cat, **kw):
        return shop(cat, log=self.log.append, **kw)

    def offers(self, dex='penguin-shop'):
        led = load(dex)
        return {o['title']: o['status'] for o in state(led)['offers'].values() if o['status'] != 'withdrawn'}

    def catalog(self, **shop_fields):
        cat = copy.deepcopy(CATALOG)
        cat['shop'].update(shop_fields)
        return cat

    def test_a_catalog_becomes_a_published_shop_that_follows_the_catalog(self):
        subprocess.run(['git', 'init', '-q', '--bare', 'site.git'], check=True)   # no -b: git before 2.28 lacks it
        subprocess.run(['git', '--git-dir=site.git', 'symbolic-ref', 'HEAD', 'refs/heads/main'], check=True)
        cat = self.catalog(dest='file://' + os.path.join(self.tmp, 'site.git'), url='https://penguin.example')
        r = self.make(cat)
        self.assertEqual((0, 2, 0, True), (r['kept'], r['offered'], r['withdrawn'], r['published']))
        self.assertEqual({'Ice axe': 'open', 'Snow boots': 'open'}, self.offers())
        self.assertEqual('https://penguin.example', r['url'])
        published = subprocess.run(['git', '--git-dir=site.git', 'show', 'main:ledgdex.jsonl'], check=True,
                                   capture_output=True).stdout
        self.assertEqual(load('penguin-shop').data, published)
        body = [e['msg']['body'] for e in load('penguin-shop').entries if e['msg']['type'] == 'offer'][0]
        self.assertEqual(('USD', 'Delivery in 5 days.', 'unit', 'any'),
                         (body['currency'], body['terms'], body['unit'], body['allow']))
        # the same catalog again: nothing is signed
        lines = len(load('penguin-shop').lines)
        r = self.make(cat)
        self.assertEqual((2, 0, 0), (r['kept'], r['offered'], r['withdrawn']))
        self.assertEqual(lines, len(load('penguin-shop').lines))
        # a changed price, a removed product and a new product
        cat['products'] = [dict(cat['products'][0], price=5499), {'title': 'Wool hat', 'quantity': 5, 'price': 1500}]
        r = self.make(cat)
        self.assertEqual((0, 2, 2), (r['kept'], r['offered'], r['withdrawn']))
        self.assertEqual({'Ice axe': 'open', 'Wool hat': 'open'}, self.offers())
        prices = [o['price'] for o in (e['msg']['body'] for e in load('penguin-shop').entries
                                       if e['msg']['type'] == 'offer') if o['item']['title'] == 'Ice axe']
        self.assertEqual([4999, 5499], prices)
        published = subprocess.run(['git', '--git-dir=site.git', 'show', 'main:ledgdex.jsonl'], check=True,
                                   capture_output=True).stdout
        self.assertEqual(load('penguin-shop').data, published)

    def test_a_sold_out_product_is_not_offered_again(self):
        self.make(self.catalog())
        quiet('init', 'buyer', '--name', 'Buyer', '--key', 'buyer')
        axe = [i for i, o in state(load('penguin-shop'))['offers'].items() if o['title'] == 'Ice axe'][0]
        quiet('claim', 'buyer', 'penguin-shop', axe, '--quantity', 20, '--output', 'claim.json')
        quiet('record', 'penguin-shop', 'claim.json')
        self.assertEqual('sold', self.offers()['Ice axe'])
        r = self.make(self.catalog())
        self.assertEqual((2, 0, 0), (r['kept'], r['offered'], r['withdrawn']))
        # more stock is a changed product: a new offer. The sold offer stays as it is
        cat = self.catalog()
        cat['products'][0]['quantity'] = 30
        r = self.make(cat)
        self.assertEqual((1, 1, 0), (r['kept'], r['offered'], r['withdrawn']))
        self.assertEqual('open', self.offers()['Ice axe'])

    def test_a_wrong_catalog_signs_nothing_and_names_the_problem(self):
        def wrong(change, message):
            cat = self.catalog()
            change(cat)
            with self.assertRaises(Invalid) as e:
                self.make(cat)
            self.assertIn(message, str(e.exception))
            self.assertFalse(os.path.exists('penguin-shop'))
        wrong(lambda c: c['shop'].pop('currency'), '"currency" is necessary')
        wrong(lambda c: c['shop'].pop('name'), '"name" is necessary')
        wrong(lambda c: c['shop'].update(pay=[]), '"pay" must list one or more payment methods')
        wrong(lambda c: c['shop'].update(pay=[{'method': 'card'}]), '"pay" must list')
        wrong(lambda c: c['shop'].update(colour='blue'), 'unexpected field "colour"')
        wrong(lambda c: c['shop'].update(repo='not a repo'), 'OWNER/NAME')
        wrong(lambda c: c['shop'].update(repo='a/b', folder='site'), 'only one of')
        wrong(lambda c: c['products'][1].update(title='Ice axe'), 'two products have the title "Ice axe"')
        wrong(lambda c: c['products'][0].update(price=49.99), 'product 1: "price" must be an integer')
        wrong(lambda c: c['products'][0].update(quantity=0), '"quantity" must be an integer of 1 or more')
        wrong(lambda c: c['products'][0].update(price=True), '"price" must be an integer')
        wrong(lambda c: c['products'][0].pop('title'), 'product 1: the field "title" is necessary')
        wrong(lambda c: c['products'][1].update(sku='B-2'), 'product 2: unexpected field "sku"')
        wrong(lambda c: c['products'][1].update(media='photo.jpg'), 'product "Snow boots"')
        wrong(lambda c: c['products'][1].update(price=2 ** 60), 'product "Snow boots"')
        wrong(lambda c: c.update(products={}), '"products" must be a list')

    def test_optional_parts_can_be_left_out(self):
        cat = {'shop': {'name': 'Bare', 'currency': 'USD', 'pay': [{'method': 'cash', 'to': 'at the door'}]}}
        r = self.make(cat, publish=False)
        self.assertEqual(('bare', 0, False), (r['dex'], r['offered'], r['published']))
        r = self.make(cat)
        self.assertIn('not published: the catalog gives no "repo", "dest" or "folder"', self.log)

    def test_the_dex_must_hold_the_ledger_of_the_shop(self):
        self.make(self.catalog())
        with self.assertRaises(Invalid) as e:
            self.make(self.catalog(name='Other Shop'), dex='penguin-shop')
        self.assertIn('holds the ledger of "Penguin Shop"', str(e.exception))

    def test_repo_writes_the_github_settings_and_address(self):
        with open('catalog.json', 'w') as f:
            json.dump(self.catalog(folder='site', url='https://old.example'), f)
        quiet('shop', 'catalog.json', '--dex', 'pshop', '--repo', 'alinoorul/penguin-shop', '--no-publish')
        with open('pshop/config.json') as f:
            pub = json.load(f)['publish']
        self.assertEqual({'dest': 'git@github.com:alinoorul/penguin-shop.git', 'branch': 'main',
                          'append_only': ['ledgdex.jsonl']}, pub)
        self.assertEqual('https://alinoorul.github.io/penguin-shop', load('pshop').dex)
        r = self.make(self.catalog(repo='Alinoorul/alinoorul.github.io', site_path='shops/penguin/'), dex='user',
                      publish=False)
        self.assertEqual('https://alinoorul.github.io/shops/penguin', r['url'])

    def test_the_folder_method(self):
        r = self.make(self.catalog(folder='../www/penguin'))
        self.assertTrue(r['published'])
        with open(os.path.join('www', 'penguin', 'ledgdex.jsonl'), 'rb') as f:
            self.assertEqual(load('penguin-shop').data, f.read())

    def test_a_root_is_pinned_and_is_the_default_arbiter(self):
        quiet('init', 'exchange', '--name', 'Exchange', '--key', 'exchange', '--url', 'https://exchange.example')
        r = self.make(self.catalog(root='exchange', allow='admitted'))
        led = load('penguin-shop')
        body = [e['msg']['body'] for e in led.entries if e['msg']['type'] == 'offer'][0]
        self.assertEqual(load('exchange').owner, body['arbiter']['key'])
        self.assertEqual('admitted', body['allow'])
        self.assertEqual(2, r['offered'])
        with self.assertRaises(Invalid):
            self.make(self.catalog(root='another-root'))

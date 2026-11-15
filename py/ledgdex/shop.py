"""A whole shop from one catalog: a JSON file, or the same object in Python. shop() makes the ledgdex when it is
missing, signs one offer for each product, withdraws the open offers of products that the catalog no longer has (or
has changed), renders the pages and publishes with dexweb. Run it again with a changed catalog and the shop follows
the catalog. The command is "ledgdex shop CATALOG".

The catalog (spec 7.5):

    {"shop": {"name": "Penguin Shop", "currency": "USD",
              "pay": [{"method": "card", "to": "https://pay.example/penguin"}],
              "about": "...", "repo": "OWNER/NAME"},
     "products": [{"title": "Ice axe", "price": 4999, "quantity": 20, "text": "Steel, 70 cm"}]}

Unknown fields are refused, so a misspelt field cannot be lost without a warning."""
import os, re
from .canon import canon, CanonError
from .core import Invalid, check_body, message, new_ledger, is_key
from .dex import LEDGER, load, load_root, record, signer
from .render import create_dex, render
from .state import state

SHOP = {'name', 'currency', 'pay'}
SHOP_OPTIONAL = {'about', 'url', 'terms', 'unit', 'allow', 'arbiter', 'root', 'key', 'repo', 'dest', 'branch',
                 'site_path', 'folder'}
PRODUCT = {'title', 'price', 'quantity'}
PRODUCT_OPTIONAL = {'text', 'media', 'unit', 'terms', 'allow', 'expires'}
REPO_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+\Z')
PLACEHOLDER = 'ed25519:' + '0' * 64   # an arbiter of the right form, to check products before the dex exists


def fail(where, what):
    raise Invalid('catalog: ' + where + ': ' + what)


def fields(obj, where, required, optional):
    if not isinstance(obj, dict):
        fail(where, 'must be a JSON object')
    for k in obj:
        if k not in required and k not in optional:
            fail(where, 'unexpected field "' + k + '"')
    for k in sorted(required):
        if k not in obj:
            fail(where, 'the field "' + k + '" is necessary')


def text(obj, where, k, empty=True):
    if k in obj and (not isinstance(obj[k], str) or (not empty and not obj[k].strip())):
        fail(where, '"' + k + '" must be ' + ('a string' if empty else 'a string that is not empty'))


def check_catalog(cat):
    """Raise Invalid, naming the shop or the product, unless the catalog has the form above."""
    fields(cat, 'the catalog', {'shop'}, {'products'})
    s = cat['shop']
    fields(s, 'shop', SHOP, SHOP_OPTIONAL)
    for k in ('name', 'currency', 'unit', 'key', 'repo', 'dest', 'branch', 'site_path', 'folder', 'root'):
        text(s, 'shop', k, empty=False)
    for k in ('about', 'url', 'terms'):
        text(s, 'shop', k)
    pay = s['pay']
    if not (isinstance(pay, list) and pay and all(isinstance(p, dict) and set(p) == {'method', 'to'} and
                                                  all(isinstance(p[x], str) and p[x].strip() for x in p)
                                                  for p in pay)):
        fail('shop', '"pay" must list one or more payment methods, each {"method": ..., "to": ...}')
    if 'allow' in s and not (s['allow'] in ('any', 'admitted') or
                             (isinstance(s['allow'], list) and all(is_key(k) for k in s['allow']))):
        fail('shop', '"allow" must be "any", "admitted" or a list of keys')
    if 'arbiter' in s and not (isinstance(s['arbiter'], dict) and set(s['arbiter']) == {'key', 'url'} and
                               is_key(s['arbiter']['key']) and isinstance(s['arbiter']['url'], str)):
        fail('shop', '"arbiter" must be {"key": "ed25519:...", "url": ...}')
    if 'repo' in s and not REPO_RE.match(s['repo']):
        fail('shop', '"repo" must be a GitHub repository as OWNER/NAME')
    if sum(k in s for k in ('repo', 'dest', 'folder')) > 1:
        fail('shop', 'give only one of "repo", "dest" and "folder"')
    if 'folder' in s and ('branch' in s or 'site_path' in s):
        fail('shop', '"branch" and "site_path" are for "repo" or "dest", not for "folder"')
    products = cat.get('products', [])
    if not isinstance(products, list):
        fail('the catalog', '"products" must be a list')
    titles = set()
    for n, p in enumerate(products):
        where = 'product ' + str(n + 1)
        fields(p, where, PRODUCT, PRODUCT_OPTIONAL)
        text(p, where, 'title', empty=False)
        if p['title'] in titles:
            fail(where, 'two products have the title "' + p['title'] + '"')
        titles.add(p['title'])
        for k, low in (('price', 0), ('quantity', 1)):
            v = p[k]
            if not isinstance(v, int) or isinstance(v, bool) or v < low:
                fail(where, '"' + k + '" must be an integer of ' + str(low) + ' or more')
    for body, p in zip(offers(cat, {'key': PLACEHOLDER, 'url': ''}), products):
        try:
            check_body('offer', body)
            canon(body)
        except (Invalid, CanonError) as e:
            fail('product "' + p['title'] + '"', str(e))


def offers(cat, arbiter):
    """The offer body of each product, in catalog order. Products take the shop's unit, allow and terms unless
    they give their own; the currency and the payment methods are the shop's."""
    s = cat['shop']
    out = []
    for p in cat.get('products', []):
        body = {'item': {'title': p['title'], 'text': p.get('text', ''), 'media': p.get('media', [])},
                'quantity': p['quantity'], 'unit': p.get('unit', s.get('unit', 'unit')), 'currency': s['currency'],
                'price': p['price'], 'allow': p.get('allow', s.get('allow', 'any')), 'pay': s['pay'],
                'arbiter': s.get('arbiter', arbiter), 'terms': p.get('terms', s.get('terms', ''))}
        if 'expires' in p:
            body['expires'] = p['expires']
        out.append(body)
    return out


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'shop'


def publishing(s):
    """The "publish" settings of config.json that the catalog asks for, or None, and the shop's web address."""
    if 'repo' in s:
        owner, name = s['repo'].split('/')
        url = 'https://' + owner.lower() + '.github.io'
        if name.lower() != owner.lower() + '.github.io':
            url += '/' + name
        pub = {'dest': 'git@github.com:' + s['repo'] + '.git', 'branch': s.get('branch', 'main')}
    elif 'dest' in s:
        url, pub = '', {'dest': s['dest'], 'branch': s.get('branch', 'main')}
    elif 'folder' in s:
        return {'method': 'folder', 'path': s['folder']}, s.get('url', '')
    else:
        return None, s.get('url', '')
    if 'site_path' in s:
        pub['site_path'] = s['site_path'].strip('/')
        url += ('/' + pub['site_path']) if url else ''
    return pub, s.get('url', url)


def configure(dex, pub, root):
    """Write the catalog's publish settings and root into config.json. The root of a dex is pinned: another root
    is refused."""
    from .cli import read_json, write_json
    path = os.path.join(dex, 'config.json')
    cfg = read_json(path)
    if pub is not None:
        old = cfg.get('publish') if isinstance(cfg.get('publish'), dict) else {}
        cfg['publish'] = dict(pub, append_only=old.get('append_only', [LEDGER]))
    if root:
        lc = cfg.setdefault('ledgdex', {})
        if lc.get('root') not in (None, root):
            raise Invalid(dex + ' trades under the root ' + lc['root'] + ', not ' + root)
        lc['root'] = root
    write_json(path, cfg)
    if root:
        load_root(dex)   # pins the root by its ledger id on this first read


def shop(catalog, dex=None, repo=None, publish=True, log=print):
    """Make or update the shop of `catalog` (a file name or a dict) in the dex folder `dex` (default: the shop name
    in lowercase, with "-" between words). `repo` (OWNER/NAME) replaces the catalog's repo, dest, folder and url. Returns
    {"dex", "ledger", "url", "kept", "offered", "withdrawn", "published"}."""
    from .cli import key_or_new, next_at, read_json
    from .publish import publish as publish_dex
    cat = read_json(catalog) if isinstance(catalog, str) else catalog
    if repo is not None:
        if not isinstance(cat, dict) or not isinstance(cat.get('shop'), dict):
            check_catalog(cat)
        cat = dict(cat, shop={k: v for k, v in cat['shop'].items() if k not in ('dest', 'folder', 'url')})
        cat['shop']['repo'] = repo
    check_catalog(cat)
    s = cat['shop']
    dex = dex or slug(s['name'])
    pub, url = publishing(s)
    if not os.path.exists(os.path.join(dex, LEDGER)):
        key = s.get('key') or slug(s['name'])
        secret, made = key_or_new(key)
        if made:
            log('new key ' + key + ' in ~/.ledgdex')
        led = new_ledger(secret, s['name'], s.get('about', ''), url)
        create_dex(dex, led.data, s['name'], pub)
        log('shop created in ' + dex + '. Ledger id: ' + led.id)
    led = load(dex)
    if led.header['name'] != s['name']:
        raise Invalid(dex + ' holds the ledger of "' + led.header['name'] + '", not of "' + s['name'] + '"')
    configure(dex, pub, s.get('root'))
    root = load_root(dex)
    led = load(dex, root=root)
    arbiter = {'key': root.owner, 'url': root.dex} if root else {'key': led.owner, 'url': led.dex}
    wanted = {canon(b): b for b in offers(cat, arbiter)}
    entries = dict(zip(led.ids, led.entries))
    have, withdraw = set(), []
    for id_, o in state(led, root=root)['offers'].items():
        key = canon(entries[id_]['msg']['body'])
        if o['status'] in ('open', 'sold') and key in wanted and key not in have:
            have.add(key)
        elif o['status'] == 'open':
            withdraw.append(id_)
    new = [b for k, b in wanted.items() if k not in have]
    if withdraw or new:
        secret = signer(led)
        at = next_at(led, secret)
        record(dex, [message(secret, 'withdraw', {'offer': i}, at=at) for i in withdraw] +
               [message(secret, 'offer', b, at=at) for b in new])
    render(dex)
    log('shop: ' + str(len(have)) + ' offers kept, ' + str(len(new)) + ' offered, ' + str(len(withdraw)) +
        ' withdrawn')
    done = False
    if publish and pub is not None:
        if not publish_dex(dex):
            raise Invalid('the shop is ready in ' + dex + ', but the publish failed. Run "ledgdex publish ' + dex +
                          '" again')
        done = True
        log('shop published' + (': ' + led.dex if led.dex else ''))
    elif publish:
        log('not published: the catalog gives no "repo", "dest" or "folder"')
    return {'dex': dex, 'ledger': led.id, 'url': led.dex, 'kept': len(have), 'offered': len(new),
            'withdrawn': len(withdraw), 'published': done}

"""ledgdex command-line tool (spec Part III). Run "ledgdex -h"."""
import argparse, json, os, sys
from .canon import canon, hash_, ID_KEY
from .core import Invalid, KEY_TYPES, OWNER_ONLY, message, new_ledger, public, is_key
from .dex import LEDGER, fetch, keygen, key_dir, load, load_key, record, signer, write
from .render import render
from .state import state

OFFER_DEFAULTS = {'unit': 'unit', 'allow': 'any', 'pay': [], 'terms': ''}
RECORDABLE = ('claim', 'paid', 'confirmed', 'dispute', 'ruling', 'bid', 'reveal')


def out(obj):
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_msg(m, path):
    path = path or m['type'] + '-' + hash_(m)[7:19] + '.json'
    with open(path, 'wb') as f:
        f.write(canon(m) + b'\n')
    return path


def owner(dex):
    led = load(dex)
    return led, signer(led)


def add(dex, type_, body):
    """Sign a message for this dex's own ledger (with a device key when this machine has one, the owner key for
    owner-only types), record it, render."""
    led = load(dex)
    secret = signer(led, owner_only=type_ in OWNER_ONLY)
    ids = record(dex, [message(secret, type_, body)])
    render(dex)
    print(type_ + ' recorded: ' + ids[0])
    return ids[0]


def seller_ledger(src):
    led, url = fetch(src)
    if not led.whole:
        raise Invalid('the seller ledger is broken: ' + str(led.error))
    dex_url = led.entries[0]['msg']['body']['dex'] if led.entries else ''
    return led, (src if src.startswith(('http://', 'https://')) else dex_url or src)


def claim_id(seller, ref):
    """The seller's entry id for a claim, given that id or the id of the claim message."""
    if seller.find(ref) is not None:
        return ref
    for n, e in enumerate(seller.entries):
        if hash_(e['msg']) == ref:
            return seller.ids[n]
    raise Invalid('the seller ledger has no entry ' + ref + '. Has the seller recorded your claim?')


def send(dex, to, type_, body, path):
    """Sign a message for another ledger, keep a "sent" copy, write the message file. Messages to other ledgers
    are signed with the owner key: it is this self's identity there."""
    led = load(dex)
    m = message(signer(led, owner_only=True), type_, body)
    record(dex, [message(signer(led), 'sent', {'to': to, 'msg': m})])
    render(dex)
    p = save_msg(m, path)
    print(type_ + ' signed and kept as "sent". Send ' + p + ' to the ledger owner, or publish your dex: they can '
          'collect it with "ledgdex record THEIR_DEX --from YOUR_DEX_URL"')
    return m


# ---------- commands ----------

def c_keygen(a):
    print(keygen(a.name))


def c_init(a):
    from dexweb import dexgen
    dex = a.dex
    if os.path.exists(os.path.join(dex, LEDGER)):
        raise Invalid(dex + ' already has a ledger')
    try:
        secret = load_key(a.key)
    except Invalid:
        keygen(a.key)
        secret = load_key(a.key)
        print('new key ' + a.key + ': ' + public(secret))
    os.makedirs(dex, exist_ok=True)
    led = new_ledger(secret, a.name, a.about, a.url)
    write(dex, led.data)
    cfg_path = os.path.join(dex, 'config.json')
    if os.path.exists(cfg_path):
        cfg = read_json(cfg_path)
    else:
        g = dexgen.Dexgen.__new__(dexgen.Dexgen)
        g.dexname = a.dexname or a.name
        g.save_dexname_in_config(dex, g.dexname)  # dexweb's own default template
        cfg = read_json(cfg_path)
    pub = cfg.get('publish') if isinstance(cfg.get('publish'), dict) else {}
    pub['append_only'] = sorted(set(pub.get('append_only', [])) | {LEDGER})
    if a.dest:
        pub['dest'] = a.dest
    if a.branch:
        pub['branch'] = a.branch
    if a.site_path:
        pub['site_path'] = a.site_path
    cfg['publish'] = pub
    with open(cfg_path, 'w') as f:
        f.write(json.dumps(cfg, indent=4))
    if not os.path.exists(os.path.join(dex, 'data.json')):
        with open(os.path.join(dex, 'data.json'), 'w') as f:
            f.write('[]')
    if not os.path.exists(os.path.join(dex, 'run.py')):
        with open(os.path.join(dex, 'run.py'), 'w') as f:
            f.write('from dexweb import dexgen\ndex = dexgen.Dexgen()\n')
    render(dex)
    print('ledgdex created in ' + dex + '. Ledger id: ' + led.id)


def c_offer(a):
    led, secret = owner(a.dex)
    body = read_json(a.file)
    for k, v in OFFER_DEFAULTS.items():
        body.setdefault(k, v)
    body.setdefault('arbiter', {'key': led.owner, 'url': led.entries[0]['msg']['body']['dex']})
    if isinstance(body.get('item'), dict):
        body['item'].setdefault('text', '')
        body['item'].setdefault('media', [])
    add(a.dex, 'offer', body)


def c_withdraw(a):
    add(a.dex, 'withdraw', {'offer': a.offer})


def c_received(a):
    add(a.dex, 'received', {'claim': a.claim, 'amount': a.amount})


def c_delivered(a):
    add(a.dex, 'delivered', {'claim': a.claim, 'note': a.note})


def c_admit(a):
    add(a.dex, 'admit', {'key': a.key, 'name': a.name, 'note': a.note})


def c_revoke(a):
    add(a.dex, 'revoke', {'key': a.key, 'reason': a.reason})


def c_note(a):
    add(a.dex, 'note', {'ref': a.ref, 'text': a.text})


def c_record(a):
    """Seller side: record messages from files, or collect the "sent" messages addressed to this ledger."""
    led = load(a.dex)
    msgs = [read_json(p) for p in a.files]
    for src in a.sources or []:
        other, _ = fetch(src)
        msgs += [e['msg']['body']['msg'] for e in other.entries
                 if e['msg']['type'] == 'sent' and e['msg']['body']['to'] in led.key_history
                 and e['msg']['body']['msg']['by'] in other.key_history]
    have = {hash_(e['msg']) for e in led.entries}
    new = []
    for m in msgs:
        h = hash_(m)
        if h not in have and m['type'] in RECORDABLE:
            have.add(h)
            new.append(m)
    if not new:
        print('nothing new to record')
        return
    ids = record(a.dex, new)
    render(a.dex)
    st = state(load(a.dex))
    for m, i in zip(new, ids):
        c = st['claims'].get(i)
        print(m['type'] + ' recorded: ' + i + ('' if c is None else ' (' + c['status'] +
                                                (', ' + c['reason'] if 'reason' in c else '') + ')'))


def c_claim(a):
    seller, _ = seller_ledger(a.seller)
    if seller.id == load(a.dex).id:
        raise Invalid('you cannot buy from your own ledger')
    st = state(seller)
    n = seller.find(a.offer)
    if n is None or seller.entries[n]['msg']['type'] != 'offer':
        raise Invalid('no offer ' + a.offer + ' in that ledger')
    o, m = st['offers'][a.offer], seller.entries[n]['msg']
    if o['status'] != 'open' or a.quantity > o['remaining']:
        raise Invalid('the offer is ' + o['status'] + ' with ' + str(o['remaining']) + ' left')
    send(a.dex, seller.owner, 'claim', {'offer': a.offer, 'offer_hash': hash_(m), 'quantity': a.quantity,
                                        'price': m['body']['price']}, a.output)


def c_pay(a):
    seller, _ = seller_ledger(a.seller)
    send(a.dex, seller.owner, 'paid', {'claim': claim_id(seller, a.claim), 'method': a.method, 'ref': a.ref},
         a.output)


def c_confirm(a):
    seller, _ = seller_ledger(a.seller)
    send(a.dex, seller.owner, 'confirmed', {'claim': claim_id(seller, a.claim)}, a.output)


def c_receipt(a):
    """Buyer side: keep the seller's entries that record this self's messages (the third entry)."""
    led = load(a.dex)
    seller, url = seller_ledger(a.seller)
    held = {hash_(e['msg']['body']['entry']) for e in led.entries if e['msg']['type'] == 'receipt'}
    mine = {hash_(e['msg']['body']['msg']) for e in led.entries if e['msg']['type'] == 'sent'}
    chain = [e for e in seller.entries if e['msg']['type'] in KEY_TYPES]
    picked = []
    for n, e in enumerate(seller.entries):
        if (a.entry and seller.ids[n] != a.entry) or seller.ids[n] in held:
            continue
        if a.entry or hash_(e['msg']) in mine:
            if e['msg']['by'] not in led.key_history:
                raise Invalid('entry ' + seller.ids[n] + ' does not record a message of yours')
            picked.append(e)
    if not picked:
        print('no new receipts')
        return
    secret = signer(led)

    def body(e):
        b = {'ledger': seller.id, 'url': url, 'header': seller.header, 'entry': e}
        keys = [k for k in chain if k['seq'] < e['seq']]
        if keys:
            b['keys'] = keys
        return b
    record(a.dex, [message(secret, 'receipt', body(e)) for e in picked])
    render(a.dex)
    for e in picked:
        line = 'receipt kept for your ' + e['msg']['type'] + ': seller entry ' + str(e['seq'])
        if e['msg']['type'] == 'claim':
            line += '. Claim id: ' + hash_(e)
        print(line)


def c_sign(a):
    m = message(load_key(a.key), a.type, read_json(a.file))
    sys.stdout.write(canon(m).decode('utf-8') + '\n')


def c_verify(a):
    from .sig import backend
    led, _ = fetch(a.ledger, cache=not a.full, root=root_of(a))
    if led.whole:
        print('whole: ' + str(len(led.entries)) + ' entries, ledger ' + str(led.id) + ' (' +
              (str(led.cached) + ' entries from the cache, ' if led.cached else '') + backend.name + ' Ed25519)')
        return
    print('broken' + ('' if led.broken_at is None else ' at seq ' + str(led.broken_at)) + ': ' + str(led.error))
    sys.exit(1)


def c_state(a):
    root = root_of(a)
    led, _ = fetch(a.ledger, root=root)
    if led.header is None:
        raise Invalid(str(led.error))
    sys.stdout.write(canon(state(led, root=root), ID_KEY).decode('utf-8') + '\n')


def c_render(a):
    render(a.dex)
    print('rendered ' + a.dex)


def c_check(a):
    import time
    from .check import check
    sources = a.sources or ['.']
    while True:
        report = check(sources, a.state, media=a.media, published=a.published, root=a.root,
                       log=(lambda line: None) if a.quiet else print)
        if a.json:
            with open(a.json, 'w') as f:
                f.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(report['time'] + ' ' + ('ok' if report['ok'] else 'FAILED') + ': ' + str(len(report['checked'])) +
              ' ledgers checked, ' + str(report['errors']) + ' errors, ' + str(report['warnings']) + ' warnings')
        sys.stdout.flush()
        if not a.every:
            if not report['ok']:
                sys.exit(1)
            return
        time.sleep(a.every)


def c_workflow(a):
    from .check import workflow
    sys.stdout.write(workflow(a.sources, a.cron, a.media))


def c_publish(a):
    from .publish import publish
    if not publish(a.dex):
        sys.exit(1)


def root_of(a):
    return fetch(a.root)[0] if getattr(a, 'root', None) else None


def key_arg(k):
    """A public key, or the name of a key in ~/.ledgdex."""
    return k if is_key(k) else public(load_key(k))


def new_or_existing_key(name):
    try:
        return load_key(name)
    except Invalid:
        keygen(name)
        return load_key(name)


# ---------- keys (spec 5.1, 5.7) ----------

def c_device(a):
    if a.action == 'add':
        add(a.dex, 'device', {'key': key_arg(a.key), 'name': a.name})
    else:
        add(a.dex, 'device_revoke', {'key': key_arg(a.key), 'reason': a.reason})


def c_rotate(a):
    new = new_or_existing_key(a.key)
    add(a.dex, 'rotate', {'key': public(new)})
    print('the owner key is now ' + public(new) + ' (' + a.key + ')')


def c_recover(a):
    """Root side: name a new key for a ledger whose owner lost theirs."""
    other, _ = fetch(a.ledger)
    if other.header is None:
        raise Invalid('not a ledger: ' + str(other.error))
    add(a.dex, 'recover', {'ledger': other.id, 'key': key_arg(a.key)})


def c_recovered(a):
    """Owner side: take the ledger back with the key the root named."""
    root, _ = fetch(a.root)
    led = load(a.dex, root=root)
    new = load_key(a.key)
    rid = None
    for n, e in enumerate(root.entries):
        b = e['msg']['body']
        if e['msg']['type'] == 'recover' and b['ledger'] == led.id and b['key'] == public(new):
            rid = root.ids[n]
    if rid is None:
        raise Invalid('the root has no recover entry for this ledger and key ' + public(new))
    cfg_path = os.path.join(a.dex, 'config.json')
    cfg = read_json(cfg_path)
    cfg.setdefault('ledgdex', {})['root'] = a.root   # every later read of this ledger needs the root
    with open(cfg_path, 'w') as f:
        f.write(json.dumps(cfg, indent=4))
    record(a.dex, [message(new, 'recovered', {'root': root.id, 'entry': rid})], secret=new)
    render(a.dex)
    print('recovered: the owner key is now ' + public(new))


# ---------- disputes (spec 5.5) ----------

def c_dispute(a):
    body = {'claim': a.claim, 'text': a.text, 'evidence': a.evidence or []}
    if a.seller:   # the buyer disputes in the seller's ledger
        seller, _ = seller_ledger(a.seller)
        body['claim'] = claim_id(seller, a.claim)
        send(a.dex, seller.owner, 'dispute', body, a.output)
    else:          # the seller disputes in its own ledger
        add(a.dex, 'dispute', body)


def c_ruling(a):
    seller, _ = seller_ledger(a.seller)
    st = state(seller)
    if a.dispute not in st['disputes']:
        raise Invalid('no dispute ' + a.dispute + ' in that ledger')
    send(a.dex, seller.owner, 'ruling', {'dispute': a.dispute, 'outcome': a.outcome, 'text': a.text}, a.output)


# ---------- auctions (spec 5.6) ----------

def c_auction(a):
    led = load(a.dex)
    body = read_json(a.file)
    for k, v in (('allow', 'any'), ('terms', ''), ('best', 'highest'), ('reserve', 0)):
        body.setdefault(k, v)
    body.setdefault('arbiter', {'key': led.owner, 'url': led.entries[0]['msg']['body']['dex']})
    if isinstance(body.get('item'), dict):
        body['item'].setdefault('text', '')
        body['item'].setdefault('media', [])
    add(a.dex, 'auction', body)


def bid_path(led, auction):
    return os.path.join(key_dir(), 'bids', led.id[7:19] + '-' + auction[7:] + '.json')


def c_bid(a):
    from .core import now
    led = load(a.dex)
    seller, _ = seller_ledger(a.seller)
    st = state(seller, now=now())
    if st['auctions'].get(a.auction, {}).get('status') != 'open':
        raise Invalid('no open auction ' + a.auction + ' in that ledger')
    path = bid_path(led, a.auction)
    if os.path.exists(path):
        raise Invalid('you already bid in this auction (one bid per key)')
    nonce = os.urandom(32).hex()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:   # the amount stays private until the reveal
        json.dump({'auction': a.auction, 'ledger': seller.id, 'amount': a.amount, 'nonce': nonce}, f)
    send(a.dex, seller.owner, 'bid', {'auction': a.auction, 'commit': hash_({'amount': a.amount, 'nonce': nonce})},
         a.output)


def c_reveal(a):
    led = load(a.dex)
    seller, _ = seller_ledger(a.seller)
    path = bid_path(led, a.auction)
    if not os.path.exists(path):
        raise Invalid('no bid of yours for ' + a.auction + ' on this machine')
    saved = read_json(path)
    send(a.dex, seller.owner, 'reveal', {'auction': a.auction, 'amount': saved['amount'], 'nonce': saved['nonce']},
         a.output)


# ---------- indexes (spec 5.7) ----------

def c_list(a):
    other, url = fetch(a.ledger)
    if not other.whole:
        raise Invalid('that ledger is broken: ' + str(other.error))
    dex_url = other.entries[0]['msg']['body']['dex'] if other.entries else ''
    add(a.dex, 'list', {'ledger': other.id, 'url': a.url or dex_url or a.ledger, 'owner': other.owner,
                        'note': a.note})


def c_delist(a):
    add(a.dex, 'delist', {'ledger': a.ledger, 'reason': a.reason})


def c_discover(a):
    """Read an index: the ledgers it lists, and with --offers their open offers and auctions."""
    idx, _ = fetch(a.index)
    found = []
    for lid, l in state(idx)['listings'].items():
        item = {'ledger': lid, 'url': l['url'], 'owner': l['owner'], 'note': l['note']}
        if a.offers:
            try:
                led, _ = fetch(l['url'])
                if led.id != lid:
                    item['error'] = 'that address serves another ledger'
                else:
                    st = state(led)
                    item['offers'] = [dict(id=i, **o) for i, o in st['offers'].items() if o['status'] == 'open']
                    item['auctions'] = [dict(id=i, **x) for i, x in st['auctions'].items() if x['status'] == 'open']
            except Exception as e:
                item['error'] = str(e)
        found.append(item)
    if a.json:
        out(found)
        return
    for f in found:
        print(f['url'] + '  ' + f['ledger'] + ('  ' + f['note'] if f['note'] else ''))
        for o in f.get('offers', []):
            print('  offer ' + o['id'] + '  ' + o['title'] + '  ' + str(o['remaining']) + ' left')
        for x in f.get('auctions', []):
            print('  auction ' + x['id'] + '  ' + str(x['bids']) + ' bids')
        if 'error' in f:
            print('  ' + f['error'])


def parser():
    p = argparse.ArgumentParser(prog='ledgdex', description='Ledgdex: a simple market on a dex. Spec: architecture/SPEC.md')
    s = p.add_subparsers(dest='cmd', required=True)

    def cmd(name, fn, help_, *args):
        c = s.add_parser(name, help=help_, description=help_)
        for names, kw in args:
            c.add_argument(*names, **kw)
        c.set_defaults(fn=fn)

    D = (['dex'], {'help': 'the dex folder'})
    S = (['seller'], {'help': "the seller's dex URL, dex folder or ledger file"})
    O = (['-o', '--output'], {'help': 'where to write the message file'})
    cmd('keygen', c_keygen, 'make a key in ~/.ledgdex and print its public key', (['name'], {}))
    cmd('init', c_init, 'make a ledgdex: a complete dex with a new ledger', D,
        (['--name'], {'required': True, 'help': 'your name, shown on the ledger'}),
        (['--about'], {'default': '', 'help': 'one line about you or your shop'}),
        (['--url'], {'default': '', 'help': "this dex's web address"}),
        (['--key'], {'required': True, 'help': 'key name in ~/.ledgdex (made if missing)'}),
        (['--dexname'], {'help': 'dex name (default: --name)'}),
        (['--dest'], {'help': 'repository address to publish to'}),
        (['--branch'], {'help': 'branch to publish to'}),
        (['--site-path'], {'dest': 'site_path', 'help': 'folder in the repository to publish to (default: its root)'}))
    cmd('offer', c_offer, 'sell something: sign and record an offer from a JSON file', D, (['file'], {}))
    cmd('withdraw', c_withdraw, 'withdraw an offer', D, (['offer'], {}))
    cmd('record', c_record, 'record claims, payments and confirmations from buyers', D,
        (['files'], {'nargs': '*', 'help': 'message files'}),
        (['--from'], {'dest': 'sources', 'action': 'append', 'help': "a buyer's dex: collect what they sent you"}))
    cmd('received', c_received, 'record that a payment arrived', D, (['claim'], {}), (['amount'], {'type': int}))
    cmd('delivered', c_delivered, 'record delivery', D, (['claim'], {}), (['--note'], {'default': ''}))
    cmd('admit', c_admit, 'admit a key (for offers with "allow": "admitted")', D, (['key'], {}),
        (['--name'], {'default': ''}), (['--note'], {'default': ''}))
    cmd('revoke', c_revoke, 'revoke an admitted key', D, (['key'], {}), (['--reason'], {'default': ''}))
    cmd('note', c_note, 'add a remark about an earlier entry', D, (['ref'], {}), (['text'], {}))
    cmd('claim', c_claim, "buy: sign a claim for a seller's offer", D, S, (['offer'], {}),
        (['--quantity'], {'type': int, 'default': 1}), O)
    cmd('pay', c_pay, 'tell the seller you paid', D, S, (['claim'], {'help': 'claim id (or your claim message id)'}),
        (['--method'], {'required': True}), (['--ref'], {'default': ''}), O)
    cmd('confirm', c_confirm, 'confirm you received the goods', D, S, (['claim'], {}), O)
    cmd('receipt', c_receipt, "keep the seller's records of your messages as receipts", D, S,
        (['--entry'], {'help': 'only this entry id'}))
    R = (['--root'], {'help': 'the root ledger (dex, file or URL)'})
    cmd('device', c_device, 'add or revoke a device key (needs the owner key)', (['action'], {'choices': ['add', 'revoke']}),
        D, (['key'], {'help': 'public key, or the name of a key in ~/.ledgdex'}), (['--name'], {'default': ''}),
        (['--reason'], {'default': ''}))
    cmd('rotate', c_rotate, 'replace the owner key (signed by the old one)', D,
        (['--key'], {'required': True, 'help': 'name of the new key in ~/.ledgdex (made if missing)'}))
    cmd('recover', c_recover, "root: name a new key for a ledger whose owner lost theirs", D,
        (['ledger'], {'help': 'the ledger (dex, file or URL)'}), (['key'], {'help': 'the new public key'}))
    cmd('recovered', c_recovered, 'take a ledger back with the key the root named', D,
        (['--root'], {'required': True}), (['--key'], {'required': True, 'help': 'name of the new key'}))
    cmd('dispute', c_dispute, 'open a dispute about a claim', D, (['claim'], {}), (['--text'], {'default': ''}),
        (['--evidence'], {'action': 'append', 'help': 'an entry id or URL (repeatable)'}),
        (['--seller'], {'help': "buyer: the seller's dex (without it, a dispute in your own ledger)"}), O)
    cmd('ruling', c_ruling, "arbiter: rule on a dispute in a seller's ledger", D, S, (['dispute'], {}),
        (['--outcome'], {'required': True, 'choices': ['release', 'refund', 'split']}), (['--text'], {'default': ''}), O)
    cmd('auction', c_auction, 'start a sealed-bid auction from a JSON file', D, (['file'], {}))
    cmd('bid', c_bid, "bid in a seller's auction (the amount stays secret until you reveal)", D, S, (['auction'], {}),
        (['--amount'], {'type': int, 'required': True}), O)
    cmd('reveal', c_reveal, 'reveal your bid after the auction closes', D, S, (['auction'], {}), O)
    cmd('list', c_list, 'index: list a ledger', D, (['ledger'], {'help': 'dex, file or URL'}),
        (['--url'], {'help': 'address to list (default: its dex address)'}), (['--note'], {'default': ''}))
    cmd('delist', c_delist, 'index: delist a ledger', D, (['ledger'], {'help': 'ledger id'}), (['--reason'], {'default': ''}))
    cmd('discover', c_discover, 'read an index: listed ledgers, and with --offers what they sell',
        (['index'], {'help': 'the index (dex, file or URL)'}), (['--offers'], {'action': 'store_true'}),
        (['--json'], {'action': 'store_true'}))
    cmd('sign', c_sign, 'print a signed message (advanced)', (['type'], {}), (['file'], {}),
        (['--key'], {'required': True}))
    cmd('verify', c_verify, 'check a ledger; exit code 0 only if whole', (['ledger'], {'help': 'dex, file or URL'}),
        (['--full'], {'action': 'store_true', 'help': 'verify every line, ignoring the verification cache'}), R)
    cmd('state', c_state, "print a ledger's state", (['ledger'], {'help': 'dex, file or URL'}), R)
    cmd('render', c_render, 'rewrite the generated pages and rebuild the site', D)
    cmd('check', c_check, 'check ledgers for tampering over time: rewrites, missing receipts, changed addresses',
        (['sources'], {'nargs': '*', 'help': 'ledgers to check: dex folders, files or URLs (default: this folder)'}),
        (['--state'], {'default': '.ledgdex-check', 'help': 'where last-seen copies and proofs are kept'}),
        (['--media'], {'action': 'store_true', 'help': 'also fetch offer media and check their hashes'}),
        (['--published'], {'action': 'store_true', 'help': 'for dex folders: compare with the published ledger'}),
        (['--json'], {'help': 'write the report as JSON to this file'}),
        (['--every'], {'type': int, 'help': 'run as a worker: check again every this many seconds'}),
        (['--quiet'], {'action': 'store_true', 'help': 'print only the summary line'}), R)
    cmd('workflow', c_workflow, 'print a GitHub Actions workflow that runs ledgdex check',
        (['sources'], {'nargs': '+', 'help': 'ledger files in the repository, or URLs'}),
        (['--cron'], {'default': '17 6 * * *', 'help': 'schedule (UTC cron)'}),
        (['--media'], {'action': 'store_true'}))
    cmd('publish', c_publish, 'publish the dex with dexweb (catches up with other devices)', D)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        a.fn(a)
    except Invalid as e:
        print('ledgdex: ' + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

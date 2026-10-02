"""ledgdex command-line tool (spec Part III). Run "ledgdex -h"."""
import argparse, json, os, sys, time
from .canon import canon, hash_, ID_KEY
from .core import Invalid, KEY_TYPES, OWNER_ONLY, message, new_ledger, now, public, is_id, is_key
from .dex import LEDGER, fetch, keygen, key_dir, load, load_key, load_root, record, signer
from .render import render
from .state import state

RECORDABLE = ('claim', 'paid', 'confirmed', 'dispute', 'ruling', 'bid', 'reveal')


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, obj):
    with open(path, 'w') as f:
        f.write(json.dumps(obj, indent=4))


def key_or_new(name):
    """The secret key NAME in ~/.ledgdex, made if missing. Returns (secret, made)."""
    try:
        return load_key(name), False
    except Invalid:
        keygen(name)
        return load_key(name), True


def id_arg(s):
    """An id on the command line: sha256: and 64 lowercase hex digits (ids also name files, so nothing else)."""
    if not is_id(s):
        raise argparse.ArgumentTypeError('not an id (sha256: and 64 hex digits): ' + s)
    return s


def key_arg(k):
    """A public key, or the name of a key in ~/.ledgdex."""
    return k if is_key(k) else public(load_key(k))


def add(dex, type_, body):
    """Sign a message for this dex's own ledger (with a device key when this machine has one, the owner key for
    owner-only types), record it, render."""
    secret = signer(load(dex), owner_only=type_ in OWNER_ONLY)
    i = record(dex, [message(secret, type_, body)])[0]
    render(dex)
    print(type_ + ' recorded: ' + i)
    return i


def with_defaults(dex, body, defaults):
    """An offer or auction body from a file, with the fields a seller usually leaves out. The default arbiter is the
    root's owner when the dex names its root (spec, Decision 2), else the seller itself."""
    led = load(dex)
    for k, v in defaults.items():
        body.setdefault(k, v)
    if 'arbiter' not in body:
        root = load_root(dex)
        body['arbiter'] = {'key': root.owner, 'url': root.dex} if root else {'key': led.owner, 'url': led.dex}
    if isinstance(body.get('item'), dict):
        body['item'].setdefault('text', '')
        body['item'].setdefault('media', [])
    return body


def other(src, what='the seller ledger', root=None):
    """Another ledger, which must be whole, and the address to cite it by."""
    led, _ = fetch(src, root=root)
    if not led.whole:
        raise Invalid(what + ' is broken: ' + str(led.error))
    return led, (src if src.startswith(('http://', 'https://')) else led.dex or src)


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
    path = path or m['type'] + '-' + hash_(m)[7:19] + '.json'
    with open(path, 'wb') as f:
        f.write(canon(m) + b'\n')
    print(type_ + ' signed and kept as "sent". Send ' + path + ' to the ledger owner, or publish your dex: they can '
          'collect it with "ledgdex record THEIR_DEX --from YOUR_DEX_URL"')


def bid_path(led, auction):
    return os.path.join(key_dir(), 'bids', led.id[7:19] + '-' + auction[7:] + '.json')


def root_of(a):
    return fetch(a.root)[0] if getattr(a, 'root', None) else None


# ---------- commands ----------

def c_keygen(a):
    print(keygen(a.name))


def c_init(a):
    from .render import create_dex
    if os.path.exists(os.path.join(a.dex, LEDGER)):
        raise Invalid(a.dex + ' already has a ledger')
    secret, made = key_or_new(a.key)
    if made:
        print('new key ' + a.key + ': ' + public(secret))
    led = new_ledger(secret, a.name, a.about, a.url)
    create_dex(a.dex, led.data, a.dexname or a.name,
               {k: v for k, v in (('dest', a.dest), ('branch', a.branch), ('site_path', a.site_path)) if v})
    print('ledgdex created in ' + a.dex + '. Ledger id: ' + led.id)


def c_offer(a):
    add(a.dex, 'offer', with_defaults(a.dex, read_json(a.file), {'unit': 'unit', 'allow': 'any', 'pay': [], 'terms': ''}))


def c_auction(a):
    add(a.dex, 'auction', with_defaults(a.dex, read_json(a.file),
                                        {'allow': 'any', 'terms': '', 'best': 'highest', 'reserve': 0}))


# commands that record one message, built from the arguments, in the dex's own ledger
SIMPLE = {
    'withdraw': ('withdraw an offer', [(['offer'], {'type': id_arg})], lambda a: ('withdraw', {'offer': a.offer})),
    'received': ('record that a payment arrived', [(['claim'], {'type': id_arg}), (['amount'], {'type': int})],
                 lambda a: ('received', {'claim': a.claim, 'amount': a.amount})),
    'delivered': ('record delivery', [(['claim'], {'type': id_arg}), (['--note'], {'default': ''})],
                  lambda a: ('delivered', {'claim': a.claim, 'note': a.note})),
    'admit': ('admit a key (for offers with "allow": "admitted")',
              [(['key'], {}), (['--name'], {'default': ''}), (['--note'], {'default': ''})],
              lambda a: ('admit', {'key': a.key, 'name': a.name, 'note': a.note})),
    'revoke': ('revoke an admitted key', [(['key'], {}), (['--reason'], {'default': ''})],
               lambda a: ('revoke', {'key': a.key, 'reason': a.reason})),
    'note': ('add a remark about an earlier entry', [(['ref'], {'type': id_arg}), (['text'], {})],
             lambda a: ('note', {'ref': a.ref, 'text': a.text})),
    'delist': ('index: delist a ledger', [(['ledger'], {'type': id_arg, 'help': 'ledger id'}), (['--reason'], {'default': ''})],
               lambda a: ('delist', {'ledger': a.ledger, 'reason': a.reason})),
    'device': ('add or revoke a device key (needs the owner key)',
               [(['action'], {'choices': ['add', 'revoke']}), (['key'], {'help': 'public key, or the name of a key '
                                                                         'in ~/.ledgdex'}),
                (['--name'], {'default': ''}), (['--reason'], {'default': ''})],
               lambda a: ('device', {'key': key_arg(a.key), 'name': a.name}) if a.action == 'add' else
               ('device_revoke', {'key': key_arg(a.key), 'reason': a.reason})),
}


def c_record(a):
    """Seller side: record messages from files, or collect the "sent" messages addressed to this ledger."""
    led = load(a.dex)
    msgs = [read_json(p) for p in a.files]
    for src in a.sources or []:
        o, _ = fetch(src)
        msgs += [e['msg']['body']['msg'] for e in o.entries
                 if e['msg']['type'] == 'sent' and e['msg']['body']['to'] in led.key_history
                 and e['msg']['body']['msg']['by'] in o.key_history]
    have, new = {hash_(e['msg']) for e in led.entries}, []
    for m in msgs:
        if hash_(m) not in have and m['type'] in RECORDABLE:
            have.add(hash_(m))
            new.append(m)
    if not new:
        print('nothing new to record')
        return
    ids = record(a.dex, new)
    render(a.dex)
    claims = state(load(a.dex))['claims']
    for m, i in zip(new, ids):
        c = claims.get(i)
        print(m['type'] + ' recorded: ' + i + ('' if c is None else ' (' + c['status'] +
                                                (', ' + c['reason'] if 'reason' in c else '') + ')'))


def c_claim(a):
    seller, _ = other(a.seller)
    if seller.id == load(a.dex).id:
        raise Invalid('you cannot buy from your own ledger')
    n = seller.find(a.offer)
    if n is None or seller.entries[n]['msg']['type'] != 'offer':
        raise Invalid('no offer ' + a.offer + ' in that ledger')
    o, m = state(seller)['offers'][a.offer], seller.entries[n]['msg']
    if o['status'] != 'open' or a.quantity > o['remaining']:
        raise Invalid('the offer is ' + o['status'] + ' with ' + str(o['remaining']) + ' left')
    send(a.dex, seller.owner, 'claim', {'offer': a.offer, 'offer_hash': hash_(m), 'quantity': a.quantity,
                                        'price': m['body']['price']}, a.output)


def c_pay(a):
    seller, _ = other(a.seller)
    send(a.dex, seller.owner, 'paid', {'claim': claim_id(seller, a.claim), 'method': a.method, 'ref': a.ref}, a.output)


def c_confirm(a):
    seller, _ = other(a.seller)
    send(a.dex, seller.owner, 'confirmed', {'claim': claim_id(seller, a.claim)}, a.output)


def c_receipt(a):
    """Buyer side: keep the seller's entries that record this self's messages (the third entry)."""
    led = load(a.dex)
    seller, url = other(a.seller, root=led.root)
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

    def body(e):
        b = {'ledger': seller.id, 'url': url, 'header': seller.header, 'entry': e}
        keys = [k for k in chain if k['seq'] < e['seq']]
        return dict(b, keys=keys) if keys else b
    secret = signer(led)
    record(a.dex, [message(secret, 'receipt', body(e), root=led.root) for e in picked])
    render(a.dex)
    for e in picked:
        print('receipt kept for your ' + e['msg']['type'] + ': seller entry ' + str(e['seq']) +
              ('. Claim id: ' + hash_(e) if e['msg']['type'] == 'claim' else ''))


def c_sign(a):
    print(canon(message(load_key(a.key), a.type, read_json(a.file))).decode('utf-8'))


def c_verify(a):
    from .sig import backend
    led, _ = fetch(a.ledger, cache=not a.full, root=root_of(a))
    if not led.whole:
        print('broken' + ('' if led.broken_at is None else ' at seq ' + str(led.broken_at)) + ': ' + str(led.error))
        sys.exit(1)
    print('whole: ' + str(len(led.entries)) + ' entries, ledger ' + str(led.id) + ' (' +
          (str(led.cached) + ' entries from the cache, ' if led.cached else '') + backend.name + ' Ed25519)')


def c_state(a):
    root = root_of(a)
    led, _ = fetch(a.ledger, root=root)
    if led.header is None:
        raise Invalid(str(led.error))
    print(canon(state(led, root=root), ID_KEY).decode('utf-8'))


def c_render(a):
    render(a.dex)
    print('rendered ' + a.dex)


def c_check(a):
    from .check import check
    while True:
        report = check(a.sources or ['.'], a.state, media=a.media, published=a.published, root=a.root,
                       log=(lambda line: None) if a.quiet else print)
        if a.json:
            with open(a.json, 'w') as f:
                f.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(report['time'] + ' ' + ('ok' if report['ok'] else 'FAILED') + ': ' + str(len(report['checked'])) +
              ' ledgers checked, ' + str(report['errors']) + ' errors, ' + str(report['warnings']) + ' warnings',
              flush=True)
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


def c_rotate(a):
    new, _ = key_or_new(a.key)
    add(a.dex, 'rotate', {'key': public(new)})
    print('the owner key is now ' + public(new) + ' (' + a.key + ')')


def c_recover(a):
    """Root side: name a new key for a ledger whose owner lost theirs."""
    led, _ = fetch(a.ledger)
    if led.header is None:
        raise Invalid('not a ledger: ' + str(led.error))
    add(a.dex, 'recover', {'ledger': led.id, 'key': key_arg(a.key)})


def c_recovered(a):
    """Owner side: take the ledger back with the key the root named."""
    root, _ = fetch(a.root)
    led, new = load(a.dex, root=root), load_key(a.key)
    rid = None
    for n, e in enumerate(root.entries):
        b = e['msg']['body']
        if e['msg']['type'] == 'recover' and b['ledger'] == led.id and b['key'] == public(new):
            rid = root.ids[n]
    if rid is None:
        raise Invalid('the root has no recover entry for this ledger and key ' + public(new))
    cfg_path = os.path.join(a.dex, 'config.json')
    cfg = read_json(cfg_path)
    cfg.setdefault('ledgdex', {}).update(root=a.root, root_id=root.id)   # every later read needs this root
    write_json(cfg_path, cfg)
    record(a.dex, [message(new, 'recovered', {'root': root.id, 'entry': rid})], secret=new)
    render(a.dex)
    print('recovered: the owner key is now ' + public(new))


def c_dispute(a):
    body = {'claim': a.claim, 'text': a.text, 'evidence': a.evidence or []}
    if not a.seller:   # the seller disputes in its own ledger
        add(a.dex, 'dispute', body)
        return
    seller, _ = other(a.seller)   # the buyer disputes in the seller's ledger
    send(a.dex, seller.owner, 'dispute', dict(body, claim=claim_id(seller, a.claim)), a.output)


def c_ruling(a):
    seller, _ = other(a.seller)
    if a.dispute not in state(seller)['disputes']:
        raise Invalid('no dispute ' + a.dispute + ' in that ledger')
    send(a.dex, seller.owner, 'ruling', {'dispute': a.dispute, 'outcome': a.outcome, 'text': a.text}, a.output)


def c_bid(a):
    led = load(a.dex)
    seller, _ = other(a.seller)
    if state(seller, now=now())['auctions'].get(a.auction, {}).get('status') != 'open':
        raise Invalid('no open auction ' + a.auction + ' in that ledger')
    path = bid_path(led, a.auction)
    if os.path.exists(path):
        raise Invalid('you already bid in this auction (one bid per key)')
    nonce = os.urandom(32).hex()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:  # private until the reveal
        json.dump({'auction': a.auction, 'ledger': seller.id, 'amount': a.amount, 'nonce': nonce}, f)
    send(a.dex, seller.owner, 'bid', {'auction': a.auction, 'commit': hash_({'amount': a.amount, 'nonce': nonce})},
         a.output)


def c_reveal(a):
    seller, _ = other(a.seller)
    path = bid_path(load(a.dex), a.auction)
    if not os.path.exists(path):
        raise Invalid('no bid of yours for ' + a.auction + ' on this machine')
    saved = read_json(path)
    send(a.dex, seller.owner, 'reveal', {'auction': a.auction, 'amount': saved['amount'], 'nonce': saved['nonce']},
         a.output)


def c_list(a):
    led, _ = other(a.ledger, 'that ledger')
    add(a.dex, 'list', {'ledger': led.id, 'url': a.url or led.dex or a.ledger, 'owner': led.owner, 'note': a.note})


def c_discover(a):
    """Read an index: the ledgers it lists, and with --offers their open offers and auctions."""
    idx, _ = fetch(a.index)
    found = []
    for lid, l in state(idx)['listings'].items():
        item = dict(l, ledger=lid)
        if a.offers:
            try:
                led, _ = fetch(l['url'], remote=True)
                if led.id != lid:
                    raise Invalid('that address serves another ledger')
                st = state(led)
                for kind in ('offers', 'auctions'):
                    item[kind] = [dict(x, id=i) for i, x in st[kind].items() if x['status'] == 'open']
            except Exception as e:
                item['error'] = str(e)
        found.append(item)
    if a.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
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
    R = (['--root'], {'help': 'the root ledger (dex, file or URL)'})
    L = (['ledger'], {'help': 'dex, file or URL'})
    flag = {'action': 'store_true'}
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
    for name, (help_, args, make) in SIMPLE.items():
        if name == 'device':   # "ledgdex device add DEX KEY": the action comes before the dex
            args = args[:1] + [D] + args[1:]
        else:
            args = [D] + args
        cmd(name, lambda a, make=make: add(a.dex, *make(a)), help_, *args)
    cmd('record', c_record, 'record claims, payments and confirmations from buyers', D,
        (['files'], {'nargs': '*', 'help': 'message files'}),
        (['--from'], {'dest': 'sources', 'action': 'append', 'help': "a buyer's dex: collect what they sent you"}))
    cmd('claim', c_claim, "buy: sign a claim for a seller's offer", D, S, (['offer'], {'type': id_arg}),
        (['--quantity'], {'type': int, 'default': 1}), O)
    cmd('pay', c_pay, 'tell the seller you paid', D, S, (['claim'], {'type': id_arg, 'help': 'claim id (or your claim message id)'}),
        (['--method'], {'required': True}), (['--ref'], {'default': ''}), O)
    cmd('confirm', c_confirm, 'confirm you received the goods', D, S, (['claim'], {'type': id_arg}), O)
    cmd('receipt', c_receipt, "keep the seller's records of your messages as receipts", D, S,
        (['--entry'], {'type': id_arg, 'help': 'only this entry id'}))
    cmd('rotate', c_rotate, 'replace the owner key (signed by the old one)', D,
        (['--key'], {'required': True, 'help': 'name of the new key in ~/.ledgdex (made if missing)'}))
    cmd('recover', c_recover, "root: name a new key for a ledger whose owner lost theirs", D,
        (['ledger'], {'help': 'the ledger (dex, file or URL)'}), (['key'], {'help': 'the new public key'}))
    cmd('recovered', c_recovered, 'take a ledger back with the key the root named', D,
        (['--root'], {'required': True}), (['--key'], {'required': True, 'help': 'name of the new key'}))
    cmd('dispute', c_dispute, 'open a dispute about a claim', D, (['claim'], {'type': id_arg}), (['--text'], {'default': ''}),
        (['--evidence'], {'action': 'append', 'help': 'an entry id or URL (repeatable)'}),
        (['--seller'], {'help': "buyer: the seller's dex (without it, a dispute in your own ledger)"}), O)
    cmd('ruling', c_ruling, "arbiter: rule on a dispute in a seller's ledger", D, S, (['dispute'], {'type': id_arg}),
        (['--outcome'], {'required': True, 'choices': ['release', 'refund', 'split']}), (['--text'], {'default': ''}), O)
    cmd('auction', c_auction, 'start a sealed-bid auction from a JSON file', D, (['file'], {}))
    cmd('bid', c_bid, "bid in a seller's auction (the amount stays secret until you reveal)", D, S, (['auction'], {'type': id_arg}),
        (['--amount'], {'type': int, 'required': True}), O)
    cmd('reveal', c_reveal, 'reveal your bid after the auction closes', D, S, (['auction'], {'type': id_arg}), O)
    cmd('list', c_list, 'index: list a ledger', D, L, (['--url'], {'help': 'address to list (default: its dex address)'}),
        (['--note'], {'default': ''}))
    cmd('discover', c_discover, 'read an index: listed ledgers, and with --offers what they sell',
        (['index'], {'help': 'the index (dex, file or URL)'}), (['--offers'], flag), (['--json'], flag))
    cmd('sign', c_sign, 'print a signed message (advanced)', (['type'], {}), (['file'], {}), (['--key'], {'required': True}))
    cmd('verify', c_verify, 'check a ledger; exit code 0 only if whole', L,
        (['--full'], dict(flag, help='verify every line, ignoring the verification cache')), R)
    cmd('state', c_state, "print a ledger's state", L, R)
    cmd('render', c_render, 'rewrite the generated pages and rebuild the site', D)
    cmd('check', c_check, 'check ledgers for tampering over time: rewrites, missing receipts, changed addresses',
        (['sources'], {'nargs': '*', 'help': 'ledgers to check: dex folders, files or URLs (default: this folder)'}),
        (['--state'], {'default': '.ledgdex-check', 'help': 'where last-seen copies and proofs are kept'}),
        (['--media'], dict(flag, help='also fetch offer media and check their hashes')),
        (['--published'], dict(flag, help='for dex folders: compare with the published ledger')),
        (['--json'], {'help': 'write the report as JSON to this file'}),
        (['--every'], {'type': int, 'help': 'run as a worker: check again every this many seconds'}),
        (['--quiet'], dict(flag, help='print only the summary line')), R)
    cmd('workflow', c_workflow, 'print a GitHub Actions workflow that runs ledgdex check',
        (['sources'], {'nargs': '+', 'help': 'ledger files in the repository, or URLs'}),
        (['--cron'], {'default': '17 6 * * *', 'help': 'schedule (UTC cron)'}), (['--media'], flag))
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

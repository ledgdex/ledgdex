"""ledgdex command-line tool (spec Part III). Run "ledgdex -h"."""
import argparse, json, os, sys
from .canon import canon, hash_, ID_KEY
from .core import Invalid, message, new_ledger, public
from .dex import LEDGER, fetch, find_key, keygen, load, load_key, record, write
from .render import render
from .state import state

OFFER_DEFAULTS = {'unit': 'unit', 'allow': 'any', 'pay': [], 'terms': ''}


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
    return led, find_key(led.owner)


def add(dex, type_, body):
    """Sign a message with the dex owner's key, record it, render."""
    led, secret = owner(dex)
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
    """Buyer side: sign a message for another ledger, keep a "sent" copy, write the message file."""
    led, secret = owner(dex)
    m = message(secret, type_, body)
    record(dex, [message(secret, 'sent', {'to': to, 'msg': m})])
    render(dex)
    p = save_msg(m, path)
    print(type_ + ' signed and kept as "sent". Send ' + p + ' to the seller, or publish your dex: '
          'the seller can collect it with "ledgdex record SELLER_DEX --from YOUR_DEX_URL"')
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
                 if e['msg']['type'] == 'sent' and e['msg']['body']['to'] == led.owner
                 and e['msg']['body']['msg']['by'] == other.owner]
    have = {hash_(e['msg']) for e in led.entries}
    new = []
    for m in msgs:
        h = hash_(m)
        if h not in have and m['type'] in ('claim', 'paid', 'confirmed'):
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
    picked = []
    for n, e in enumerate(seller.entries):
        if (a.entry and seller.ids[n] != a.entry) or seller.ids[n] in held:
            continue
        if a.entry or hash_(e['msg']) in mine:
            if e['msg']['by'] != led.owner:
                raise Invalid('entry ' + seller.ids[n] + ' does not record a message of yours')
            picked.append(e)
    if not picked:
        print('no new receipts')
        return
    secret = find_key(led.owner)
    record(a.dex, [message(secret, 'receipt', {'ledger': seller.id, 'url': url, 'header': seller.header,
                                                     'entry': e}) for e in picked])
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
    led, _ = fetch(a.ledger)
    if led.whole:
        print('whole: ' + str(len(led.entries)) + ' entries, ledger ' + str(led.id))
        return
    print('broken' + ('' if led.broken_at is None else ' at seq ' + str(led.broken_at)) + ': ' + str(led.error))
    sys.exit(1)


def c_state(a):
    led, _ = fetch(a.ledger)
    if led.header is None:
        raise Invalid(str(led.error))
    sys.stdout.write(canon(state(led), ID_KEY).decode('utf-8') + '\n')


def c_render(a):
    render(a.dex)
    print('rendered ' + a.dex)


def c_publish(a):
    from .publish import publish
    if not publish(a.dex):
        sys.exit(1)


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
        (['--branch'], {'help': 'branch to publish to'}))
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
    cmd('sign', c_sign, 'print a signed message (advanced)', (['type'], {}), (['file'], {}),
        (['--key'], {'required': True}))
    cmd('verify', c_verify, 'check a ledger; exit code 0 only if whole', (['ledger'], {'help': 'dex, file or URL'}))
    cmd('state', c_state, "print a ledger's state", (['ledger'], {'help': 'dex, file or URL'}))
    cmd('render', c_render, 'rewrite the generated pages and rebuild the site', D)
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

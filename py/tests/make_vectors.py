"""Shared test vectors for the Python and JavaScript implementations (spec Part III).

python tests/make_vectors.py   writes vectors/*.json and vectors/ledgers/
test_vectors.py checks the files are up to date; js/test.mjs checks JavaScript reproduces them byte for byte."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Book, BUYER, OTHER, SELLER, t  # noqa: E402
from ledgdex.canon import canon, hash_, ID_KEY  # noqa: E402
from ledgdex.core import Ledger, message, public, sign  # noqa: E402
from ledgdex.state import state  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'vectors')
PHONE = bytes(range(10, 42))
NEWKEY = bytes(range(20, 52))
ROOTKEY = bytes(range(30, 62))
NONCE = 'ab' * 16
NONCE2 = 'cd' * 16
ZERO = 'sha256:' + '0' * 64


def auction_body(**kw):
    b = {'item': {'title': 'Old map', 'text': 'sealed bids', 'media': []}, 'currency': 'INR', 'close': t(30),
         'reveal_until': t(60), 'best': 'highest', 'reserve': 100, 'allow': 'any',
         'arbiter': {'key': public(OTHER), 'url': ''}, 'terms': 'as seen'}
    b.update(kw)
    return b


def at(b, minute):
    b.minute = minute


def scenarios():
    out = {}

    # a market: every claim outcome, the whole trade, withdraw, admission
    b = Book()
    oid, oh = b.offer(quantity=3, item={'title': 'Mangoes ✓ आम', 'text': 'line one\nline "two"', 'media': [
        {'url': 'https://example.com/m.jpg', 'hash': 'sha256:' + '1' * 64}]})
    b.claim(ZERO, oh)
    b.claim(oid, ZERO)
    b.claim(oid, oh, quantity=0)
    b.claim(oid, oh, price=1)
    b.claim(oid, oh, secret=SELLER)
    cid = b.claim(oid, oh, quantity=2)
    b.claim(oid, oh, secret=OTHER, quantity=2)
    b.from_(BUYER, 'paid', {'claim': cid, 'method': 'upi', 'ref': 'r1'})
    b.from_(OTHER, 'paid', {'claim': cid, 'method': 'x', 'ref': ''})
    b.own('received', {'claim': cid, 'amount': 240000})
    b.from_(BUYER, 'confirmed', {'claim': cid})
    b.own('delivered', {'claim': cid, 'note': 'courier'})
    b.from_(BUYER, 'confirmed', {'claim': cid})
    o2, oh2 = b.offer(allow='admitted', expires=t(40))
    b.claim(o2, oh2)
    b.own('admit', {'key': public(BUYER), 'name': 'Asha', 'note': ''})
    b.claim(o2, oh2)
    b.own('revoke', {'key': public(BUYER), 'reason': ''})
    at(b, 45)
    b.claim(o2, oh2, secret=OTHER)
    b.own('withdraw', {'offer': o2})
    b.own('withdraw', {'offer': o2})
    b.own('note', {'ref': cid, 'text': 'thanks'})
    out['market'] = (b, None, None)

    # keys: device, revoke, rotate; and a buyer receipt that needs the key chain
    s = Book()
    oid, oh = s.offer()
    s.own('device', {'key': public(PHONE), 'name': 'phone'})
    m = message(PHONE, 'note', {'ref': oid, 'text': 'from the phone'}, at=s.tick())
    s.led.append(s.led.next_entry(PHONE, m, at=t(s.minute)))
    s.own('rotate', {'key': public(NEWKEY)})
    s.secret = NEWKEY
    m = message(BUYER, 'claim', {'offer': oid, 'offer_hash': oh, 'quantity': 1, 'price': 120000}, at=s.tick())
    s.led.append(s.led.next_entry(PHONE, m, at=t(s.minute)))
    s.own('device_revoke', {'key': public(PHONE), 'reason': 'lost'})
    s.own('note', {'ref': oid, 'text': 'new owner key'})
    out['keys'] = (s, None, None)
    buyer = Book(BUYER, 'Asha')
    buyer.own('sent', {'to': public(SELLER), 'msg': m})
    e = s.led.entries[s.led.find(s.led.ids[-3])]
    chain = [x for x in s.led.entries if x['msg']['type'] in ('rotate', 'device', 'device_revoke') and x['seq'] < e['seq']]
    buyer.own('receipt', {'ledger': s.led.id, 'url': 'https://farm.example', 'header': s.led.header, 'entry': e,
                          'keys': chain})
    out['buyer'] = (buyer, None, None)

    # the root, a recovery, and admission through the root
    root = Book(ROOTKEY, 'Root')
    r = Book()
    r.own('note', {'ref': r.led.ids[0], 'text': 'before the loss'})
    rid = root.own('recover', {'ledger': r.led.id, 'key': public(NEWKEY)})
    root.own('admit', {'key': public(BUYER), 'name': 'Asha', 'note': ''})
    out['root'] = (root, None, None)
    r.led.root = Ledger(root.led.data, cache=False)
    m = message(NEWKEY, 'recovered', {'root': root.led.id, 'entry': rid}, at=r.tick())
    r.led.append(r.led.next_entry(NEWKEY, m, at=t(r.minute)))
    r.secret = NEWKEY
    o, oh = r.offer(allow='admitted')
    r.own('admit', {'key': public(BUYER), 'name': '', 'note': ''})
    r.own('admit', {'key': public(OTHER), 'name': '', 'note': ''})
    r.claim(o, oh)
    r.claim(o, oh, secret=OTHER)
    out['recovered'] = (r, 'root', None)
    # receipts from a recovered ledger: the "recovered" key entry must be checked against the root (1.0.2)
    rl = Ledger(root.led.data, cache=False)
    rchain = [x for x in r.led.entries if x['msg']['type'] in ('rotate', 'device', 'device_revoke', 'recovered')]
    rc = r.led.entries[-2]                                           # BUYER's claim, recorded after the recovery
    rb = Book(BUYER, 'Asha')
    rb.led.root = rl
    rbody = {'ledger': r.led.id, 'url': 'https://farm.example', 'header': r.led.header, 'entry': rc,
             'keys': [x for x in rchain if x['seq'] < rc['seq']]}
    rm = message(BUYER, 'receipt', rbody, at=rb.tick(), root=rl)
    rb.led.append(rb.led.next_entry(BUYER, rm, at=t(rb.minute)))
    out['receipt-recovered'] = (rb, 'root', None)
    # the same root recover entry used a second time: before 1.0.2 a stolen old key could take the ledger back
    rr = message(NEWKEY, 'recovered', {'root': rl.id, 'entry': rid}, at=t(r.minute + 5))
    re_ = {'seq': len(r.led.entries), 'prev': r.led.ids[-1], 'time': t(r.minute + 5), 'msg': rr}
    re_['sig'] = sign(NEWKEY, re_)
    out['broken-recovery-replay'] = (r.led.data + canon(re_) + b'\n', 'root', None)
    # a forged receipt: a "recovered" entry signed by the buyer hands the seller's ledger to the buyer's key, then a
    # made-up entry. Before 1.0.2 it verified and "check" blamed the honest seller with receipt_mismatch.
    fk = {'v': 1, 'type': 'recovered', 'by': public(BUYER), 'at': t(1), 'body': {'root': rl.id, 'entry': rl.ids[1]}}
    fk['sig'] = sign(BUYER, fk)
    fk = {'seq': 1, 'prev': r.led.ids[0], 'time': t(1), 'msg': fk}
    fk['sig'] = sign(BUYER, fk)
    ff = {'v': 1, 'type': 'confirmed', 'by': public(BUYER), 'at': t(2), 'body': {'claim': ZERO}}
    ff['sig'] = sign(BUYER, ff)
    ff = {'seq': 2, 'prev': ZERO, 'time': t(2), 'msg': ff}
    ff['sig'] = sign(BUYER, ff)
    fb = Book(BUYER, 'Asha')
    fm = {'v': 1, 'type': 'receipt', 'by': public(BUYER), 'at': t(3), 'body': {
        'ledger': r.led.id, 'url': 'https://farm.example', 'header': r.led.header, 'entry': ff, 'keys': [fk]}}
    fm['sig'] = sign(BUYER, fm)
    fe = {'seq': 1, 'prev': fb.led.ids[-1], 'time': t(3), 'msg': fm}
    fe['sig'] = sign(BUYER, fe)
    out['broken-forged-receipt'] = (fb.led.data + canon(fe) + b'\n', 'root', None)

    # disputes
    d = Book()
    oid, oh = d.offer(arbiter={'key': public(OTHER), 'url': ''})
    c1, c2 = d.claim(oid, oh), d.claim(oid, oh)
    d.from_(OTHER, 'dispute', {'claim': c1, 'text': '', 'evidence': []})
    d1 = d.from_(BUYER, 'dispute', {'claim': c1, 'text': 'never arrived', 'evidence': [ZERO, 'https://x/y']})
    d.from_(SELLER, 'ruling', {'dispute': d1, 'outcome': 'release', 'text': ''})
    d.from_(OTHER, 'ruling', {'dispute': d1, 'outcome': 'refund', 'text': 'refund'})
    d.from_(OTHER, 'ruling', {'dispute': d1, 'outcome': 'split', 'text': ''})
    d2 = d.own('dispute', {'claim': c2, 'text': 'not paid', 'evidence': []})
    d.from_(OTHER, 'ruling', {'dispute': d2, 'outcome': 'split', 'text': 'half'})
    d.from_(OTHER, 'ruling', {'dispute': ZERO, 'outcome': 'split', 'text': ''})
    d.from_(BUYER, 'paid', {'claim': c2, 'method': 'x', 'ref': ''})
    out['disputes'] = (d, None, None)

    # auctions: highest with payment, lowest with a tie, one with no winner
    a = Book()
    a1 = a.own('auction', auction_body())
    a2 = a.own('auction', auction_body(best='lowest', reserve=600))
    a3 = a.own('auction', auction_body(reserve=10000))
    for aid, secret, amount, nonce in ((a1, BUYER, 500, NONCE), (a1, OTHER, 700, NONCE2), (a1, BUYER, 1, NONCE),
                                        (a2, BUYER, 400, NONCE), (a2, OTHER, 400, NONCE), (a3, BUYER, 50, NONCE),
                                        (a1, SELLER, 9, NONCE), (ZERO, BUYER, 1, NONCE)):
        a.from_(secret, 'bid', {'auction': aid, 'commit': hash_({'amount': amount, 'nonce': nonce})})
    a.from_(BUYER, 'reveal', {'auction': a1, 'amount': 500, 'nonce': NONCE})          # early
    a.from_(BUYER, 'paid', {'claim': a1, 'method': 'x', 'ref': ''})                   # not awarded yet
    at(a, 30)
    a.from_(PHONE, 'bid', {'auction': a1, 'commit': ZERO})                            # late
    a.from_(BUYER, 'reveal', {'auction': a1, 'amount': 500, 'nonce': NONCE})
    a.from_(OTHER, 'reveal', {'auction': a1, 'amount': 700, 'nonce': NONCE})          # wrong nonce
    a.from_(OTHER, 'reveal', {'auction': a2, 'amount': 400, 'nonce': NONCE})
    a.from_(BUYER, 'reveal', {'auction': a2, 'amount': 400, 'nonce': NONCE})
    a.from_(BUYER, 'reveal', {'auction': a2, 'amount': 400, 'nonce': NONCE})          # twice
    a.from_(PHONE, 'reveal', {'auction': a2, 'amount': 1, 'nonce': NONCE})            # never bid
    a.from_(BUYER, 'reveal', {'auction': a3, 'amount': 50, 'nonce': NONCE})
    out['auctions-revealing'] = (a, None, None)
    a2b = Book()
    a2b.led = Ledger(a.led.data, cache=False)
    a2b.minute = a.minute
    at(a2b, 60)
    a2b.from_(OTHER, 'reveal', {'auction': a1, 'amount': 700, 'nonce': NONCE2})       # late
    a2b.from_(BUYER, 'paid', {'claim': a1, 'method': 'upi', 'ref': 'r'})
    a2b.own('received', {'claim': a1, 'amount': 500})
    a2b.own('delivered', {'claim': a1, 'note': ''})
    a2b.from_(BUYER, 'confirmed', {'claim': a1})
    a2b.from_(BUYER, 'dispute', {'claim': a2, 'text': 'tie?', 'evidence': []})
    out['auctions'] = (a2b, None, None)
    out['auctions-later'] = (a2b, None, t(500))

    # an index
    i = Book(OTHER, 'Market')
    i.own('list', {'ledger': b.led.id, 'url': 'https://farm.example', 'owner': public(SELLER), 'note': 'mangoes'})
    i.own('list', {'ledger': d.led.id, 'url': 'https://d.example', 'owner': public(SELLER), 'note': ''})
    i.own('delist', {'ledger': d.led.id, 'reason': 'gone'})
    i.own('delist', {'ledger': ZERO, 'reason': ''})
    out['index'] = (i, None, None)

    # broken ledgers
    data = b.led.data
    lines = data.split(b'\n')
    flipped = bytearray(data)
    flipped[len(lines[0]) + 1 + len(lines[1]) + 1 + 60] ^= 1
    out['broken-byte'] = (bytes(flipped), None, None)
    out['broken-newline'] = (data[:-1], None, None)
    out['broken-order'] = (b'\n'.join(lines[:2] + [lines[3], lines[2]] + lines[4:]), None, None)
    e = json.loads(lines[3])
    e['sig'] = sign(OTHER, {k: v for k, v in e.items() if k != 'sig'})
    out['broken-signer'] = (b'\n'.join(lines[:3] + [canon(e)] + lines[4:]), None, None)
    out['broken-noroot'] = (r, None, None)

    # found by tests/fuzz.py: values Python and JavaScript once read differently
    def resigned(change, seq=1):
        e = json.loads(lines[seq + 1])
        change(e)
        e['msg']['sig'] = sign(SELLER, {k: v for k, v in e['msg'].items() if k != 'sig'})
        e['sig'] = sign(SELLER, {k: v for k, v in e.items() if k != 'sig'})
        return b'\n'.join(lines[:seq + 1] + [canon(e)] + lines[seq + 2:seq + 3]) + b'\n'
    out['broken-type-object'] = (resigned(lambda e: e['msg'].update(type={})), None, None)      # crashed Python
    out['broken-version-true'] = (resigned(lambda e: e['msg'].update(v=True)), None, None)       # True == 1 in Python
    out['broken-seq-true'] = (resigned(lambda e: e.update(seq=True)), None, None)
    # found by the security audit: replays, nesting, early years
    rp = Book()
    oid, oh = rp.offer(quantity=5)
    claim = message(BUYER, 'claim', {'offer': oid, 'offer_hash': oh, 'quantity': 2, 'price': 120000}, at=rp.tick())
    rp.rec(claim)
    rp.rec(claim)                                                    # the same signed claim again: ignored
    dev = message(SELLER, 'device', {'key': public(PHONE), 'name': 'phone'}, at=rp.tick())
    rp.led.append(rp.led.next_entry(SELLER, dev, at=t(rp.minute)))
    rp.own('device_revoke', {'key': public(PHONE), 'reason': 'lost'})
    rp.led.append(rp.led.next_entry(SELLER, dev, at=t(rp.tick() and rp.minute)))  # replayed: no device again
    out['replay'] = (rp, None, None)
    from ledgdex.core import new_ledger
    old = new_ledger(SELLER, 'Year 99', '', '', at='0099-01-01T00:00:00Z')
    old.append(old.next_entry(SELLER, message(SELLER, 'note', {'ref': old.ids[0], 'text': 'early'},
                                              at='0099-12-31T23:59:59Z'), at='0099-12-31T23:59:59Z'))
    out['year-99'] = (old.data, None, None)
    # every free text a ledger holds, written to break out of a page: it must render as text (invariant 14)
    X = '<script>x()</script><img src=x onerror=y()>\'"&amp;<a href="javascript:z()">'
    hs = Book(SELLER, X)
    from helpers import offer_body
    hid = hs.own('offer', offer_body(item={'title': X, 'text': X, 'media': [{'url': X, 'hash': 'sha256:' + '3' * 64}]},
                                     unit=X, currency=X, pay=[{'method': X, 'to': X}], terms=X,
                                     arbiter={'key': public(SELLER), 'url': X}))
    hoh = hash_(hs.led.entries[-1]['msg'])
    hc = message(BUYER, 'claim', {'offer': hid, 'offer_hash': hoh, 'quantity': 1, 'price': 120000}, at=hs.tick())
    hs.rec(hc)
    hcid = hs.led.ids[-1]
    hs.from_(BUYER, 'paid', {'claim': hcid, 'method': X, 'ref': X})
    hs.own('delivered', {'claim': hcid, 'note': X})
    hs.from_(BUYER, 'dispute', {'claim': hcid, 'text': X, 'evidence': [X]})
    hs.own('note', {'ref': hcid, 'text': X})
    hs.own('admit', {'key': public(BUYER), 'name': X, 'note': X})
    hs.own('revoke', {'key': public(BUYER), 'reason': X})
    hs.own('list', {'ledger': ZERO, 'url': X, 'owner': public(SELLER), 'note': X})
    hs.own('delist', {'ledger': ZERO, 'reason': X})
    out['hostile-text'] = (hs, None, None)
    hb = Book(BUYER, X)
    hb.own('sent', {'to': public(SELLER), 'msg': hc})
    hb.own('receipt', {'ledger': hs.led.id, 'url': X, 'header': hs.led.header,
                       'entry': hs.led.entries[hs.led.find(hcid)]})
    out['hostile-buyer'] = (hb, None, None)

    # a time with a full-width digit: Python read it as a time before 1.0.4, JavaScript did not
    fw = Book()
    fe = json.loads(fw.led.lines[0])
    fe['time'] = '\uff12' + fe['time'][1:]
    fe['msg']['at'] = fe['time']
    fe['msg']['sig'] = sign(SELLER, {k: v for k, v in fe['msg'].items() if k != 'sig'})
    fe['sig'] = sign(SELLER, {k: v for k, v in fe.items() if k != 'sig'})
    out['broken-fullwidth-time'] = (fw.led.header_line + b'\n' + canon(fe) + b'\n', None, None)

    # a device copies in an owner-signed "device" message meant for another ledger of the same owner (before 1.0.6
    # it was accepted, giving that key signing power here)
    dc = Book(SELLER, 'Shop B')
    dc.own('device', {'key': public(PHONE), 'name': 'phone'})
    other_ledger_msg = message(SELLER, 'device', {'key': public(OTHER), 'name': 'terminal at A'}, at=dc.tick())
    de = {'seq': len(dc.led.entries), 'prev': dc.led.ids[-1], 'time': t(dc.minute), 'msg': other_ledger_msg}
    de['sig'] = sign(PHONE, de)
    out['broken-device-copies-owner-message'] = (dc.led.data + canon(de) + b'\n', None, None)

    # a small-order owner key: before 1.0 one forged signature (R = B, S = 1) verified for every message
    from ledgdex import ed25519
    from ledgdex.core import sha256 as id_of
    weak, forged = 'ed25519:01' + '00' * 31, (ed25519._compress(ed25519.G) + (1).to_bytes(32, 'little')).hex()
    hl = canon({'ledger': 1, 'name': 'Anyone', 'owner': weak})
    m = {'v': 1, 'type': 'open', 'by': weak, 'at': t(0), 'body': {'about': '', 'dex': ''}, 'sig': forged}
    out['broken-small-order-key'] = (hl + b'\n' + canon({'seq': 0, 'prev': id_of(hl), 'time': t(0), 'msg': m,
                                                         'sig': forged}) + b'\n', None, None)
    xs = Book()                                                      # addresses that must not become links
    xs.offer(item={'title': 'Links', 'text': '', 'media': [
        {'url': 'javascript:alert(1)', 'hash': 'sha256:' + '2' * 64},
        {'url': 'JAVASCRIPT:alert(1)', 'hash': 'sha256:' + '2' * 64},
        {'url': ' https://x.example', 'hash': 'sha256:' + '2' * 64},
        {'url': 'https://x.example/a b', 'hash': 'sha256:' + '2' * 64},
        {'url': "https://x.example/'><script>", 'hash': 'sha256:' + '2' * 64},
        {'url': 'DATA:text/html,x', 'hash': 'sha256:' + '2' * 64}]})
    xs.own('list', {'ledger': ZERO, 'url': 'javascript:alert(2)', 'owner': public(SELLER), 'note': ''})
    out['links'] = (xs, None, None)
    out['broken-header-true'] = (b'{"ledger":true,"name":"x","owner":"' + public(SELLER).encode() + b'"}\n', None, None)
    out['broken-header'] = (b'{"ledger":1,"name":"x"}\n', None, None)
    return out


def build():
    files = {}
    ledgers = {}
    scenarios_root = {}
    for name, (src, root, now) in scenarios().items():
        data = src if isinstance(src, bytes) else src.led.data
        ledgers[name] = data
        scenarios_root[name] = root
    for name, (src, root, now) in scenarios().items():
        data = ledgers[name]
        root_led = Ledger(ledgers[root], cache=False) if root else None
        led = Ledger(data, cache=False, root=root_led)
        expect = {'root': root, 'now': now, 'whole': led.whole, 'broken_at': led.broken_at,
                  'entries': len(led.entries)}
        if led.header is not None:
            expect['state'] = canon(state(led, root=root_led, now=now), ID_KEY).decode('utf-8')
        if name.startswith('auctions-later'):
            continue_name = 'auctions'
            files['ledgers/' + name + '.json'] = json.dumps(dict(expect, ledger=continue_name), indent=1,
                                                            ensure_ascii=False) + '\n'
            continue
        files['ledgers/' + name + '.jsonl'] = data
        files['ledgers/' + name + '.json'] = json.dumps(dict(expect, ledger=name), indent=1, ensure_ascii=False) + '\n'

    # the dex pages each whole ledger renders to (spec 7.2): JavaScript's render.js must match
    from ledgdex.render import pages
    rendered = {}
    for name in sorted(ledgers):
        root_name = scenarios_root.get(name)
        led = Ledger(ledgers[name], cache=False, root=Ledger(ledgers[root_name], cache=False) if root_name else None)
        if led.whole:
            rendered[name] = pages(led, ['Mangoes', 'About', 'Farm ledger'])
    files['pages.json'] = json.dumps(rendered, indent=1, ensure_ascii=False) + '\n'

    # dex names as dexweb may write them, unescaped (render.dex_name): JavaScript's dexName must agree
    from ledgdex.render import dex_name
    names = ['Farm ü', 'Maps & co', '<script>x()</script>', '"\'><img src=x onerror=y()>', '\x00\x1f\x7f', '', '<>&',
             'आम 😀 Asha', 'tab\there', 'line\nbreak']
    files['dexnames.json'] = json.dumps([[n, dex_name(n)] for n in names], indent=1, ensure_ascii=False) + '\n'

    # whole dexs built by dexweb (what "ledgdex init" makes): JavaScript's dexweb.js must build the same files
    import contextlib, io, shutil, tempfile
    from dexweb import dexgen
    from ledgdex.render import create_dex, render
    tmp = tempfile.mkdtemp(prefix='ledgdex-vectors-')
    try:
        for name, dexname in (('market', 'Farm ü'), ('buyer', 'आम Asha'), ('index', 'Market'), ('auctions', 'Maps & co'),
                              ('hostile-text', '<img src=x onerror=y()>"\'\x00\x7f')):
            dex = os.path.join(tmp, name)
            with contextlib.redirect_stdout(io.StringIO()):
                create_dex(dex, ledgers[name], dexname)
            files.update(dex_files(dex, 'dex/' + name + '/'))
        # the same ledger with dexweb's other index style and script hooks: only gen/ changes
        dex = os.path.join(tmp, 'market')
        with open(os.path.join(dex, 'config.json')) as f:
            cfg = json.load(f)
        cfg.update(index_list_type_para=False, page_javascript='<script src="p.js"></script>',
                   index_javascript='<script src="i.js"></script>')
        with open(os.path.join(dex, 'config.json'), 'w') as f:
            f.write(json.dumps(cfg, indent=4))
        with contextlib.redirect_stdout(io.StringIO()):
            render(dex)
        files.update({k: v for k, v in dex_files(dex, 'dex/market-variant/').items() if '/gen/' in k})
        # dexweb's own template and styles, for building dexs in the browser
        g = dexgen.Dexgen.__new__(dexgen.Dexgen)
        g.dexname = ''
        g.save_dexname_in_config(tmp, '')
        with open(os.path.join(tmp, 'config.json')) as f:
            config = json.load(f)
        import base64, importlib_resources
        from ledgdex.render import favicon
        styles = importlib_resources.files('dexweb').joinpath('styles.css').read_text()
        files['../js/dexweb-template.json'] = json.dumps({'config': config, 'styles': styles,
                                                          'favicon': base64.b64encode(favicon()).decode()},
                                                         indent=1, ensure_ascii=False) + '\n'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # canonical JSON: does parse() accept these exact bytes?
    texts = ['{"a":1}', '{ "a":1}', '{"b":1,"a":2}', '{"a":1,"a":1}', '{"a":1.0}', '{"a":1e3}', '{"a":-0}',
             '{"a":9007199254740991}', '{"a":9007199254740992}', '{"A":1}', '{"a-b":1}', '{"é":1}', '"\\u00e9"',
             '"é"', '"\\ud800"', '"\\b\\f\\n\\r\\t\\u0000\\u001f\x7f"', '"\\u001F"', '"\\/"', '[true,false,null]',
             '[1,2]', '[1, 2]', 'NaN', '{"a":"🥭"}', '{"a":"\\ud83e\\udd6d"}', '[]', '{}', '""', '{"z":{"b":[],"a":{}}}',
             '\ufeff{"a":1}', '\ufeff""', '[' * 32 + ']' * 32, '[' * 33 + ']' * 33, '[' * 5000 + ']' * 5000,
             '{"a":' * 33 + '1' + '}' * 33]  # a leading byte-order mark: JavaScript's decoder once dropped it
    files['canon.json'] = json.dumps([{'input': x, 'ok': _ok(x)} for x in texts], indent=1, ensure_ascii=False) + '\n'

    # signatures: the same key and value sign to the same bytes everywhere
    sigs = []
    for secret in (SELLER, BUYER, PHONE):
        for v in ({'a': 1}, {'msg': 'आम 🥭', 'n': -5, 'l': [True, None]}, []):
            sigs.append({'secret': secret.hex(), 'public': public(secret), 'value': v, 'canon': canon(v).decode(),
                         'hash': hash_(v), 'sig': sign(secret, v)})
    files['signatures.json'] = json.dumps(sigs, indent=1, ensure_ascii=False) + '\n'
    return files


def dex_files(dex, prefix):
    out = {}
    for base, dirs, names in os.walk(dex):
        for n in names:
            full = os.path.join(base, n)
            with open(full, 'rb') as f:
                out[prefix + os.path.relpath(full, dex)] = f.read()
    return out


def _ok(text):
    from ledgdex.canon import parse, CanonError
    try:
        parse(text.encode('utf-8', 'surrogatepass'))
        return True
    except (CanonError, UnicodeDecodeError):
        return False


def write():
    for path, content in build().items():
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(content if isinstance(content, bytes) else content.encode('utf-8'))


if __name__ == '__main__':
    os.environ['LEDGDEX_NO_CACHE'] = '1'
    write()
    print('wrote', len(build()), 'files to', os.path.normpath(ROOT))

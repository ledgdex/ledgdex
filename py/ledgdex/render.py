"""Every ledgdex is a dex (spec 7): generated pages in data.json, then the dexweb build."""
import contextlib, html, io, json, os, shutil
from .canon import hash_
from .dex import LEDGER, inside, load
from .core import Invalid
from .state import state

MARKER = '<!-- ledgdex -->'
DIGITS = {'INR': 2, 'USD': 2, 'EUR': 2, 'GBP': 2, 'AUD': 2, 'CAD': 2, 'SGD': 2, 'AED': 2, 'CHF': 2, 'CNY': 2,
          'JPY': 0, 'KRW': 0, 'BTC': 8}


def esc(s):
    return html.escape(s, quote=True).replace('\n', '<br>')


def amount(currency, n):
    """INR 20,000.00 (2000000). Currencies without known minor units are written as the integer."""
    k = DIGITS.get(currency)
    if k is None:
        return esc(currency) + ' ' + '{:,}'.format(n)
    sign, n2 = ('-' if n < 0 else ''), abs(n)
    major = '{:,}'.format(n2 // 10 ** k) + ('.' + str(n2 % 10 ** k).zfill(k) if k else '')
    return esc(currency) + ' ' + sign + major + ' (' + str(n) + ')'


def short(s):
    return s.split(':')[0] + ':' + s.split(':')[1][:12]


def code(s):
    return '<code>' + esc(s) + '</code>'


def html_title(t):
    # dexweb names each page file after its title: letters and digits only, lowercase
    return ''.join(x for x in t if x.isalnum()).lower()


def link(title):
    # title is already escaped (see pages)
    return "<a href='" + html_title(title) + ".html'>" + title + '</a>'


def _ref(label, key):
    return lambda b: label + code(short(b[key]))


# one line about each entry type, for the ledger page
SUMMARY = {
    'open': lambda b: 'opened the ledger',
    'offer': lambda b: esc(b['item']['title']) + ', ' + str(b['quantity']) + ' ' + esc(b['unit']) + ' at ' +
    amount(b['currency'], b['price']) + ' each',
    'withdraw': _ref('offer ', 'offer'),
    'claim': lambda b: str(b['quantity']) + ' of offer ' + code(short(b['offer'])),
    'paid': lambda b: 'claim ' + code(short(b['claim'])) + ' by ' + esc(b['method']),
    'received': lambda b: 'claim ' + code(short(b['claim'])) + ' amount ' + str(b['amount']),
    'delivered': _ref('claim ', 'claim'),
    'confirmed': _ref('claim ', 'claim'),
    'admit': _ref('', 'key'),
    'revoke': _ref('', 'key'),
    'note': lambda b: 'about ' + code(short(b['ref'])) + ': ' + esc(b['text']),
    'sent': lambda b: esc(b['msg']['type']) + ' to ' + code(short(b['to'])),
    'rotate': _ref('', 'key'),
    'device': lambda b: code(short(b['key'])) + (' (' + esc(b['name']) + ')' if b['name'] else ''),
    'device_revoke': _ref('', 'key'),
    'recovered': _ref('owner key recovered through the root, entry ', 'entry'),
    'recover': lambda b: 'new key ' + code(short(b['key'])) + ' for ledger ' + code(short(b['ledger'])),
    'dispute': lambda b: 'about ' + code(short(b['claim'])) + (': ' + esc(b['text']) if b['text'] else ''),
    'ruling': lambda b: b['outcome'] + ' on dispute ' + code(short(b['dispute'])),
    'auction': lambda b: esc(b['item']['title']) + ', bids until ' + b['close'],
    'bid': _ref('auction ', 'auction'),
    'reveal': lambda b: 'auction ' + code(short(b['auction'])) + ' amount ' + str(b['amount']),
    'list': lambda b: 'ledger ' + code(short(b['ledger'])) + ' ' + esc(b['url']),
    'delist': _ref('ledger ', 'ledger'),
    'receipt': lambda b: 'entry ' + str(b['entry']['seq']) + ' (' + esc(b['entry']['msg']['type']) + ') of ' +
    esc(b['header']['name']) + "'s ledger",
}


def item_lines(item):
    """An item's text and media links (with their hashes)."""
    return ([esc(item['text'])] if item['text'] else []) + [
        "Media: <a href='" + esc(md['url']) + "'>" + esc(md['url']) + '</a> ' + code(md['hash']) for md in item['media']]


def pages(led, author_titles):
    """The generated pages (spec 7.2) for a whole ledger, as dex page objects."""
    st = state(led)
    name = led.header['name']
    taken = set(html_title(t) for t in author_titles) | {'index'}
    own = set(taken)

    def title_for(t, id_=None):
        t = html.escape(' '.join(t.split()), quote=True)  # dexweb writes titles into the page as they are
        if not html_title(t):
            t = 'Offer ' + (id_ or '')[7:15]
        if html_title(t) in own:
            t += ' (ledgdex)'
        if html_title(t) in taken and id_:
            t += ' ' + id_[7:15]
        taken.add(html_title(t))
        return t

    ledger_title = title_for(name + ' ledger')
    offers = [(led.ids[n], e['msg']) for n, e in enumerate(led.entries) if e['msg']['type'] == 'offer']
    offer_titles = {id_: title_for(m['body']['item']['title'], id_) for id_, m in offers}
    auctions = [(led.ids[n], e['msg']) for n, e in enumerate(led.entries) if e['msg']['type'] == 'auction']
    auction_titles = {id_: title_for(m['body']['item']['title'], id_) for id_, m in auctions}
    listings_title = title_for(name + ' listings') if st['listings'] else None
    sent_claims = [e for e in led.entries if e['msg']['type'] == 'sent' and e['msg']['body']['msg']['type'] == 'claim']
    purchases_title = title_for(name + ' purchases') if sent_claims else None
    admits = [e for e in led.entries if e['msg']['type'] in ('admit', 'revoke')]
    admissions_title = title_for(name + ' admissions') if admits else None
    about = led.entries[0]['msg']['body']['about'] if led.entries else ''
    dex = led.dex or 'THIS_DEX'
    out = []

    # 1. the ledger
    head = led.head()
    body = [MARKER + esc(name) + "'s ledger: " + str(len(led.entries)) + ' entries, ' +
            ('whole' if led.whole else 'broken at seq ' + str(led.broken_at)),
            'Owner key: ' + code(led.owner),
            'Device keys: ' + (', '.join(code(k) for k in st['devices']) if st['devices'] else 'none'),
            'Ledger id: ' + code(led.id),
            'Head: ' + ('seq ' + str(head['seq']) + ', ' + code(head['id']) if head else 'none'),
            'Verification: ' + ('whole' if led.whole else 'broken at seq ' + str(led.broken_at)),
            "Download the ledger: <a href='" + LEDGER + "'>" + LEDGER + '</a>']
    if about:
        body.insert(1, esc(about))
    links = [link(offer_titles[i]) for i, _ in offers] + [link(auction_titles[i]) for i, _ in auctions]
    links += [link(t) for t in (purchases_title, admissions_title, listings_title) if t]
    if links:
        body.append('Pages: ' + ', '.join(links))
    body.append('Entries:')
    for n, e in enumerate(led.entries):
        m = e['msg']
        body.append(str(n) + '. ' + e['time'] + ' ' + esc(m['type']) + ' by ' + code(short(m['by'])) + ': ' +
                    SUMMARY[m['type']](m['body']) + ' ' + code(short(led.ids[n])))
    out.append({'title': ledger_title, 'body': body})

    # 2. one page per offer
    for id_, m in offers:
        b, o = m['body'], st['offers'][id_]
        cur = b['currency']
        body = [MARKER + amount(cur, b['price']) + ' per ' + esc(b['unit']) + ', ' + str(o['remaining']) + ' of ' +
                str(b['quantity']) + ' left, ' + o['status']] + item_lines(b['item'])
        body += ['Status: ' + o['status'],
                 'Remaining: ' + str(o['remaining']) + ' of ' + str(b['quantity']) + ' ' + esc(b['unit']),
                 'Price: ' + amount(cur, b['price']) + ' per ' + esc(b['unit'])]
        if 'expires' in b:
            body.append('Expires: ' + b['expires'])
        for p in b['pay']:
            body.append('Pay by ' + esc(p['method']) + ': ' + esc(p['to']))
        body.append('Arbiter: ' + code(b['arbiter']['key']) + (' ' + esc(b['arbiter']['url']) if b['arbiter']['url'] else ''))
        if b['terms']:
            body.append('Terms: ' + esc(b['terms']))
        allow = b['allow']
        body.append('Who may buy: ' + ('anyone' if allow == 'any' else 'keys admitted by this ledger'
                                       if allow == 'admitted' else ', '.join(code(k) for k in allow)))
        body += ['Offer id: ' + code(id_), 'Offer hash: ' + code(hash_(m)),
                 'To buy, with your own ledgdex: ' + code('ledgdex claim YOUR_DEX ' + dex +
                                                          ' ' + id_ + ' --quantity 1'),
                 'Then send the claim file to the seller, or publish your dex: the seller collects claims with ' +
                 code('ledgdex record DEX --from YOUR_DEX_URL') + '.']
        mine = [(cid, c) for cid, c in st['claims'].items() if c['offer'] == id_]
        if mine:
            body.append('Claims:')
            for cid, c in mine:
                body.append(code(short(cid)) + ' by ' + code(short(c['buyer'])) + ': ' + str(c['quantity']) + ' at ' +
                            amount(cur, c['price']) + ', ' + c['status'] +
                            (' (' + c['reason'] + ')' if 'reason' in c else '') + flags(c))
        out.append({'title': offer_titles[id_], 'body': body})

    # 2b. one page per auction
    for id_, m in auctions:
        b, a = m['body'], st['auctions'][id_]
        body = [MARKER + a['status'] + ', ' + str(a['bids']) + ' sealed bids'] + item_lines(b['item'])
        body += ['Status: ' + a['status'], 'Bids close: ' + b['close'], 'Reveals until: ' + b['reveal_until'],
                 'Best bid: ' + b['best'] + ', reserve ' + amount(b['currency'], b['reserve']),
                 'Arbiter: ' + code(b['arbiter']['key'])]
        if b['terms']:
            body.append('Terms: ' + esc(b['terms']))
        if 'winner' in a:
            body.append('Winner: ' + code(a['winner']) + ' at ' + amount(b['currency'], a['amount']))
        body += ['Auction id: ' + code(id_),
                 'To bid, with your own ledgdex: ' + code('ledgdex bid YOUR_DEX ' + dex + ' ' +
                                                          id_ + ' --amount N') + '. After the close, reveal it with ' +
                 code('ledgdex reveal YOUR_DEX ' + dex + ' ' + id_) + '.']
        out.append({'title': auction_titles[id_], 'body': body})

    # 3. purchases: claims this self sent, and the receipts it holds for them
    if purchases_title:
        receipts = {}
        for e in led.entries:
            if e['msg']['type'] == 'receipt':
                r = e['msg']['body']
                receipts[hash_(r['entry']['msg'])] = (r, hash_(r['entry']))
        body = [MARKER + str(len(sent_claims)) + ' claims sent']
        for e in sent_claims:
            s = e['msg']['body']
            c = s['msg']
            line = e['time'] + ': ' + str(c['body']['quantity']) + ' of offer ' + code(short(c['body']['offer'])) + \
                ' from ' + code(short(s['to'])) + ' at ' + str(c['body']['price']) + ' each. '
            got = receipts.get(hash_(c))
            if got:
                r, eid = got
                line += 'Receipt: entry ' + str(r['entry']['seq']) + ' of ' + esc(r['header']['name']) + \
                    "'s ledger, claim id " + code(eid)
            else:
                line += 'No receipt yet.'
            body.append(line)
        out.append({'title': purchases_title, 'body': body})

    # 3b. listings (an index)
    if listings_title:
        body = [MARKER + str(len(st['listings'])) + ' ledgers listed']
        for lid, l in st['listings'].items():
            body.append("<a href='" + esc(l['url']) + "'>" + esc(l['url']) + '</a> ledger ' + code(lid) + ', owner ' +
                        code(l['owner']) + (': ' + esc(l['note']) if l['note'] else ''))
        out.append({'title': listings_title, 'body': body})

    # 4. admissions
    if admissions_title:
        body = [MARKER + str(len(st['admitted'])) + ' keys admitted']
        for e in admits:
            b = e['msg']['body']
            body.append(e['time'] + ' ' + e['msg']['type'] + ' ' + code(b['key']) + ': ' +
                        esc(b.get('name', b.get('reason', ''))) + (' ' + esc(b['note']) if b.get('note') else ''))
        out.append({'title': admissions_title, 'body': body})
    return out


def flags(c):
    f = [k for k in ('paid', 'received', 'delivered', 'confirmed') if k in c]
    return (', ' + ', '.join(f)) if f else ''


def generated(page):
    b = page.get('body') if isinstance(page, dict) else None
    return bool(b) and isinstance(b[0], str) and b[0].startswith(MARKER)


RUN_PY = 'from dexweb import dexgen\ndex = dexgen.Dexgen()\n'


def create_dex(dex, data, dexname, publish=None):
    """A complete dex (spec 7.1) around the ledger bytes `data`: config.json with dexweb's own template and
    "publish" with "append_only", data.json, run.py, then render. Keeps a config.json that is already there."""
    from dexweb import dexgen
    from .dex import write
    os.makedirs(dex, exist_ok=True)
    write(dex, data)
    cfg_path = os.path.join(dex, 'config.json')
    if not os.path.exists(cfg_path):
        g = dexgen.Dexgen.__new__(dexgen.Dexgen)
        g.dexname = dexname
        g.save_dexname_in_config(dex, dexname)  # dexweb's own default template
    with open(cfg_path) as f:
        cfg = json.load(f)
    pub = cfg.get('publish') if isinstance(cfg.get('publish'), dict) else {}
    pub['append_only'] = sorted(set(pub.get('append_only', [])) | {LEDGER})
    pub.update(publish or {})
    cfg['publish'] = pub
    with open(cfg_path, 'w') as f:
        f.write(json.dumps(cfg, indent=4))
    for name, text in (('data.json', '[]'), ('run.py', RUN_PY)):
        if not os.path.exists(os.path.join(dex, name)):
            with open(os.path.join(dex, name), 'w') as f:
                f.write(text)
    render(dex)


def render(dex, build=True):
    """Spec 7.3: rewrite the generated pages in data.json, copy the ledger into gen/, build with dexweb."""
    led = load(dex)
    if not os.path.exists(os.path.join(dex, 'config.json')):
        raise Invalid(dex + ' is not a dex: config.json is missing. Run "ledgdex init" first')
    data_path = os.path.join(dex, 'data.json')
    author = []
    if os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            author = [p for p in json.load(f) if not generated(p)]
    data = author + pages(led, [p.get('title', '') for p in author])
    with open(data_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))
    os.makedirs(os.path.join(dex, 'gen'), exist_ok=True)
    shutil.copyfile(os.path.join(dex, LEDGER), os.path.join(dex, 'gen', LEDGER))
    if build:
        dexgen_build(dex)


def dexgen_build(dex):
    from dexweb import dexgen
    with inside(dex), contextlib.redirect_stdout(io.StringIO()):
        dexgen.Dexgen()

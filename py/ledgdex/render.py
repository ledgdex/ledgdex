"""Every ledgdex is a dex (spec 7): generated pages in data.json, then the dexweb build."""
import contextlib, html, io, json, os, shutil
from .canon import hash_
from .dex import LEDGER, load
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


def summary(led, n):
    """One line about entry n, for the ledger page."""
    m = led.entries[n]['msg']
    b, t = m['body'], m['type']
    if t == 'open':
        return 'opened the ledger'
    if t == 'offer':
        return esc(b['item']['title']) + ', ' + str(b['quantity']) + ' ' + esc(b['unit']) + ' at ' + \
            amount(b['currency'], b['price']) + ' each'
    if t in ('withdraw',):
        return 'offer ' + code(short(b['offer']))
    if t == 'claim':
        return str(b['quantity']) + ' of offer ' + code(short(b['offer']))
    if t in ('paid', 'received', 'delivered', 'confirmed'):
        extra = {'paid': ' by ' + esc(b.get('method', '')), 'received': ' amount ' + str(b.get('amount', ''))}
        return 'claim ' + code(short(b['claim'])) + extra.get(t, '')
    if t in ('admit', 'revoke'):
        return code(short(b['key']))
    if t == 'note':
        return 'about ' + code(short(b['ref'])) + ': ' + esc(b['text'])
    if t == 'sent':
        return esc(b['msg']['type']) + ' to ' + code(short(b['to']))
    if t == 'receipt':
        return 'entry ' + str(b['entry']['seq']) + ' (' + esc(b['entry']['msg']['type']) + ') of ' + \
            esc(b['header']['name']) + "'s ledger"
    return ''


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
    sent_claims = [e for e in led.entries if e['msg']['type'] == 'sent' and e['msg']['body']['msg']['type'] == 'claim']
    purchases_title = title_for(name + ' purchases') if sent_claims else None
    admits = [e for e in led.entries if e['msg']['type'] in ('admit', 'revoke')]
    admissions_title = title_for(name + ' admissions') if admits else None
    about = led.entries[0]['msg']['body'] if led.entries else {'about': '', 'dex': ''}
    out = []

    # 1. the ledger
    head = led.head()
    body = [MARKER + esc(name) + "'s ledger: " + str(len(led.entries)) + ' entries, ' +
            ('whole' if led.whole else 'broken at seq ' + str(led.broken_at)),
            'Owner key: ' + code(led.owner),
            'Ledger id: ' + code(led.id),
            'Head: ' + ('seq ' + str(head['seq']) + ', ' + code(head['id']) if head else 'none'),
            'Verification: ' + ('whole' if led.whole else 'broken at seq ' + str(led.broken_at)),
            "Download the ledger: <a href='" + LEDGER + "'>" + LEDGER + '</a>']
    if about['about']:
        body.insert(1, esc(about['about']))
    links = [link(offer_titles[i]) for i, _ in offers]
    links += [link(t) for t in (purchases_title, admissions_title) if t]
    if links:
        body.append('Pages: ' + ', '.join(links))
    body.append('Entries:')
    for n, e in enumerate(led.entries):
        m = e['msg']
        body.append(str(n) + '. ' + e['time'] + ' ' + esc(m['type']) + ' by ' + code(short(m['by'])) + ': ' +
                    summary(led, n) + ' ' + code(short(led.ids[n])))
    out.append({'title': ledger_title, 'body': body})

    # 2. one page per offer
    for id_, m in offers:
        b, o = m['body'], st['offers'][id_]
        cur = b['currency']
        body = [MARKER + amount(cur, b['price']) + ' per ' + esc(b['unit']) + ', ' + str(o['remaining']) + ' of ' +
                str(b['quantity']) + ' left, ' + o['status']]
        if b['item']['text']:
            body.append(esc(b['item']['text']))
        for md in b['item']['media']:
            body.append("Media: <a href='" + esc(md['url']) + "'>" + esc(md['url']) + '</a> ' + code(md['hash']))
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
                 'To buy, with your own ledgdex: ' + code('ledgdex claim YOUR_DEX ' + (about['dex'] or 'THIS_DEX') +
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
    cwd = os.getcwd()
    os.chdir(dex)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            dexgen.Dexgen()
    finally:
        os.chdir(cwd)

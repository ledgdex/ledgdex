"""Differential fuzzing: Python and JavaScript must agree on every input.

    python tests/fuzz.py [--seed N] [--ledgers N] [--texts N] [--keep DIR]

Builds random ledgers (every message type), corrupts them (bytes, lines, and fields re-signed so the change reaches
the deeper rules), and makes tricky JSON texts. Python and node (js/fuzz.mjs) each verify every case: whether it
parses, whether it is whole, where it breaks, why, and canon(state). Any difference is printed and saved, and the
exit code is 1."""
import argparse, base64, json, os, random, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['LEDGDEX_NO_CACHE'] = '1'
from helpers import T0  # noqa: E402
from ledgdex.canon import canon, hash_, parse, CanonError, ID_KEY  # noqa: E402
from ledgdex.core import Invalid, Keys, Ledger, message, new_ledger, public, seconds, sign, unsigned, utc  # noqa: E402
from ledgdex.state import state  # noqa: E402
from ledgdex.render import pages  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, '..', '..', 'js', 'fuzz.mjs')
SECRETS = [bytes([i] * 31 + [7]) for i in range(1, 7)]
# the vector ledgers' keys too (helpers.py, make_vectors.py), so their mutations can be re-signed
KEYS = {public(s): s for s in SECRETS + [bytes(range(i, i + 32)) for i in (0, 1, 2, 10, 20, 30)]}
WEIRD = ['', 'a', 'Mangoes', 'आम', '🥭', 'quote " and \\ backslash', 'line\nbreak', 'tab\there', '\x00nul', '\x1f',
         '\x7f', ' ', '﻿', 'é', 'Ω', 'é', '\U0010ffff', ' ', '{"json":1}', '<b>html</b>']
BIG = [0, 1, 2, 3, 100, 120000, 2 ** 31, 2 ** 53 - 1, -1, -(2 ** 53 - 1)]


class Gen:
    """A random but structurally valid ledger: every type, many business-rule violations."""

    def __init__(self, rnd):
        self.r = rnd
        self.owner = rnd.choice(SECRETS)
        self.signers = [self.owner]           # secrets that may sign entries now
        self.minute = 0
        self.led = new_ledger(self.owner, rnd.choice(WEIRD), rnd.choice(WEIRD), rnd.choice(['', 'https://x.example']),
                              at=T0)
        self.offers, self.claims, self.auctions, self.disputes, self.bids = [], [], [], [], []

    def t(self, minutes=None):
        self.minute += self.r.choice([0, 0, 1, 1, 2, 5, 20]) if minutes is None else minutes
        return utc(seconds(T0) + 60 * self.minute)

    def ref(self, pool):
        if pool and self.r.random() < 0.85:
            return self.r.choice(pool)
        return 'sha256:' + ''.join(self.r.choice('0123456789abcdef') for _ in range(64))

    def item(self):
        media = [] if self.r.random() < 0.7 else [{'url': 'https://m.example/' + str(self.r.randrange(9)),
                                                   'hash': self.ref([])}]
        return {'title': self.r.choice(WEIRD), 'text': self.r.choice(WEIRD), 'media': media}

    def allow(self):
        return self.r.choice(['any', 'any', 'admitted', [public(self.r.choice(SECRETS))]])

    def someone(self):
        return self.r.choice(SECRETS)

    def step(self):
        r, t = self.r, self.t()
        kind = r.choice(['offer', 'offer', 'claim', 'claim', 'claim', 'paid', 'received', 'delivered', 'confirmed',
                         'withdraw', 'admit', 'revoke', 'note', 'dispute', 'ruling', 'auction', 'bid', 'bid',
                         'reveal', 'reveal', 'list', 'delist', 'device', 'device_revoke', 'rotate', 'sent'])
        own = self.r.choice(self.signers)
        if kind == 'offer':
            b = {'item': self.item(), 'quantity': r.choice([1, 2, 3, 10]), 'unit': r.choice(WEIRD),
                 'currency': r.choice(['INR', 'USD', 'BTC', 'ASS', '']), 'price': r.choice(BIG[:8]),
                 'allow': self.allow(), 'pay': [], 'arbiter': {'key': public(self.someone()), 'url': ''},
                 'terms': r.choice(WEIRD)}
            if r.random() < 0.3:
                b['expires'] = utc(seconds(t) + 60 * r.choice([0, 1, 10, 100]))
            m = message(own, 'offer', b, at=t)
        elif kind == 'claim':
            o = self.ref([x[0] for x in self.offers])
            known = [x for x in self.offers if x[0] == o]
            price = known[0][2] if known and r.random() < 0.8 else r.choice(BIG)
            ohash = known[0][1] if known and r.random() < 0.9 else self.ref([])
            m = message(self.someone(), 'claim', {'offer': o, 'offer_hash': ohash,
                                                  'quantity': r.choice([0, 1, 1, 2, 3, -1]), 'price': price}, at=t)
        elif kind in ('paid', 'received', 'delivered', 'confirmed', 'dispute'):
            c = self.ref(self.claims + self.auctions)
            author = own if kind in ('received', 'delivered') else self.someone()
            b = {'paid': {'claim': c, 'method': r.choice(WEIRD), 'ref': r.choice(WEIRD)},
                 'received': {'claim': c, 'amount': r.choice(BIG)}, 'delivered': {'claim': c, 'note': r.choice(WEIRD)},
                 'confirmed': {'claim': c}, 'dispute': {'claim': c, 'text': r.choice(WEIRD),
                                                        'evidence': [r.choice(WEIRD)]}}[kind]
            m = message(author, kind, b, at=t)
        elif kind == 'withdraw':
            m = message(own, 'withdraw', {'offer': self.ref([x[0] for x in self.offers])}, at=t)
        elif kind in ('admit', 'revoke'):
            b = {'key': public(self.someone())}
            b.update({'name': r.choice(WEIRD), 'note': ''} if kind == 'admit' else {'reason': ''})
            m = message(own, kind, b, at=t)
        elif kind == 'note':
            m = message(own, 'note', {'ref': self.ref(self.led.ids), 'text': r.choice(WEIRD)}, at=t)
        elif kind == 'ruling':
            m = message(self.someone(), 'ruling', {'dispute': self.ref(self.disputes),
                                                   'outcome': r.choice(['release', 'refund', 'split']), 'text': ''}, at=t)
        elif kind == 'auction':
            close = seconds(t) + 60 * r.choice([1, 3, 10])
            b = {'item': self.item(), 'currency': 'INR', 'close': utc(close),
                 'reveal_until': utc(close + 60 * r.choice([1, 5, 20])), 'best': r.choice(['highest', 'lowest']),
                 'reserve': r.choice([0, 100, 500, 10 ** 6]), 'allow': self.allow(),
                 'arbiter': {'key': public(self.someone()), 'url': ''}, 'terms': ''}
            m = message(own, 'auction', b, at=t)
        elif kind == 'bid':
            a, who = self.ref(self.auctions), self.someone()
            amount, nonce = r.choice([0, 50, 100, 400, 500, 700]), r.choice(['ab' * 16, 'cd' * 20, '0' * 32])
            self.bids.append((a, who, amount, nonce))
            m = message(who, 'bid', {'auction': a, 'commit': hash_({'amount': amount, 'nonce': nonce})}, at=t)
        elif kind == 'reveal':
            a, who, amount, nonce = r.choice(self.bids) if self.bids else (self.ref([]), self.someone(), 1, 'ab' * 16)
            if r.random() < 0.2:
                amount += 1
            m = message(who, 'reveal', {'auction': a, 'amount': amount, 'nonce': nonce}, at=t)
        elif kind == 'list':
            m = message(own, 'list', {'ledger': self.ref([]), 'url': r.choice(WEIRD), 'owner': public(self.someone()),
                                      'note': ''}, at=t)
        elif kind == 'delist':
            m = message(own, 'delist', {'ledger': self.ref([]), 'reason': ''}, at=t)
        elif kind == 'device':
            m = message(self.led_owner_secret(), 'device', {'key': public(self.someone()), 'name': 'd'}, at=t)
        elif kind == 'device_revoke':
            m = message(self.led_owner_secret(), 'device_revoke', {'key': public(self.someone()), 'reason': ''}, at=t)
        elif kind == 'rotate':
            m = message(self.led_owner_secret(), 'rotate', {'key': public(self.someone())}, at=t)
        else:
            inner = message(own, 'paid', {'claim': self.ref(self.claims), 'method': '', 'ref': ''}, at=t)
            m = message(own, 'sent', {'to': public(self.someone()), 'msg': inner}, at=t)
        try:
            i = self.led.append(self.led.next_entry(own, m, at=t))
        except Invalid:
            return
        self.signers = [KEYS[k] for k in self.led.keys.signing()]
        if kind == 'offer':
            self.offers.append((i, hash_(m), m['body']['price']))
        elif kind == 'claim':
            self.claims.append(i)
        elif kind == 'auction':
            self.auctions.append(i)
        elif kind == 'dispute':
            self.disputes.append(i)

    def led_owner_secret(self):
        return KEYS[self.led.owner]


def build(rnd, steps):
    g = Gen(rnd)
    for _ in range(steps):
        g.step()
    return g.led


def resign_from(lines, k, change, rnd):
    """Change entry k (and re-sign it, its message, and every later entry), so the change reaches deeper rules."""
    head, entries = lines[0], [json.loads(x) for x in lines[1:]]
    keys, ids = Keys(json.loads(head)['owner']), [hash_(json.loads(head))]
    out = [head]
    for n, e in enumerate(entries):
        try:
            signer = keys.signed_by(e) or e['msg']['by']
        except Exception:
            signer = None
        if n == k:
            change(e, rnd)
            by = e.get('msg', {}).get('by') if isinstance(e, dict) and isinstance(e.get('msg'), dict) else None
            if isinstance(by, str) and by in KEYS:
                try:
                    e['msg']['sig'] = sign(KEYS[e['msg']['by']], unsigned(e['msg']))
                except (CanonError, Exception):
                    pass
        if n >= k and isinstance(e, dict):
            e['prev'] = ids[-1]
            try:
                e['sig'] = sign(KEYS.get(signer, SECRETS[0]) if isinstance(signer, str) else SECRETS[0], unsigned(e))
            except Exception:
                pass
        try:
            line = canon(e)
        except Exception:
            line = json.dumps(e, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8', 'surrogatepass')
        out.append(line)
        ids.append('sha256:' + __import__('hashlib').sha256(line).hexdigest())
        if isinstance(e, dict) and isinstance(e.get('msg'), dict) and e['msg'].get('type') in ('rotate', 'device', 'device_revoke', 'recovered'):
            try:
                keys.apply(e['msg'])
            except Exception:
                pass
    return b'\n'.join(out) + b'\n'


def transplant(lines, donors, rnd):
    """Record, on top of a ledger, a message taken from another ledger (or from earlier in this one), signed by any
    known key, with the chain and time kept valid: only the rules on who may record what decide (owner-only copies,
    devices, counterparties, duplicates)."""
    head = json.loads(lines[0])
    entries = [json.loads(x) for x in lines[1:]]
    donor = rnd.choice(donors)
    msgs = [json.loads(x)['msg'] for x in donor[1:]]
    if not entries or not msgs:
        return b'\n'.join(lines) + b'\n'
    m = rnd.choice(msgs)
    for x in (m.get('body', {}).get('msg'), m.get('body', {}).get('entry', {}).get('msg') if isinstance(m.get('body', {}).get('entry'), dict) else None):
        if isinstance(x, dict) and rnd.random() < 0.3:
            m = x            # sometimes the message inside a "sent" or a receipt
    last = entries[-1]
    t = max(last['time'], m['at']) if isinstance(m.get('at'), str) else last['time']
    e = {'seq': len(entries), 'prev': 'sha256:' + __import__('hashlib').sha256(lines[-1]).hexdigest(), 'time': t, 'msg': m}
    try:   # mostly signed by one of the ledger's own current keys (owner or a device), so the rules are reached
        own = [KEYS[k] for k in Ledger(b'\n'.join(lines) + b'\n', cache=False).keys.signing() if k in KEYS]
    except Exception:
        own = []
    e['sig'] = sign(rnd.choice(own) if own and rnd.random() < 0.8 else rnd.choice(list(KEYS.values())), e)
    return b'\n'.join(lines + [canon(e)]) + b'\n'


def random_value(rnd):
    return rnd.choice([0, -1, 2 ** 53 - 1, 2 ** 53, 1.5, True, False, None, '', 'x', '\ud800', 'é', [], {}, [1],
                       {'a': 1}, {'A': 1}, 'sha256:' + '0' * 64, 'ed25519:' + '1' * 64, '2026-02-30T00:00:00Z',
                       '2026-10-01T09:00:60Z', '2026-10-01T09:00:00Z', 'ab' * 15, 'AB' * 16,
                       # non-ASCII digits that look like the real thing (Python's \d took them in times before 1.0.4)
                       '\uff12026-10-01T09:00:00Z', '2026-10-01T09:00:0\u0663Z', 'sha256:' + '\uff10' * 64,
                       'ed25519:' + '\u0661' * 64, '\uff12', '\u0661'])


def mutate_field(e, rnd):
    targets = []

    def walk(v, path):
        if isinstance(v, dict):
            for k in v:
                targets.append(path + [k])
                walk(v[k], path + [k])
        elif isinstance(v, list):
            for i, x in enumerate(v):
                targets.append(path + [i])
                walk(x, path + [i])
    walk(e, [])
    path = rnd.choice(targets)
    parent = e
    for p in path[:-1]:
        parent = parent[p]
    how = rnd.random()
    if how < 0.15 and isinstance(parent, dict):
        del parent[path[-1]]
    elif how < 0.3 and isinstance(parent, dict):
        parent[rnd.choice(['extra', 'constructor', '__proto__', 'toString', 'A', 'sig2'])] = random_value(rnd)
    else:
        parent[path[-1]] = random_value(rnd)


def mutate_bytes(data, rnd):
    b = bytearray(data)
    how = rnd.randrange(9)
    lines = data.split(b'\n')
    if how == 0 and b:
        b[rnd.randrange(len(b))] ^= 1 << rnd.randrange(8)
    elif how == 1 and b:
        b[rnd.randrange(len(b))] = rnd.choice(b'\x00\n"\\\x7f\x80\xc3\xff{}[],: 0e.-')
    elif how == 2 and b:
        del b[rnd.randrange(len(b))]
    elif how == 3:
        b.insert(rnd.randrange(len(b) + 1), rnd.choice(b' \n\t"\\\xef\xbb\xbf0'))
    elif how == 4 and len(lines) > 3:
        i = rnd.randrange(1, len(lines) - 2)
        lines[i], lines[i + 1] = lines[i + 1], lines[i]
        return b'\n'.join(lines)
    elif how == 5 and len(lines) > 2:
        i = rnd.randrange(1, len(lines) - 1)
        return b'\n'.join(lines[:i] + [lines[i]] + lines[i:])
    elif how == 6:
        return data[:rnd.randrange(len(data) + 1)]
    elif how == 7 and len(lines) > 2:
        i = rnd.randrange(1, len(lines) - 1)
        text = lines[i].decode('utf-8', 'replace')
        swaps = [('é', '\\u00e9'), ('":', '": '), (',"', ', "'), ('0,', '0.0,'), ('1,', '1e0,'), ('true', 'True'),
                 ('\\n', '\\u000a'), ('\\"', '\\u0022'), ('/', '\\/'), ('"seq":', '"seq":0'), ('\\u001f', '\\u001F')]
        a, c = rnd.choice(swaps)
        lines[i] = text.replace(a, c, 1).encode('utf-8')
        return b'\n'.join(lines)
    else:
        return data + rnd.choice([b'\n', b'{}\n', b'x', b'\r\n', lines[-2] + b'\n' if len(lines) > 1 else b''])
    return bytes(b)


def texts(rnd, n):
    base = ['{"a":1}', '[1,2,3]', '"x"', '{"a":{"b":[true,false,null]}}', '{"k":"आम🥭"}', '{"a":-5}', '[]', '{}', '""']
    pieces = ['{', '}', '[', ']', '"', ':', ',', ' ', '\t', '\n', '\r', '0', '1', '-', '.', 'e', 'E', '+', 'a', 'z',
              'A', '_', '\\', '\\u00e9', '\\u0000', '\\ud800', '\\udc00', '\\ud83e\\udd6d', 'é', '🥭', '\x7f', ' ',
              'true', 'false', 'null', 'NaN', 'Infinity', '9007199254740991', '9007199254740992', '1e400', '\\/',
              '\\b', '\\f', '\\x', '\\U0041', '\x00', '\x1f', '﻿']
    out = []
    for i in range(n):
        if rnd.random() < 0.5:
            s = rnd.choice(base)
            for _ in range(rnd.randrange(1, 4)):
                p = rnd.randrange(len(s) + 1)
                s = s[:p] + rnd.choice(pieces) + s[p + rnd.choice([0, 0, 1]):]
            data = s.encode('utf-8', 'surrogatepass')
        else:
            data = rnd.choice(base).encode('utf-8')
            data = bytes(bytearray(data) + bytes([rnd.choice([0x80, 0xc0, 0xc3, 0xed, 0xef, 0xf0, 0xf4, 0xff])]))
            if rnd.random() < 0.5:
                data = b'"' + bytes([rnd.choice([0xc0, 0xe0, 0xed, 0xf0])]) + bytes(rnd.choice([b'\x80', b'\xa0\x80',
                                                                                              b'\x80\x80\x80'])) + b'"'
        out.append(data)
    return out


# ---------- the verdicts ----------

def py_ledger(data, root, now):
    root_led = Ledger(root, cache=False) if root else None
    led = Ledger(data, cache=False, root=root_led)
    v = {'header': led.header is not None, 'whole': led.whole, 'broken_at': led.broken_at,
         'entries': len(led.entries), 'error': led.error}
    if led.header is not None:
        v['state'] = canon(state(led, root=root_led, now=now), ID_KEY).decode('utf-8')
    if led.whole:
        v['pages'] = json.dumps(pages(led, ['Mangoes', 'About']), ensure_ascii=False, separators=(',', ':'))
    return v


def py_text(data):
    try:
        return {'ok': True, 'canon': canon(parse(data)).decode('utf-8')}
    except (CanonError, UnicodeDecodeError, RecursionError):
        return {'ok': False}


def reason(error):
    # each language's JSON parser words its own complaint; what must agree is where and that it is not JSON
    # and a line that breaks canonical JSON (1.2) may break it several ways: which one is named first can differ
    if error is None:
        return None
    return re.sub(r'(not JSON: .*|not canonical JSON|floats are not allowed|bad key: .*|integer out of range|'
                  r'string is not valid Unicode|duplicate key: .*|too deeply nested)$', 'not canonical JSON (1.2)', error)


def corpus(seed, n_ledgers, n_texts):
    rnd = random.Random(seed)
    cases = []
    vec = os.path.join(HERE, '..', '..', 'vectors', 'ledgers')
    bases = []
    for f in sorted(os.listdir(vec)):
        if f.endswith('.jsonl') and not f.startswith('broken'):
            with open(os.path.join(vec, f), 'rb') as fh:
                bases.append(fh.read())
    with open(os.path.join(vec, 'root.jsonl'), 'rb') as fh:
        root = fh.read()
    for i in range(n_ledgers):
        if i < n_ledgers // 4:
            data = build(rnd, rnd.choice([5, 15, 30, 60])).data
        else:
            src = rnd.choice(bases + [build(rnd, 20).data])
            lines = src.split(b'\n')[:-1]
            if rnd.random() < 0.3 and len(lines) > 1:
                data = transplant(lines, [b.split(b'\n')[:-1] for b in bases], rnd)
            elif rnd.random() < 0.5 and len(lines) > 2:
                data = resign_from(lines, rnd.randrange(len(lines) - 1), mutate_field, rnd)
            else:
                data = src
                for _ in range(rnd.choice([1, 1, 2, 3])):
                    data = mutate_bytes(data, rnd)
        use_root = rnd.random() < 0.2
        now = rnd.choice([None, None, utc(seconds(T0) + 60 * rnd.randrange(0, 2000))])
        cases.append({'id': 'L%d' % i, 'kind': 'ledger', 'data': data, 'root': root if use_root else None, 'now': now})
    for i, data in enumerate(texts(rnd, n_texts)):
        cases.append({'id': 'T%d' % i, 'kind': 'text', 'data': data})
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--ledgers', type=int, default=400)
    ap.add_argument('--texts', type=int, default=4000)
    ap.add_argument('--keep', help='save the corpus and any disagreements here')
    a = ap.parse_args()
    cases = corpus(a.seed, a.ledgers, a.texts)
    work = a.keep or tempfile.mkdtemp(prefix='ledgdex-fuzz-')
    os.makedirs(work, exist_ok=True)
    cpath, rpath = os.path.join(work, 'corpus.jsonl'), os.path.join(work, 'js-results.jsonl')
    with open(cpath, 'w') as f:
        for c in cases:
            row = dict(c, data=base64.b64encode(c['data']).decode())
            if c.get('root'):
                row['root'] = base64.b64encode(c['root']).decode()
            f.write(json.dumps(row) + '\n')
    subprocess.run(['node', JS, cpath, rpath], check=True)
    with open(rpath) as f:
        js = {r['id']: r for r in map(json.loads, f)}
    diffs, reasons = [], 0
    stats = {'ledger': 0, 'whole': 0, 'text': 0, 'text_ok': 0}
    for c in cases:
        py = py_ledger(c['data'], c.get('root'), c.get('now')) if c['kind'] == 'ledger' else py_text(c['data'])
        j = js[c['id']]
        stats[c['kind']] += 1
        if c['kind'] == 'ledger':
            stats['whole'] += py['whole']
        else:
            stats['text_ok'] += py['ok']
        verdict = {k: v for k, v in py.items() if k != 'error'}
        if verdict != {k: v for k, v in j.items() if k in verdict}:
            diffs.append({'id': c['id'], 'python': py, 'javascript': j})
        elif reason(py.get('error')) != reason(j.get('error')):
            reasons += 1
            diffs.append({'id': c['id'], 'only_reason': True, 'python': py.get('error'), 'javascript': j.get('error')})
    print('%d ledgers (%d whole), %d texts (%d canonical): %d verdict differences, %d reason differences' % (
        stats['ledger'], stats['whole'], stats['text'], stats['text_ok'], len(diffs) - reasons, reasons))
    if diffs:
        out = os.path.join(work, 'differences.json')
        with open(out, 'w') as f:
            json.dump(diffs, f, indent=1, ensure_ascii=False)
        for d in diffs[:10]:
            print(json.dumps(d, ensure_ascii=False)[:400])
        print('all differences: ' + out + ' (corpus: ' + cpath + ')')
        sys.exit(1)


if __name__ == '__main__':
    main()

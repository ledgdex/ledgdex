"""Keys, messages, entries and ledger verification (spec 1-5)."""
import datetime, os, re
from . import ed25519
from .canon import canon, hash_, sha256, parse, check, CanonError

KEY_RE = re.compile(r'ed25519:[0-9a-f]{64}\Z')
SIG_RE = re.compile(r'[0-9a-f]{128}\Z')
ID_RE = re.compile(r'sha256:[0-9a-f]{64}\Z')
TIME_RE = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z')
SKEW = 300  # spec 3.3 rule 7


class Invalid(ValueError):
    pass


# ---------- keys and time ----------

def new_secret():
    return os.urandom(32)


def public(secret):
    return 'ed25519:' + ed25519.public_key(secret).hex()


def sign(secret, obj):
    return ed25519.sign(secret, canon(obj)).hex()


def verify(key, obj, sig):
    if not is_key(key) or not isinstance(sig, str) or not SIG_RE.match(sig):
        return False
    return ed25519.verify(bytes.fromhex(key[8:]), canon(obj), bytes.fromhex(sig))


def is_key(v):
    return isinstance(v, str) and bool(KEY_RE.match(v))


def is_id(v):
    return isinstance(v, str) and bool(ID_RE.match(v))


def is_time(v):
    if not isinstance(v, str) or not TIME_RE.match(v):
        return False
    try:
        datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        return False
    return True


def seconds(t):
    return int(datetime.datetime.strptime(t, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp())


def utc(s):
    return datetime.datetime.fromtimestamp(s, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def now():
    return utc(int(datetime.datetime.now(datetime.timezone.utc).timestamp()))


# ---------- message bodies (spec 5, the v1 market subset) ----------

def _str(v):
    return isinstance(v, str)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _media(v):
    return (isinstance(v, list) and all(isinstance(m, dict) and set(m) == {'url', 'hash'} and _str(m['url'])
            and not m['url'].startswith('data:') and is_id(m['hash']) for m in v))


def _item(v):
    return (isinstance(v, dict) and set(v) == {'title', 'text', 'media'} and _str(v['title']) and _str(v['text'])
            and _media(v['media']))


def _allow(v):
    return v in ('any', 'admitted') or (isinstance(v, list) and all(is_key(k) for k in v))


def _pay(v):
    return isinstance(v, list) and all(isinstance(x, dict) and set(x) == {'method', 'to'} and _str(x['method'])
                                       and _str(x['to']) for x in v)


def _arbiter(v):
    return isinstance(v, dict) and set(v) == {'key', 'url'} and is_key(v['key']) and _str(v['url'])


def _header(v):
    return (isinstance(v, dict) and set(v) == {'ledger', 'name', 'owner'} and v['ledger'] == 1 and _str(v['name'])
            and is_key(v['owner']))


def _entry(v):
    return (isinstance(v, dict) and set(v) == {'seq', 'prev', 'time', 'msg', 'sig'} and _int(v['seq'])
            and v['seq'] >= 0 and is_id(v['prev']) and is_time(v['time']) and isinstance(v['sig'], str))


# type: (required fields, optional fields), field checks
BODIES = {
    'open': ({'about': _str, 'dex': _str}, {}),
    'admit': ({'key': is_key, 'name': _str, 'note': _str}, {}),
    'revoke': ({'key': is_key, 'reason': _str}, {}),
    'note': ({'ref': is_id, 'text': _str}, {}),
    'sent': ({'to': is_key, 'msg': lambda v: isinstance(v, dict)}, {}),
    'receipt': ({'ledger': is_id, 'url': _str, 'header': _header, 'entry': _entry}, {}),
    'offer': ({'item': _item, 'quantity': lambda v: _int(v) and v >= 1, 'unit': _str, 'currency': _str,
               'price': lambda v: _int(v) and v >= 0, 'allow': _allow, 'pay': _pay, 'arbiter': _arbiter,
               'terms': _str}, {'expires': is_time}),
    'withdraw': ({'offer': is_id}, {}),
    'claim': ({'offer': is_id, 'offer_hash': is_id, 'quantity': _int, 'price': _int}, {}),
    'paid': ({'claim': is_id, 'method': _str, 'ref': _str}, {}),
    'received': ({'claim': is_id, 'amount': _int}, {}),
    'delivered': ({'claim': is_id, 'note': _str}, {}),
    'confirmed': ({'claim': is_id}, {}),
}
# types someone other than the owner authors and the owner records (spec 4, 5.4)
COUNTERPARTY = {'claim', 'paid', 'confirmed'}


def check_body(type_, body):
    if type_ not in BODIES:
        raise Invalid('unknown type: ' + str(type_))
    req, opt = BODIES[type_]
    if not isinstance(body, dict):
        raise Invalid(type_ + ': body is not an object')
    for k in body:
        if k not in req and k not in opt:
            raise Invalid(type_ + ': unexpected field ' + k)
    for k, ok in list(req.items()) + list(opt.items()):
        if k in body and not ok(body[k]):
            raise Invalid(type_ + ': bad ' + k)
        if k in req and k not in body:
            raise Invalid(type_ + ': missing ' + k)
    if type_ == 'sent':
        check_message(body['msg'])
    if type_ == 'receipt':
        check_receipt(body)


def check_message(m):
    """Raise Invalid unless m is a valid message (spec 2)."""
    if not isinstance(m, dict) or set(m) != {'v', 'type', 'by', 'at', 'body', 'sig'}:
        raise Invalid('a message has exactly the keys v, type, by, at, body, sig')
    try:
        check(m)
    except CanonError as e:
        raise Invalid(str(e))
    if m['v'] != 1:
        raise Invalid('message version must be 1')
    if not is_key(m['by']):
        raise Invalid('bad author key')
    if not is_time(m['at']):
        raise Invalid('bad time')
    check_body(m['type'], m['body'])
    if not verify(m['by'], unsigned(m), m['sig']):
        raise Invalid('message signature does not verify')


def check_receipt(body):
    # v1 has no device keys or rotation: the entry is signed by the owner key in the other ledger's header
    if hash_(body['header']) != body['ledger']:
        raise Invalid('receipt: header does not match ledger id')
    e = body['entry']
    if not verify(body['header']['owner'], unsigned(e), e['sig']):
        raise Invalid('receipt: entry signature does not verify')
    check_message(e['msg'])


def unsigned(obj):
    return {k: v for k, v in obj.items() if k != 'sig'}


def message(secret, type_, body, at=None):
    m = {'v': 1, 'type': type_, 'by': public(secret), 'at': at or now(), 'body': body}
    m['sig'] = sign(secret, m)
    check_message(m)
    return m


# ---------- ledgers (spec 3) ----------

class Ledger:
    """A parsed ledger. Verification stops at the first structurally invalid line (spec 3.3)."""

    def __init__(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.data = data
        self.header = None
        self.id = None
        self.entries = []   # valid entries, in order
        self.ids = []       # their entry ids
        self.lines = []     # their lines, without the newline
        self.broken_at = None
        self.error = None
        self.header_line = None
        self._load()

    def _load(self):
        lines = self.data.split(b'\n')
        partial = lines.pop()  # bytes after the last newline: none in a whole file
        if not lines:
            self.error = 'empty ledger' if not partial else 'the header must end with a newline'
            return
        try:
            h = parse(lines[0])
        except CanonError as e:
            self.error = 'header: ' + str(e)
            return
        if not _header(h):
            self.error = 'header: must be {"ledger":1,"name":str,"owner":key}'
            return
        self.header, self.header_line, self.id = h, lines[0], sha256(lines[0])
        for n, line in enumerate(lines[1:]):
            try:
                e = parse(line)
                self.check_entry(n, e)
            except (CanonError, Invalid) as err:
                self.broken_at, self.error = n, 'seq ' + str(n) + ': ' + str(err)
                return
            self.entries.append(e)
            self.ids.append(sha256(line))
            self.lines.append(line)
        if partial:
            n = len(self.entries)
            self.broken_at, self.error = n, 'seq ' + str(n) + ': the line does not end with a newline'

    @property
    def owner(self):
        return self.header['owner'] if self.header else None

    @property
    def whole(self):
        return self.header is not None and self.broken_at is None and self.error is None

    def head(self):
        if not self.entries:
            return None
        return {'seq': len(self.entries) - 1, 'id': self.ids[-1]}

    def check_entry(self, n, e):
        """Spec 3.3, rules 1-8, for entry n on top of the entries already loaded."""
        if not isinstance(e, dict) or set(e) != {'seq', 'prev', 'time', 'msg', 'sig'}:
            raise Invalid('an entry has exactly the keys seq, prev, time, msg, sig')
        if e['seq'] != n:
            raise Invalid('seq must be ' + str(n))
        if e['prev'] != (self.ids[-1] if self.ids else self.id):
            raise Invalid('prev does not match the previous entry')
        if not is_time(e['time']):
            raise Invalid('bad time')
        if self.entries and e['time'] < self.entries[-1]['time']:
            raise Invalid('time goes backwards')
        check_message(e['msg'])
        if not verify(self.owner, unsigned(e), e['sig']):
            raise Invalid('entry signature does not verify with the owner key')
        m = e['msg']
        if seconds(e['time']) < seconds(m['at']) - SKEW:
            raise Invalid('message recorded more than ' + str(SKEW) + ' seconds before it was signed')
        if (n == 0) != (m['type'] == 'open'):
            raise Invalid('"open" is the first entry, and only the first')
        if m['type'] not in COUNTERPARTY and m['by'] != self.owner:
            raise Invalid(m['type'] + ' must be authored by the ledger owner')

    def next_entry(self, secret, msg, at=None):
        """A new signed entry recording msg on top of this ledger. Raises Invalid if it would not be valid."""
        if not self.whole:
            raise Invalid('the ledger is broken: ' + str(self.error))
        if public(secret) != self.owner:
            raise Invalid('this key is not the ledger owner key')
        t = at or now()
        if self.entries and t < self.entries[-1]['time']:
            t = self.entries[-1]['time']
        if seconds(t) < seconds(msg['at']) - SKEW:
            raise Invalid('the message is signed more than ' + str(SKEW) + ' seconds in the future')
        e = {'seq': len(self.entries), 'prev': self.ids[-1] if self.ids else self.id, 'time': t, 'msg': msg}
        e['sig'] = sign(secret, e)
        self.check_entry(len(self.entries), e)
        return e

    def append(self, entry):
        line = canon(entry)
        self.check_entry(len(self.entries), entry)
        self.entries.append(entry)
        self.ids.append(sha256(line))
        self.lines.append(line)
        self.data += line + b'\n'
        return self.ids[-1]

    def find(self, id_):
        """Index of the entry with this entry id, or None."""
        try:
            return self.ids.index(id_)
        except ValueError:
            return None


def new_ledger(secret, name, about, dex_url, at=None):
    """Header plus the "open" entry (spec 3.1, 5.1)."""
    header = {'ledger': 1, 'name': name, 'owner': public(secret)}
    led = Ledger(canon(header) + b'\n')
    t = at or now()
    led.append(led.next_entry(secret, message(secret, 'open', {'about': about, 'dex': dex_url}, at=t), at=t))
    return led

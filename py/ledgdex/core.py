"""Keys, messages, entries and ledger verification (spec 1-5)."""
import datetime, hashlib, json, os, re
from .sig import backend
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
    return 'ed25519:' + backend.public_key(secret).hex()


def sign(secret, obj):
    return backend.sign(secret, canon(obj)).hex()


def verify(key, obj, sig):
    if not is_key(key) or not isinstance(sig, str) or not SIG_RE.match(sig):
        return False
    return backend.verify(bytes.fromhex(key[8:]), canon(obj), bytes.fromhex(sig))


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


def _nonce(v):
    return isinstance(v, str) and bool(re.match(r'[0-9a-f]{32,}\Z', v))


def _entries(v):
    return isinstance(v, list) and all(_entry(x) for x in v)


def _auction(b):
    return b['close'] < b['reveal_until']


# type: (required fields, optional fields), field checks
BODIES = {
    'open': ({'about': _str, 'dex': _str}, {}),
    'admit': ({'key': is_key, 'name': _str, 'note': _str}, {}),
    'revoke': ({'key': is_key, 'reason': _str}, {}),
    'note': ({'ref': is_id, 'text': _str}, {}),
    'sent': ({'to': is_key, 'msg': lambda v: isinstance(v, dict)}, {}),
    'receipt': ({'ledger': is_id, 'url': _str, 'header': _header, 'entry': _entry}, {'keys': _entries}),
    'rotate': ({'key': is_key}, {}),
    'device': ({'key': is_key, 'name': _str}, {}),
    'device_revoke': ({'key': is_key, 'reason': _str}, {}),
    'dispute': ({'claim': is_id, 'text': _str, 'evidence': lambda v: isinstance(v, list) and all(map(_str, v))}, {}),
    'ruling': ({'dispute': is_id, 'outcome': lambda v: v in ('release', 'refund', 'split'), 'text': _str}, {}),
    'auction': ({'item': _item, 'currency': _str, 'close': is_time, 'reveal_until': is_time,
                 'best': lambda v: v in ('highest', 'lowest'), 'reserve': lambda v: _int(v) and v >= 0,
                 'allow': _allow, 'arbiter': _arbiter, 'terms': _str}, {}),
    'bid': ({'auction': is_id, 'commit': is_id}, {}),
    'reveal': ({'auction': is_id, 'amount': lambda v: _int(v) and v >= 0, 'nonce': _nonce}, {}),
    'list': ({'ledger': is_id, 'url': _str, 'owner': is_key, 'note': _str}, {}),
    'delist': ({'ledger': is_id, 'reason': _str}, {}),
    'recover': ({'ledger': is_id, 'key': is_key}, {}),
    'recovered': ({'root': is_id, 'entry': is_id}, {}),
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
# types someone other than the owner authors and the owner records (spec 4, 5.4-5.6)
COUNTERPARTY = {'claim', 'paid', 'confirmed', 'dispute', 'ruling', 'bid', 'reveal'}
# O-authored types only the owner key itself may author (spec 4)
OWNER_ONLY = {'open', 'rotate', 'device', 'device_revoke'}
KEY_TYPES = {'rotate', 'device', 'device_revoke', 'recovered'}


class Keys:
    """A ledger's signing keys as its entries change them (spec 5.1, 5.7, 6.1)."""

    def __init__(self, owner):
        self.owner = owner
        self.devices = set()

    def signing(self):
        return [self.owner] + sorted(self.devices)

    def can_author(self, type_, key):
        if type_ in OWNER_ONLY:
            return key == self.owner
        return key == self.owner or key in self.devices

    def signed_by(self, e):
        """The current signing key that signed entry e, or None."""
        for k in self.signing():
            if verify(k, unsigned(e), e['sig']):
                return k
        return None

    def apply(self, m):
        t, b = m['type'], m['body']
        if t == 'rotate':
            self.owner = b['key']
        elif t == 'device':
            self.devices.add(b['key'])
        elif t == 'device_revoke':
            self.devices.discard(b['key'])
        elif t == 'recovered':  # a recovery replaces every key: the lost one and the devices it authorised
            self.owner, self.devices = m['by'], set()


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
    if m['type'] == 'auction' and not _auction(m['body']):
        raise Invalid('auction: close must be before reveal_until')
    if not verify(m['by'], unsigned(m), m['sig']):
        raise Invalid('message signature does not verify')


def check_receipt(body):
    """A receipt verifies on its own (spec 5.1, invariant 10): the entry is signed by the other ledger's header key,
    or by a key that the key entries in "keys" (rotate, device, device_revoke, recovered, in order) lead to."""
    if hash_(body['header']) != body['ledger']:
        raise Invalid('receipt: header does not match ledger id')
    e = body['entry']
    keys, last = Keys(body['header']['owner']), -1
    for k in body.get('keys', []):
        if not last < k['seq'] < e['seq']:
            raise Invalid('receipt: key entries must be in order and before the entry')
        check_message(k['msg'])
        m = k['msg']
        if m['type'] not in KEY_TYPES:
            raise Invalid('receipt: keys may hold only rotate, device, device_revoke and recovered entries')
        if m['type'] == 'recovered':
            ok = verify(m['by'], unsigned(k), k['sig'])  # the recovery itself is checked against the root in full
        else:
            ok = keys.signed_by(k) is not None and keys.can_author(m['type'], m['by'])
        if not ok:
            raise Invalid('receipt: key entry ' + str(k['seq']) + ' does not verify')
        keys.apply(m)
        last = k['seq']
    if keys.signed_by(e) is None:
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

def cache_dir():
    return os.environ.get('LEDGDEX_CACHE') or os.path.join(
        os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache'), 'ledgdex')


class Ledger:
    """A parsed ledger. Verification stops at the first structurally invalid line (spec 3.3).

    Verified prefixes are cached (in ~/.cache/ledgdex, by ledger id, length and SHA-256 of the exact bytes), so a
    ledger that only grew is verified only from where it was verified before. Any changed byte misses the cache and
    is verified in full. cache=False, or LEDGDEX_NO_CACHE=1, always verifies everything."""

    def __init__(self, data, cache=True, root=None):
        self.use_cache = cache and not os.environ.get('LEDGDEX_NO_CACHE')
        self.root = root    # the root Ledger, needed to verify "recovered" entries (spec 5.7)
        self.keys = None    # current signing keys
        self.key_history = set()
        self.cached = 0     # entries taken from the cache instead of verified again
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
        self.keys = Keys(h['owner'])
        self.key_history = {h['owner']}
        hit = self._cache_get(len(lines) - 1)
        for n, line in enumerate(lines[1:]):
            if n < hit:  # these exact bytes were verified before
                self._add(json.loads(line), line)
                continue
            try:
                e = parse(line)
                self.check_entry(n, e)
            except (CanonError, Invalid) as err:
                self.broken_at, self.error = n, 'seq ' + str(n) + ': ' + str(err)
                return
            self._add(e, line)
        if partial:
            n = len(self.entries)
            self.broken_at, self.error = n, 'seq ' + str(n) + ': the line does not end with a newline'
        self.cached = hit
        if len(self.entries) > hit:
            self._cache_put()

    def _cache_path(self):
        return os.path.join(cache_dir(), 'verified', self.id[7:] + '.json')

    def _cache_get(self, available):
        """How many entries at the start of this data were verified before (0 if none)."""
        if not self.use_cache:
            return 0
        try:
            with open(self._cache_path()) as f:
                c = json.load(f)
            n, length = c['entries'], c['length']
            if (0 < n <= available and length <= len(self.data) and self.data[length - 1:length] == b'\n'
                    and hashlib.sha256(self.data[:length]).hexdigest() == c['sha256']):
                return n
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return 0

    def _cache_put(self):
        if not self.use_cache:
            return
        length = len(self.header_line) + 1 + sum(len(x) + 1 for x in self.lines)
        c = {'entries': len(self.lines), 'length': length, 'sha256': hashlib.sha256(self.data[:length]).hexdigest()}
        try:
            os.makedirs(os.path.dirname(self._cache_path()), exist_ok=True)
            tmp = self._cache_path() + '.' + str(os.getpid())
            with open(tmp, 'w') as f:
                json.dump(c, f)
            os.replace(tmp, self._cache_path())
        except OSError:
            pass  # the cache is only a shortcut

    def _add(self, e, line):
        self.entries.append(e)
        self.ids.append(sha256(line))
        self.lines.append(line)
        if e['msg']['type'] in KEY_TYPES:
            self.keys.apply(e['msg'])
            self.key_history |= {self.keys.owner} | self.keys.devices

    @property
    def owner(self):
        """The current owner key (the header's, until a rotate or a recovery)."""
        return self.keys.owner if self.keys else None

    @property
    def devices(self):
        return sorted(self.keys.devices) if self.keys else []

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
        m = e['msg']
        if m['type'] == 'recovered':
            self.check_recovery(e)
        elif self.keys.signed_by(e) is None:
            raise Invalid('entry signature does not verify with a current signing key')
        if seconds(e['time']) < seconds(m['at']) - SKEW:
            raise Invalid('message recorded more than ' + str(SKEW) + ' seconds before it was signed')
        if (n == 0) != (m['type'] == 'open'):
            raise Invalid('"open" is the first entry, and only the first')
        if m['type'] not in COUNTERPARTY and m['type'] != 'recovered' and not self.keys.can_author(m['type'], m['by']):
            raise Invalid(m['type'] + ' must be authored by the ledger owner' +
                          ('' if m['type'] in OWNER_ONLY else ' or an active device key'))

    def check_recovery(self, e):
        """Spec 5.7: a "recovered" entry is signed by the new key, which a "recover" entry in the root names."""
        m, b = e['msg'], e['msg']['body']
        if not verify(m['by'], unsigned(e), e['sig']):
            raise Invalid('recovered: the entry is not signed by the recovered key')
        root = self.root
        if root is None:
            raise Invalid('a "recovered" entry can only be verified with the root ledger')
        if root.id != b['root']:
            raise Invalid('recovered: names root ' + b['root'] + ', not the root given (' + str(root.id) + ')')
        i = root.find(b['entry'])
        r = root.entries[i]['msg'] if i is not None else None
        if r is None or r['type'] != 'recover' or r['body']['ledger'] != self.id or r['body']['key'] != m['by']:
            raise Invalid('recovered: the root has no recover entry for this ledger and key')

    def next_entry(self, secret, msg, at=None):
        """A new signed entry recording msg on top of this ledger. Raises Invalid if it would not be valid."""
        if not self.whole:
            raise Invalid('the ledger is broken: ' + str(self.error))
        signer = public(secret)
        if signer not in self.keys.signing() and not (msg['type'] == 'recovered' and msg['by'] == signer):
            raise Invalid('this key is not a signing key of this ledger')
        t = at or now()
        if self.entries and t < self.entries[-1]['time']:
            t = self.entries[-1]['time']
        if seconds(t) < seconds(msg['at']) - SKEW:
            raise Invalid('the message is signed more than ' + str(SKEW) + ' seconds in the future')
        e = {'seq': len(self.entries), 'prev': self.ids[-1] if self.ids else self.id, 'time': t, 'msg': msg}
        e['sig'] = sign(secret, e)
        return e

    def append(self, entry):
        """Verify entry on top of this ledger and add it. Raises Invalid if it is not valid."""
        line = canon(entry)
        self.check_entry(len(self.entries), entry)
        self._add(entry, line)
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

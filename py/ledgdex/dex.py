"""A ledgdex on disk: the ledger file in a dex, keys in ~/.ledgdex, and reading other ledgers."""
import contextlib, os, re, urllib.request
from .core import Ledger, Invalid, public

LEDGER = 'ledgdex.jsonl'


@contextlib.contextmanager
def inside(folder):
    """Run with folder as the working folder (dexweb works on the current folder)."""
    cwd = os.getcwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(cwd)


# ---------- keys (spec 7.1: private keys live outside the dex) ----------

def key_dir():
    return os.environ.get('LEDGDEX_HOME') or os.path.join(os.path.expanduser('~'), '.ledgdex')


def _key_name(name):
    if not re.match(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z', name):
        raise Invalid('a key name uses letters, digits, ".", "_" and "-"')


def keygen(name):
    """Write a new secret key to ~/.ledgdex/NAME.key (mode 600) and return its public key."""
    _key_name(name)
    os.makedirs(key_dir(), mode=0o700, exist_ok=True)
    path = os.path.join(key_dir(), name + '.key')
    if os.path.exists(path):
        raise Invalid(path + ' already exists')
    secret = os.urandom(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(secret.hex() + '\n')
    return public(secret)


def load_key(name):
    _key_name(name)
    path = os.path.join(key_dir(), name + '.key')
    if not os.path.exists(path):
        raise Invalid('no key named ' + name + ' in ' + key_dir())
    return _read_key(path)


def _read_key(path):
    """A secret key file, refused if anyone but its owner can read it (as ssh refuses private keys)."""
    if hasattr(os, 'getuid'):
        mode = os.stat(path).st_mode
        if mode & 0o077:
            raise Invalid(path + ' can be read by others (mode ' + oct(mode & 0o777) + '): run chmod 600 ' + path)
    with open(path) as f:
        return bytes.fromhex(f.read().strip())


def find_key(pub):
    """The secret key in ~/.ledgdex whose public key is pub."""
    d = key_dir()
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.endswith('.key'):
                try:
                    secret = _read_key(os.path.join(d, name))
                except Invalid:
                    raise
                except ValueError:  # not a key file
                    continue
                if len(secret) == 32 and public(secret) == pub:
                    return secret
    raise Invalid('the key for ' + pub + ' is not in ' + d)


def signer(led, owner_only=False):
    """The local secret key to append to led with: an active device key when this machine has one, else the owner
    key. owner_only: the owner key itself (owner-only types, and messages sent to other ledgers, which carry the
    self's identity)."""
    if not owner_only:
        for k in led.devices:
            try:
                return find_key(k)
            except Invalid:
                pass
    return find_key(led.owner)


# ---------- this dex's ledger ----------

def ledger_path(dex):
    return os.path.join(dex, LEDGER)


def load(dex, root=None):
    path = ledger_path(dex)
    if not os.path.exists(path):
        raise Invalid('no ' + LEDGER + ' in ' + dex + '. Run "ledgdex init" first')
    with open(path, 'rb') as f:
        led = Ledger(f.read(), root=root or load_root(dex))
    if not led.whole:
        raise Invalid(LEDGER + ' is broken: ' + str(led.error))
    return led


@contextlib.contextmanager
def locked(dex):
    """One writer at a time: two appends at once would both take the next seq, and the second would break the
    ledger. The lock file stays in the dex folder (dexweb publishes only gen/)."""
    with open(os.path.join(dex, '.ledgdex.lock'), 'a') as f:
        try:
            import fcntl
        except ImportError:  # Windows: no lock
            yield
            return
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def record(dex, msgs, at=None, secret=None, root=None):
    """Record messages in this dex's ledger. Only appends. Returns the entry ids. Signed with secret, or with the
    key signer() picks."""
    with locked(dex):
        led = load(dex, root=root)
        start = len(led.lines)
        ids = []
        for m in msgs:
            key = secret or signer(led)
            ids.append(led.append(led.next_entry(key, m, at=at)))
        with open(ledger_path(dex), 'ab') as f:
            f.write(b''.join(line + b'\n' for line in led.lines[start:]))
            f.flush()
            os.fsync(f.fileno())
    return ids


def write(dex, data):
    """Replace the ledger file (only for re-sequencing unpublished entries, spec 3.5). The caller holds locked(dex)."""
    tmp = ledger_path(dex) + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ledger_path(dex))


# ---------- other ledgers ----------

def load_root(dex):
    """The root ledger named in config.json ("ledgdex": {"root": SOURCE}), or None."""
    import json
    p = os.path.join(dex, 'config.json')
    try:
        with open(p) as f:
            src = json.load(f).get('ledgdex', {}).get('root')
    except (OSError, ValueError, AttributeError):
        return None
    return fetch(src)[0] if src else None


MAX_BYTES = int(os.environ.get('LEDGDEX_MAX_BYTES') or 64 << 20)   # the most read from any one address


class _HttpOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not re.match(r'https?://', newurl):
            raise Invalid('refused a redirect to ' + newurl + ': only http(s) is followed')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_HttpOnly)


def http_get(url, limit=None):
    """The bytes at an http(s) address, at most limit (default MAX_BYTES) of them."""
    limit = limit or MAX_BYTES
    if not re.match(r'https?://', url):
        raise Invalid('only http(s) addresses are read: ' + url)
    req = urllib.request.Request(url, headers={'User-Agent': 'ledgdex'})
    with _opener.open(req, timeout=30) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise Invalid(url + ' is larger than ' + str(limit) + ' bytes (LEDGDEX_MAX_BYTES)')
    return data


def fetch(src, cache=True, root=None, remote=False):
    """Read a ledger from a dex folder, a file, or a dex URL. Returns (Ledger, url). remote: src came from a ledger
    (a receipt, a listing), so besides http(s) only a dex folder or a .jsonl file is read (ledgers kept on one
    machine), never any other local file."""
    if re.match(r'https?://', src):
        url = src if src.endswith('.jsonl') else src.rstrip('/') + '/' + LEDGER
        return Ledger(http_get(url), cache, root), url
    if re.match(r'[A-Za-z][A-Za-z0-9+.-]*:', src) and not os.path.exists(src):
        raise Invalid('only http(s) addresses, dex folders and ledger files are read: ' + src)
    path = os.path.join(src, LEDGER) if os.path.isdir(src) else src
    if remote and not path.endswith('.jsonl'):
        raise Invalid('a ledger names ' + src + ': only http(s) addresses, dex folders and .jsonl files are read')
    if os.path.getsize(path) > MAX_BYTES:
        raise Invalid(path + ' is larger than ' + str(MAX_BYTES) + ' bytes (LEDGDEX_MAX_BYTES)')
    with open(path, 'rb') as f:
        return Ledger(f.read(), cache, root), os.path.abspath(path)

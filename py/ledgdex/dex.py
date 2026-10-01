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


def keygen(name):
    """Write a new secret key to ~/.ledgdex/NAME.key (mode 600) and return its public key."""
    if not re.match(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z', name):
        raise Invalid('a key name uses letters, digits, ".", "_" and "-"')
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
    path = os.path.join(key_dir(), name + '.key')
    if not os.path.exists(path):
        raise Invalid('no key named ' + name + ' in ' + key_dir())
    return _read_key(path)


def _read_key(path):
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
                except ValueError:
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


def record(dex, msgs, at=None, secret=None, root=None):
    """Record messages in this dex's ledger. Only appends. Returns the entry ids. Signed with secret, or with the
    key signer() picks."""
    led = load(dex, root=root)
    start = len(led.lines)
    ids = []
    for m in msgs:
        key = secret or signer(led)
        ids.append(led.append(led.next_entry(key, m, at=at)))
    with open(ledger_path(dex), 'ab') as f:
        f.write(b''.join(line + b'\n' for line in led.lines[start:]))
    return ids


def write(dex, data):
    """Replace the ledger file (only for re-sequencing unpublished entries, spec 3.5)."""
    tmp = ledger_path(dex) + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
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


def fetch(src, cache=True, root=None):
    """Read a ledger from a dex folder, a file, or a dex URL. Returns (Ledger, url)."""
    if re.match(r'https?://', src):
        url = src if src.endswith('.jsonl') else src.rstrip('/') + '/' + LEDGER
        req = urllib.request.Request(url, headers={'User-Agent': 'ledgdex'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return Ledger(r.read(), cache, root), url
    path = os.path.join(src, LEDGER) if os.path.isdir(src) else src
    with open(path, 'rb') as f:
        return Ledger(f.read(), cache, root), os.path.abspath(path)

"""Canonical JSON (spec 1.2): the exact bytes that are hashed and signed."""
import hashlib, json, re

KEY = re.compile(r'[a-z][a-z0-9_]*\Z')
ID_KEY = re.compile(r'[\x21-\x7e]+\Z')  # state output (spec 6.3) is keyed by ids: printable ASCII
MAX_INT = 2 ** 53 - 1


class CanonError(ValueError):
    pass


def check(v, keys=KEY):
    """Raise CanonError unless v follows rules 1-3."""
    if v is None or isinstance(v, bool):
        return
    if isinstance(v, int):
        if not -MAX_INT <= v <= MAX_INT:
            raise CanonError('integer out of range')
        return
    if isinstance(v, float):
        raise CanonError('floats are not allowed')
    if isinstance(v, str):
        try:
            v.encode('utf-8')
        except UnicodeEncodeError:
            raise CanonError('string is not valid Unicode')
        return
    if isinstance(v, list):
        for x in v:
            check(x, keys)
        return
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str) or not keys.match(k):
                raise CanonError('bad key: ' + repr(k))
            check(x, keys)
        return
    raise CanonError('value of type ' + type(v).__name__ + ' is not allowed')


def canon(v, keys=KEY):
    """canon(x): canonical JSON bytes. keys=ID_KEY only for the state object, whose keys are ids."""
    check(v, keys)
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def hash_(v):
    """hash(x) = "sha256:" + hex(SHA-256(canon(x)))."""
    return sha256(canon(v))


def _pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise CanonError('duplicate key: ' + k)
        d[k] = v
    return d


def _no_float(s):
    raise CanonError('floats are not allowed')


def _no_constant(s):
    raise CanonError(s + ' is not allowed')


def parse(data):
    """Parse bytes that MUST already be canonical JSON. Returns the value or raises CanonError."""
    if isinstance(data, str):
        data = data.encode('utf-8')
    try:
        v = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                       parse_float=_no_float, parse_constant=_no_constant)
    except CanonError:
        raise
    except ValueError as e:
        raise CanonError('not JSON: ' + str(e))
    if canon(v) != data:
        raise CanonError('not canonical JSON')
    return v

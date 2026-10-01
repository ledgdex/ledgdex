"""Pure Ed25519 (RFC 8032, section 5.1), after the Python reference code in RFC 8032 section 6.
Standard library only. Not constant time: fine for public ledgers, not for keys on shared machines."""
import hashlib

p = 2 ** 255 - 19
q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x):
    return pow(x, p - 2, p)


d = -121665 * _inv(121666) % p
_sqrt_m1 = pow(2, (p - 1) // 4, p)


def _sha512_modq(data):
    return int.from_bytes(hashlib.sha512(data).digest(), 'little') % q


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C = 2 * P[3] * Q[3] * d % p
    D = 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % p == 0


def _recover_x(y, sign):
    if y >= p:
        return None
    x2 = (y * y - 1) * _inv(d * y * y + 1) % p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p != 0:
        x = x * _sqrt_m1 % p
    if (x * x - x2) % p != 0:
        return None
    if (x & 1) != sign:
        x = p - x
    return x


_gy = 4 * _inv(5) % p
_gx = _recover_x(_gy, 0)
G = (_gx, _gy, 1, _gx * _gy % p)


def _compress(P):
    zinv = _inv(P[2])
    x, y = P[0] * zinv % p, P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, 'little')
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % p)


def _expand(secret):
    if len(secret) != 32:
        raise ValueError('an Ed25519 secret key is 32 bytes')
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], 'little')
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret):
    """32-byte public key for a 32-byte secret key."""
    a, _ = _expand(secret)
    return _compress(_mul(a, G))


def sign(secret, msg):
    """64-byte signature of msg (bytes)."""
    a, prefix = _expand(secret)
    A = _compress(_mul(a, G))
    r = _sha512_modq(prefix + msg)
    Rs = _compress(_mul(r, G))
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % q
    return Rs + int.to_bytes(s, 32, 'little')


_IDENTITY = (0, 1, 1, 0)


def small_order(public):
    """True for the eight public keys of small order (or a non-point). For such a key, one signature verifies for
    every message, so anyone could sign as it: no ledger accepts one."""
    A = _decompress(public) if len(public) == 32 else None
    return A is None or _equal(_mul(8, A), _IDENTITY)


def verify(public, msg, signature):
    """True if signature (64 bytes) is public's (32 bytes) signature of msg. Small-order keys never verify."""
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _decompress(public)
    if A is None or _equal(_mul(8, A), _IDENTITY):
        return False
    Rs = signature[:32]
    R = _decompress(Rs)
    if R is None:
        return False
    s = int.from_bytes(signature[32:], 'little')
    if s >= q:
        return False
    h = _sha512_modq(Rs + public + msg)
    return _equal(_mul(s, G), _add(R, _mul(h, A)))

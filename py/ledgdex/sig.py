"""Ed25519 backends. The vendored pure-Python code (ed25519.py) always works; when the "cryptography" package is
installed, ledgdex uses it instead, about 50 times faster. Both are held to the same rules: the backend must pass a
known-answer test before it is used, and every verification first rejects what the vendored code rejects (a
non-canonical s or point encoding), so a ledger reads the same with either backend. LEDGDEX_PURE=1 forces the
vendored code."""
import os
from . import ed25519

# RFC 8032 section 7.1, TEST 1 (vectors/ed25519.json, row 0)
_KAT_SECRET = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
_KAT_PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
_KAT_SIG = bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')


class _Pure:
    name = 'pure'
    public_key = staticmethod(ed25519.public_key)
    sign = staticmethod(ed25519.sign)
    verify = staticmethod(ed25519.verify)


class _Cryptography:
    name = 'cryptography'

    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
        self._priv, self._pub, self._bad = Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature
        self._raw = (serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def public_key(self, secret):
        return self._priv.from_private_bytes(secret).public_key().public_bytes(*self._raw)

    def sign(self, secret, msg):
        return self._priv.from_private_bytes(secret).sign(msg)

    def verify(self, public, msg, signature):
        if len(public) != 32 or len(signature) != 64 or not _canonical(public) or not _canonical(signature[:32]):
            return False
        if int.from_bytes(signature[32:], 'little') >= ed25519.q:
            return False
        try:
            self._pub.from_public_bytes(public).verify(signature, msg)
            return True
        except self._bad:
            return False
        except ValueError:
            return False


def _canonical(point):
    # the y coordinate (low 255 bits) must be below p, as the vendored decoder requires
    return int.from_bytes(point, 'little') & ((1 << 255) - 1) < ed25519.p


def _passes(b):
    return (b.public_key(_KAT_SECRET) == _KAT_PUBLIC and b.sign(_KAT_SECRET, b'') == _KAT_SIG
            and b.verify(_KAT_PUBLIC, b'', _KAT_SIG) and not b.verify(_KAT_PUBLIC, b'x', _KAT_SIG))


def _choose():
    if os.environ.get('LEDGDEX_PURE'):
        return _Pure()
    try:
        b = _Cryptography()
        if _passes(b):
            return b
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # not installed, or broken (a broken install can raise outside Exception)
        pass
    return _Pure()


backend = _choose()
pure = _Pure()

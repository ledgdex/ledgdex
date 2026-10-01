import json, os, unittest
import helpers  # noqa: F401
from ledgdex import ed25519

VECTORS = os.path.join(os.path.dirname(__file__), '..', '..', 'vectors', 'ed25519.json')


class Ed25519(unittest.TestCase):
    def test_vectors(self):
        with open(VECTORS) as f:
            rows = json.load(f)['vectors']
        self.assertEqual(len(rows), 19)
        for r in rows:
            sk, pk, msg, sig = (bytes.fromhex(r[k]) for k in ('secret', 'public', 'message', 'signature'))
            self.assertEqual(ed25519.public_key(sk), pk)
            self.assertEqual(ed25519.sign(sk, msg), sig)
            self.assertTrue(ed25519.verify(pk, msg, sig))
            self.assertFalse(ed25519.verify(pk, msg + b'.', sig))
            self.assertFalse(ed25519.verify(pk, msg, sig[:63] + bytes([sig[63] ^ 1])))

    def test_bad_inputs(self):
        pk = ed25519.public_key(bytes(32))
        self.assertFalse(ed25519.verify(pk, b'', bytes(63)))
        self.assertFalse(ed25519.verify(pk[:31], b'', bytes(64)))
        sig = ed25519.sign(bytes(32), b'm')
        s = int.from_bytes(sig[32:], 'little') + ed25519.q  # non-canonical s
        self.assertFalse(ed25519.verify(pk, b'm', sig[:32] + s.to_bytes(32, 'little')))


if __name__ == '__main__':
    unittest.main()

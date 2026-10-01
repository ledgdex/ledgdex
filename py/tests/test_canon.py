import unittest
import helpers  # noqa: F401
from ledgdex.canon import canon, parse, hash_, CanonError, ID_KEY


class Canon(unittest.TestCase):
    def test_order_and_spacing(self):
        self.assertEqual(canon({'b': 1, 'a': [True, False, None, {'z': 'x', 'c': -5}]}),
                         b'{"a":[true,false,null,{"c":-5,"z":"x"}],"b":1}')

    def test_escapes(self):
        self.assertEqual(canon('"\\\b\f\n\r\t\x00\x1f\x7f/'), b'"\\"\\\\\\b\\f\\n\\r\\t\\u0000\\u001f\x7f/"')

    def test_unicode_is_written_as_itself(self):
        self.assertEqual(canon('आम 🥭'), '"आम 🥭"'.encode('utf-8'))

    def test_integer_limits(self):
        canon(2 ** 53 - 1)
        canon(-(2 ** 53 - 1))
        for v in (2 ** 53, -(2 ** 53)):
            self.assertRaises(CanonError, canon, v)

    def test_rejected_values(self):
        for v in (1.5, {'A': 1}, {'1a': 1}, {'a-b': 1}, {'é': 1}, '\ud800', b'x', (1,)):
            self.assertRaises(CanonError, canon, v)

    def test_bool_stays_boolean(self):
        self.assertEqual(canon([True, 1]), b'[true,1]')

    def test_parse_requires_canonical_bytes(self):
        self.assertEqual(parse(b'{"a":1}'), {'a': 1})
        for bad in (b'{ "a":1}', b'{"b":1,"a":2}', b'{"a":1,"a":1}', b'{"a":1.0}', b'NaN', b'{"a":"\\u00e9"}',
                    b'{"a":1}\n'):
            self.assertRaises(CanonError, parse, bad)

    def test_hash(self):
        self.assertEqual(hash_({}), 'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a')

    def test_state_keys(self):
        self.assertEqual(canon({'sha256:ab': 1}, ID_KEY), b'{"sha256:ab":1}')
        self.assertRaises(CanonError, canon, {'sha256:ab': 1})


if __name__ == '__main__':
    unittest.main()

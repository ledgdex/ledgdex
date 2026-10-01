import os, unittest
from make_vectors import ROOT, build


class Vectors(unittest.TestCase):
    def test_vectors_are_up_to_date(self):
        """Run "python tests/make_vectors.py" after changing behaviour; JavaScript is tested against these files."""
        for path, content in build().items():
            with open(os.path.join(ROOT, path), 'rb') as f:
                want = content if isinstance(content, bytes) else content.encode('utf-8')
                self.assertEqual(f.read(), want, path)


if __name__ == '__main__':
    unittest.main()

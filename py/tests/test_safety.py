"""Invariant 14: whatever a ledger holds, its pages carry only text, <code>, <br> and safe links. Checked on every page
of every shared vector (JavaScript renders the same bytes), including ledgers that put markup in every free text."""
import html.parser, json, os, re, unittest
import helpers  # noqa: F401
from ledgdex.render import MARKER

PAGES = os.path.join(os.path.dirname(__file__), '..', '..', 'vectors', 'pages.json')
SAFE_HREF = re.compile(r"(https?://[^\x00-\x20\x7f]+|[^\W_A-Z]+\.html|ledgdex\.jsonl)\Z")


class Audit(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bad = []

    def handle_starttag(self, tag, attrs):
        if tag not in ('a', 'code', 'br'):
            self.bad.append('tag ' + tag)
        for k, v in attrs:
            if tag != 'a' or k not in ('href', 'rel'):
                self.bad.append('attribute ' + tag + ' ' + k)
            elif k == 'href' and not SAFE_HREF.match(v or ''):
                self.bad.append('href ' + repr(v))
            elif k == 'rel' and v != 'nofollow noopener noreferrer':
                self.bad.append('rel ' + repr(v))

    def handle_endtag(self, tag):
        if tag not in ('a', 'code'):
            self.bad.append('end tag ' + tag)

    def handle_comment(self, data):
        if '<!--' + data + '-->' != MARKER:
            self.bad.append('comment ' + data)

    def handle_decl(self, decl):
        self.bad.append('declaration ' + decl)

    def handle_pi(self, data):
        self.bad.append('processing instruction ' + data)


class PagesCarryOnlyText(unittest.TestCase):
    def test_every_vector_page(self):
        with open(PAGES, encoding='utf-8') as f:
            rendered = json.load(f)
        self.assertIn('hostile-text', rendered)
        self.assertIn('hostile-buyer', rendered)
        n = 0
        for name, pages in rendered.items():
            for page in pages:
                for part in [page['title']] + page['body']:
                    a = Audit()
                    a.feed(part)
                    a.close()
                    self.assertEqual([], a.bad, (name, page['title'], part))
                    n += 1
        self.assertGreater(n, 100)

    def test_titles_carry_no_markup(self):
        # dexweb writes titles into <title>, <h1> and the index as they are
        with open(PAGES, encoding='utf-8') as f:
            for pages in json.load(f).values():
                for page in pages:
                    self.assertNotRegex(page['title'], '[<>"]', page['title'])


class DexPagesCarryOnlyTheTemplate(unittest.TestCase):
    def test_no_markup_from_a_ledger_in_any_built_dex(self):
        # the dex name is written unescaped by dexweb: a hostile ledger name must not become markup (render.dex_name)
        root = os.path.join(os.path.dirname(__file__), '..', '..', 'vectors', 'dex')
        pages = 0
        for dirpath, _, names in os.walk(root):
            for n in names:
                if n.endswith('.html'):
                    with open(os.path.join(dirpath, n), encoding='utf-8') as f:
                        text = f.read().lower()
                    self.assertNotIn('<img', text, n)
                    self.assertNotIn('<script>x', text, n)
                    self.assertNotRegex(text, r'<[^>]*\son\w+=', n)
                    pages += 1
        self.assertGreater(pages, 10)

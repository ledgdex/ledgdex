"""The docs' examples (guide/examples/) are run as they are printed in the docs: each in an empty folder with its
own key store, and each must exit 0 and print every line its "expect:" comments name. The docs pages include these
files verbatim, so a published example is a tested one."""
import os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, '..', '..', 'guide', 'examples')
JS = os.path.join(HERE, '..', '..', 'js')


def examples():
    return sorted(f for f in os.listdir(EXAMPLES) if re.match(r'\d\d-.*\.(sh|py|mjs)$', f))


def expected(path):
    with open(path, encoding='utf-8') as f:
        return re.findall(r'^\s*(?:#|//) expect: (.*)$', f.read(), re.M)


class Examples(unittest.TestCase):
    maxDiff = None

    def run_example(self, name):
        path = os.path.join(EXAMPLES, name)
        tmp = tempfile.mkdtemp(prefix='ledgdex-example-')
        self.addCleanup(shutil.rmtree, tmp, True)
        bin_ = os.path.join(tmp, '.bin')        # "python3" and "ledgdex" are the ones under test
        os.makedirs(bin_)
        os.symlink(sys.executable, os.path.join(bin_, 'python3'))
        with open(os.path.join(bin_, 'ledgdex'), 'w') as f:
            f.write('#!/bin/sh\nexec "' + sys.executable + '" -m ledgdex.cli "$@"\n')
        os.chmod(os.path.join(bin_, 'ledgdex'), 0o755)
        work = os.path.join(tmp, 'work')
        os.makedirs(work)
        env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ.get('PATH', ''),
                   LEDGDEX_HOME=os.path.join(tmp, 'keys'), LEDGDEX_JS=os.path.abspath(JS) + '/',
                   PYTHONPATH=os.path.abspath(os.path.join(HERE, '..')),
                   GIT_AUTHOR_NAME='docs', GIT_AUTHOR_EMAIL='docs@example', GIT_COMMITTER_NAME='docs',
                   GIT_COMMITTER_EMAIL='docs@example', GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        env.pop('LEDGDEX_NO_CACHE', None)
        cmd = {'.sh': ['sh', path], '.py': [sys.executable, path], '.mjs': ['node', path]}[os.path.splitext(name)[1]]
        r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=600)
        out = r.stdout + r.stderr
        self.assertEqual(0, r.returncode, name + ' failed:\n' + out[-3000:])
        for line in expected(path):
            self.assertIn(line, out, name + ' did not print ' + repr(line) + ':\n' + out[-3000:])

    def test_every_example_names_what_it_must_print(self):
        self.assertGreaterEqual(len(examples()), 10)
        for name in examples():
            self.assertTrue(expected(os.path.join(EXAMPLES, name)), name + ' has no "expect:" lines')


class DocsPages(unittest.TestCase):
    """The docs dex (guide/, published to docs/docs/) agrees with the code."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, '..', '..', 'guide'))
        import pages
        cls.pages = pages

    def test_every_message_body_shown_is_valid(self):
        from ledgdex.core import check_body
        for type_, _, _, body in self.pages.MESSAGE_TYPES:
            check_body(type_, body)          # raises if the docs show a body the code refuses

    def test_every_example_has_a_page(self):
        self.assertEqual(sorted(self.pages.EXAMPLE_PAGES), examples())

    def test_every_command_and_option_is_documented(self):
        from ledgdex.cli import parser
        import argparse
        text = '\n'.join(b for p in self.pages.pages() for b in p['body'])
        sub = next(a for a in parser()._actions if isinstance(a, argparse._SubParsersAction))
        for name, sp in sub.choices.items():
            self.assertIn('ledgdex ' + name, text)
            for action in sp._actions:
                for opt in action.option_strings:
                    self.assertIn(opt, text, name + ' ' + opt)

    def test_published_docs_links_resolve(self):
        docs = os.path.join(HERE, '..', '..', 'docs', 'docs')
        if not os.path.isdir(docs):
            self.skipTest('docs/docs not built')
        files = [f for f in os.listdir(docs) if f.endswith('.html')]
        self.assertGreater(len(files), 40)
        ids = {}
        for f in files:
            with open(os.path.join(docs, f), encoding='utf-8') as fh:
                ids[f] = fh.read()
        for f, text in ids.items():
            self.assertNotIn('<script', text, f)              # the docs run no scripts (and a CSP says so)
            self.assertIsNone(re.search(r'<(b|strong)[ >]', text), f)   # no bold text
            for h in re.findall(r"href=['\"]?([^'\" >]+)", text):
                if h.startswith(('http://', 'https://')):
                    continue
                target, _, anchor = h.partition('#')
                target = target or f
                self.assertTrue(os.path.exists(os.path.join(docs, target)), f + ' links to ' + h)
                if anchor and target.endswith('.html'):
                    self.assertIn("id='" + anchor + "'", ids[target], f + ' links to ' + h)


def _make(name):
    return lambda self: self.run_example(name)


for _name in examples():
    setattr(Examples, 'test_' + re.sub(r'\W', '_', _name), _make(_name))


if __name__ == '__main__':
    unittest.main()

"""The docs' examples (guide/examples/) are run as they are: each in an empty folder with its own key store, and each
must exit 0 and print every line its "expect:" comments name. The docs show every line of each file but its comments
(which become the paragraphs) and its expect: lines, so a published example is a tested one. JavaScript examples run
in node with https://ledgdex.github.io/ served from this repository (offline.mjs); a web page example runs its
module script in node with a small stand-in for the DOM (page.mjs).

These tests check the command line, not the docs pages: they read guide/examples/ and guide/tutorial.md, never
guide/dex/data.json. The docs pages are free to change by hand."""
import os, pathlib, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, '..', '..', 'guide', 'examples')
JS = os.path.join(HERE, '..', '..', 'js')


def examples():
    return sorted(f for f in os.listdir(EXAMPLES) if re.match(r'\d\d-.*\.(sh|py|mjs|html)$', f))


def expected(path):
    with open(path, encoding='utf-8') as f:
        return re.findall(r'^\s*(?:#|//|<!--) expect: (.*?)(?: -->)?$', f.read(), re.M)


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
        offline = ['--import', pathlib.Path(HERE, 'offline.mjs').as_uri()]     # https://ledgdex.github.io/ from this repo
        cmd = {'.sh': ['sh', path], '.py': [sys.executable, path], '.mjs': ['node'] + offline + [path],
               '.html': ['node'] + offline + [os.path.join(HERE, 'page.mjs'), path]}[os.path.splitext(name)[1]]
        r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=600)
        out = r.stdout + r.stderr
        self.assertEqual(0, r.returncode, name + ' failed:\n' + out[-3000:])
        for line in expected(path):
            self.assertIn(line, out, name + ' did not print ' + repr(line) + ':\n' + out[-3000:])

    def test_every_example_names_what_it_must_print(self):
        self.assertGreaterEqual(len(examples()), 10)
        for name in examples():
            self.assertTrue(expected(os.path.join(EXAMPLES, name)), name + ' has no "expect:" lines')


class Tutorial(unittest.TestCase):
    """The Tutorial page (guide/tutorial.md) is run as a reader runs it: its command blocks in order in one shell,
    in an empty folder, and the output must contain every line of its expected-output blocks. So a reader who passes
    the tutorial ran commands that work."""

    def test_the_tutorial_runs_and_prints_what_it_expects(self):
        import tutorial
        with tempfile.TemporaryDirectory(prefix='ledgdex-tutorial-') as tmp:
            code, problems = tutorial.run(tmp)
        self.assertEqual([], problems)
        self.assertEqual(0, code)

    def test_the_tutorial_uses_every_command_and_option(self):
        import tutorial
        sys.path.insert(0, os.path.join(HERE, '..'))
        from ledgdex.cli import parser
        commands = '\n'.join(text for kind, text in tutorial.blocks() if kind == 'sh')
        sub = next(a for a in parser()._actions if a.__class__.__name__ == '_SubParsersAction')
        for name, sp in sub.choices.items():
            self.assertRegex(commands, r'ledgdex ' + name + r'\b', name)
            for action in sp._actions:
                for opt in action.option_strings:
                    if opt not in ('-h', '--help'):
                        self.assertIn(' ' + opt, commands, 'ledgdex ' + name + ' ' + opt)


def _make(name):
    return lambda self: self.run_example(name)


for _name in examples():
    setattr(Examples, 'test_' + re.sub(r'\W', '_', _name), _make(_name))


if __name__ == '__main__':
    unittest.main()

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


def _make(name):
    return lambda self: self.run_example(name)


for _name in examples():
    setattr(Examples, 'test_' + re.sub(r'\W', '_', _name), _make(_name))


if __name__ == '__main__':
    unittest.main()

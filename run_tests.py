"""Run the ledgdex tests, from a clone of the repository or from the source package on PyPI. Two suites:

    python run_tests.py            essential (about 30 s): every Python test except the docs examples and the
                                   tutorial, with the fast backend, and the JavaScript vectors. For small changes.
    python run_tests.py --full     full (about 10 min): every Python test, with the examples and the tutorial, on
                                   both Ed25519 backends; the JavaScript vectors; differential fuzzing. For bigger
                                   changes, before a release, and before an upload to PyPI.

Install ledgdex first ("pip install -e .[fast]" in this folder). The tests also need git and node 20 or later. Each
part prints one line; the exit code is 0 only when every part passed."""
import argparse, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, 'py')


SLOW = {'test_guide'}   # the 15 docs examples and the tutorial: most of the time of the Python tests


def parts(full, seed):
    js = ('JavaScript core against the shared vectors', ['node', os.path.join(HERE, 'js', 'test.mjs')], HERE, {})
    if not full:
        names = sorted(f[:-3] for f in os.listdir(os.path.join(PY, 'tests'))
                       if f.startswith('test_') and f.endswith('.py') and f[:-3] not in SLOW)
        return [('Python tests, essential (fast backend, without the docs examples and the tutorial)',
                 [sys.executable, '-m', 'unittest'] + names, os.path.join(PY, 'tests'), {}), js]
    unit = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']
    return [('Python tests, all, fast backend (cryptography)', unit, PY, {}), js,
            ('Python tests, all, pure Ed25519, no verification cache', unit, PY,
             {'LEDGDEX_PURE': '1', 'LEDGDEX_NO_CACHE': '1'}),
            ('Differential fuzzing, Python against JavaScript (seed ' + str(seed) + ')',
             [sys.executable, os.path.join('tests', 'fuzz.py'), '--seed', str(seed), '--ledgers', '100',
              '--texts', '1000', '--keep', 'fuzz-out'], PY, {})]


def missing():
    """What the tests need that this computer does not have."""
    need = []
    for tool in ('git', 'node'):
        if shutil.which(tool) is None:
            need.append(tool)
    try:
        import ledgdex, dexweb  # noqa: F401
    except ImportError as e:
        need.append('ledgdex and dexweb in this Python (' + str(e) + '): run pip install -e ".[fast]"')
    if not os.path.isdir(os.path.join(HERE, 'vectors')):
        need.append('the folder vectors/: run this from a clone or from the source package, not from a wheel')
    return need


def main(argv=None):
    ap = argparse.ArgumentParser(description='Run the ledgdex tests: the essential suite, or with --full all of them.')
    ap.add_argument('--full', action='store_true', help='the full suite (about 10 min): for bigger changes and releases')
    ap.add_argument('--seed', type=int, default=1, help='the fuzzing seed (default 1)')
    ap.add_argument('--verbose', action='store_true', help='show the output of each part')
    a = ap.parse_args(argv)
    need = missing()
    if need:
        print('cannot run the tests. Missing: ' + '; '.join(need))
        return 1
    import ledgdex
    print('testing the code in ' + os.path.join(PY, 'ledgdex') + '. The ledgdex command here is ' +
          ledgdex.__version__ + ' from ' + os.path.dirname(ledgdex.__file__), flush=True)
    failed = 0
    print(('full' if a.full else 'essential') + ' suite', flush=True)
    for name, cmd, cwd, env in parts(a.full, a.seed):
        start = time.time()
        r = subprocess.run(cmd, cwd=cwd, env=dict(os.environ, **env), capture_output=not a.verbose, text=True)
        ok = r.returncode == 0
        failed += not ok
        print(('passed' if ok else 'FAILED') + ': ' + name + ' (' + str(round(time.time() - start)) + ' s)', flush=True)
        if not ok and not a.verbose:
            print((r.stdout + r.stderr)[-4000:])
    print('all tests passed' if not failed else str(failed) + ' part(s) failed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())

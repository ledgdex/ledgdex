"""Run every ledgdex test, from a clone of the repository or from the source package on PyPI:

    python run_tests.py            all parts
    python run_tests.py --quick    only the Python tests with the fast backend, and the JavaScript vectors

Install ledgdex first ("pip install -e .[fast]" in this folder). The tests also need git and node 20 or later. Each
part prints one line; the exit code is 0 only when every part passed."""
import argparse, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, 'py')


def parts(quick, seed):
    unit = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']
    out = [('Python tests, fast backend (cryptography)', unit, PY, {}),
           ('JavaScript core against the shared vectors', ['node', os.path.join(HERE, 'js', 'test.mjs')], HERE, {})]
    if not quick:
        out += [('Python tests, pure Ed25519, no verification cache', unit, PY,
                 {'LEDGDEX_PURE': '1', 'LEDGDEX_NO_CACHE': '1'}),
                ('Differential fuzzing, Python against JavaScript (seed ' + str(seed) + ')',
                 [sys.executable, os.path.join('tests', 'fuzz.py'), '--seed', str(seed), '--ledgers', '100',
                  '--texts', '1000'], PY, {})]
    return out


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
    ap = argparse.ArgumentParser(description='Run every ledgdex test.')
    ap.add_argument('--quick', action='store_true', help='only the fast backend and the JavaScript vectors')
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
    for name, cmd, cwd, env in parts(a.quick, a.seed):
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

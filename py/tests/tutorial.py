"""Run the docs tutorial (guide/tutorial.md) as a reader runs it, and check its expected output.

The tutorial has two kinds of fenced blocks: ```sh blocks are commands, run in order in one bash process (later blocks
use the variables of earlier ones); an ```expect block names lines that the output of the commands since the last
```expect block must contain. A trap stops the tutorial's web server if a block fails.

    python py/tests/tutorial.py            run it in a new temporary folder and report"""
import os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TUTORIAL = os.path.join(HERE, '..', '..', 'guide', 'tutorial.md')
MARK = '@@ledgdex-tutorial-block {}@@'


def blocks(path=TUTORIAL):
    """[(kind, text)] for the ```sh and ```expect blocks, in order."""
    with open(path, encoding='utf-8') as f:
        return [(m.group(1), m.group(2)) for m in re.finditer(r'^```(sh|expect)\n(.*?)^```$', f.read(), re.M | re.S)]


def run(workdir, path=TUTORIAL, timeout=900):
    """Run the tutorial in workdir. Returns (exit code, [problems]); no problems means the reader passed."""
    script = ['set -euo pipefail', 'trap \'[ -n "${SERVER:-}" ] && kill "$SERVER" 2>/dev/null || true\' EXIT']
    checks, n = [], 0
    for kind, text in blocks(path):
        if kind == 'sh':
            n += 1
            script += ['echo "' + MARK.format(n) + '"', text]
        else:
            checks.append((n, [line for line in text.split('\n') if line.strip()]))
    env = dict(os.environ)
    env.pop('LEDGDEX_HOME', None)
    env.pop('LEDGDEX_CACHE', None)
    r = subprocess.run(['bash', '-c', '\n'.join(script)], cwd=workdir, env=env, capture_output=True, text=True,
                       timeout=timeout)
    out = r.stdout + r.stderr
    parts = re.split(r'@@ledgdex-tutorial-block (\d+)@@\n', r.stdout)
    by_block = {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    problems, since = [], 0
    for upto, lines in checks:
        text = ''.join(by_block.get(b, '') for b in range(since + 1, upto + 1)) + r.stderr
        for line in lines:
            if line not in text:
                problems.append('blocks ' + str(since + 1) + '-' + str(upto) + ': expected "' + line + '"')
        since = upto
    if r.returncode != 0:
        problems.append('exit code ' + str(r.returncode) + ':\n' + out[-3000:])
    return r.returncode, problems


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='ledgdex-tutorial-') as tmp:
        code, problems = run(tmp)
    print('\n'.join(problems) if problems else 'passed: every expected line was in the output')
    sys.exit(1 if problems else 0)

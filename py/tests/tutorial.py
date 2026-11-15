"""Run the docs tutorial (guide/tutorial.md) as a reader runs it, and check its expected output.

The tutorial has two kinds of fenced blocks: ```sh blocks are commands, run in order in one bash process (later blocks
use the variables of earlier ones); an ```expect block names lines that the output of the commands since the last
```expect block must contain. A trap stops the tutorial's web server if a block fails.

    python py/tests/tutorial.py            run it in a new temporary folder and report"""
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TUTORIAL = os.path.join(HERE, '..', '..', 'guide', 'tutorial.md')
MARK = '@@ledgdex-tutorial-block {}@@'


def blocks(path=TUTORIAL):
    """[(kind, text)] for the ```sh and ```expect blocks, in order."""
    with open(path, encoding='utf-8') as f:
        return [(m.group(1), m.group(2)) for m in re.finditer(r'^```(sh|expect)\n(.*?)^```$', f.read(), re.M | re.S)]


def bash():
    """The bash to run shell examples with. On Windows, the one that comes with Git for Windows: "bash" on the PATH
    there can be the launcher of the Windows Subsystem for Linux, which does not see this Python or ledgdex."""
    if os.name == 'nt':
        git = shutil.which('git')
        if git:
            here, top = os.path.dirname(git), os.path.dirname(os.path.dirname(git))   # Git\cmd or Git\bin
            for path in (os.path.join(top, 'bin', 'bash.exe'), os.path.join(here, 'bash.exe'),
                         os.path.join(top, 'usr', 'bin', 'bash.exe')):
                if os.path.exists(path):
                    return path
        raise RuntimeError('the tests need Git for Windows (git and its bash): https://git-scm.com/download/win')
    return 'bash'


def shims(folder, python3=True):
    """A folder with "python3" and "ledgdex" commands that run this Python and this ledgdex, for the shell (python3
    is often missing on Windows, and the ledgdex on the PATH can be another one). Returns the folder.

    On Windows a script that runs a program stays between the shell and that program, so "kill" would stop the
    script and leave the program running. There the installed ledgdex.exe is used, and python3=False leaves out
    "python3", so that a command the tutorial stops (its web server) is the real program."""
    os.makedirs(folder, exist_ok=True)
    py = sys.executable.replace('\\', '/')
    want = [('python3', 'exec "' + py + '" "$@"')] if python3 else []
    if os.name != 'nt':
        want.append(('ledgdex', 'exec "' + py + '" -m ledgdex.cli "$@"'))
    for name, line in want:
        p = os.path.join(folder, name)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write('#!/bin/sh\n' + line + '\n')
        os.chmod(p, 0o755)
    return folder


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
    env['PATH'] = shims(os.path.join(workdir, '.bin'), python3=os.name != 'nt') + os.pathsep + env.get('PATH', '')
    env['PYTHONPATH'] = os.path.abspath(os.path.join(HERE, '..')) + os.pathsep + env.get('PYTHONPATH', '')
    r = subprocess.run([bash(), '-c', '\n'.join(script)], cwd=workdir, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
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

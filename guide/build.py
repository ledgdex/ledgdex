"""Refresh the generated pages of the ledgdex docs. Optional: run it only when the command line, the API, the message
types or an example in guide/examples/ changed.

The docs are a ledgdex in guide/dex/: a dex (data.json, config.json, styles.css) with a ledger (ledgdex.jsonl, see
make_demo_ledger.py). Pages are written by hand in data.json. A few are generated from the code and the examples
(pages.py); their bodies start with pages.MARKER. This script replaces those pages in data.json, matched by title, adds
any that are new, and leaves every other page as it is.

    python guide/build.py            update the generated pages in guide/dex/data.json
    python guide/build.py --check    exit 1 if they are out of date (CI)
    python guide/build.py --gen      also build the site into guide/dex/gen/ without publishing (to preview, and CI)

Then publish the docs to docs/ in ledgdex/ledgdex.github.io (https://ledgdex.github.io/docs/):

    cd guide/dex && ledgdex publish ."""
import contextlib, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'py'))
sys.path.insert(0, HERE)
import pages  # noqa: E402

DEX = os.path.join(HERE, 'dex')
DATA = os.path.join(DEX, 'data.json')


def updated(data):
    """data with every generated page replaced, or added at the end when new."""
    data = list(data)
    at = {p['title']: n for n, p in enumerate(data)}
    for p in pages.generated():
        if p['title'] in at:
            data[at[p['title']]] = p
        else:
            data.append(p)
    return data


def gen():
    """What ledgdex publish does before it publishes: the ledger's pages into data.json, then dexweb into gen/."""
    from dexweb import dexgen
    from ledgdex.dex import inside
    from ledgdex.render import render
    with contextlib.redirect_stdout(io.StringIO()):
        render(DEX)
        with inside(DEX):
            dexgen.Dexgen()
    print('docs built in guide/dex/gen/')


def main(argv):
    with open(DATA, encoding='utf-8') as f:
        data = json.load(f)
    new = updated(data)
    if new == data:
        print('generated docs pages are up to date')
        if '--gen' in argv:
            gen()
        return
    if '--check' in argv:
        raise SystemExit('generated docs pages are out of date: run "python guide/build.py", then '
                         '"cd guide/dex && ledgdex publish ."')
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(new, indent=4, ensure_ascii=False))     # as ledgdex writes it
    os.replace(tmp, DATA)
    print('generated docs pages updated in guide/dex/data.json; publish with: cd guide/dex && ledgdex publish .')
    if '--gen' in argv:
        gen()


if __name__ == '__main__':
    main(sys.argv[1:])

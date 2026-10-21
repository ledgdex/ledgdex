"""Make docs pages from the code and the examples, when you ask for them. Optional: the docs do not need it.

The docs are a ledgdex in guide/dex/: a dex (data.json, config.json, styles.css) with a ledger (ledgdex.jsonl, see
make_demo_ledger.py). data.json is the source of the docs: change any page there by hand, then publish. pages.py can
make five pages from the code and the examples. This script writes a page into data.json only when you name it. It
replaces the page with that title, or adds it at the end. It leaves every other page as it is.

    python guide/build.py                          list the pages that it can make
    python guide/build.py --page "Message Types"   write that page into guide/dex/data.json (use --page again for more)
    python guide/build.py --gen                    build the site into guide/dex/gen/ without publishing (to preview)

Then publish the docs to docs/ in ledgdex/ledgdex.github.io (https://ledgdex.github.io/docs/):

    cd guide/dex && ledgdex publish ."""
import argparse, contextlib, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'py'))
sys.path.insert(0, HERE)
import pages  # noqa: E402

DEX = os.path.join(HERE, 'dex')
DATA = os.path.join(DEX, 'data.json')


def written(data, titles):
    """data with the named pages replaced, or added at the end when new."""
    made = {p['title']: p for p in pages.generated()}
    unknown = [t for t in titles if t not in made]
    if unknown:
        raise SystemExit('build.py cannot make ' + ', '.join(map(repr, unknown)) + '. It can make: ' +
                         ', '.join(map(repr, made)))
    data = list(data)
    at = {p['title']: n for n, p in enumerate(data)}
    for t in titles:
        if t in at:
            data[at[t]] = made[t]
        else:
            data.append(made[t])
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
    ap = argparse.ArgumentParser(prog='build.py', description='Make docs pages from the code, when you ask.')
    ap.add_argument('--page', action='append', default=[], metavar='TITLE', help='write this page into data.json')
    ap.add_argument('--gen', action='store_true', help='build the site into guide/dex/gen/')
    a = ap.parse_args(argv)
    if not a.page and not a.gen:
        print('pages that build.py can make: ' + ', '.join(p['title'] for p in pages.generated()))
        return
    if a.page:
        with open(DATA, encoding='utf-8') as f:
            data = json.load(f)
        new = written(data, a.page)
        tmp = DATA + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(json.dumps(new, indent=4, ensure_ascii=False))     # as ledgdex writes it
        os.replace(tmp, DATA)
        print('written into guide/dex/data.json: ' + ', '.join(a.page))
    if a.gen:
        gen()


if __name__ == '__main__':
    main(sys.argv[1:])

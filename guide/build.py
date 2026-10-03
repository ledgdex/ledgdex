"""Build the ledgdex docs, a dex built with dexweb, in the style of the dexweb docs.

The docs are also a ledgdex: guide/dex/ holds a ledger (ledgdex.jsonl, see make_demo_ledger.py), so ledgdex renders
its pages next to the written ones, exactly as in every ledgdex. The written pages come from guide/pages.py; the
examples they show are guide/examples/, run by py/tests/test_guide.py; the command line and API references are
generated from the code. Published with dexweb to docs/docs/ (GitHub Pages: matrixdex.github.io/ledgdex/docs/).
Run from anywhere:  python guide/build.py"""
import contextlib, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'py'))
sys.path.insert(0, HERE)
from dexweb import dexweb  # noqa: E402
from ledgdex.dex import LEDGER, inside  # noqa: E402
from ledgdex.render import create_dex, render  # noqa: E402
import pages  # noqa: E402

DEX = os.path.join(HERE, 'dex')
NAME = 'Ledgdex Docs'
# no scripts at all, and nothing from elsewhere: the docs share an origin with the viewer, which keeps sealed keys
CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'none\'; style-src '
       '\'self\'; img-src \'self\' data:; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
       '<meta name="referrer" content="no-referrer">')
HEAD = ("<html lang='en'>\n<head>\n<meta charset='UTF-8'>\n<meta name='viewport' content='width=device-width, "
        "initial-scale=1.0'>\n<link rel='shortcut icon' type='image/x-icon' href='assets/favicon.ico'>\n"
        "<link rel='stylesheet' href='styles.css'>\n")
CONFIG = {   # dexweb's templates, as the dexweb docs use them: "LEDGDEX DOCS" and "BACK TO LEDGDEX DOCS"
    'dexname': NAME,
    'author': 'Noorul Ali',
    'index_template': HEAD + "<title>{} Dex</title>\n</head>\n<body>\n<br><h1>{}</h1><br>\n{}\n<br><br><br><br><br><br><br>"
                             "\n<h3><a href='index.html'>{}</a></h3>\n</body>\n</html>",
    'page_template': HEAD + "<title>{} - {} Dex</title>\n</head>\n<body>\n<br>\n<h1>{}</h1>\n<br>\n{}\n<br><br><br><br><br>"
                            "<br><br>\n<h3><a href='index.html'>BACK TO {}</a></h3>\n</body>\n</html>",
    'page_javascript': CSP,
    'index_javascript': CSP,
    'index_list_type_para': False,
    'index_list_no_page_link_only': True,
    'publish': {'method': 'folder', 'path': '../../docs/docs', 'append_only': [LEDGER]},
}
STYLES = '''
pre {
  background-color: rgb(20, 20, 20); border-left: 3px solid #00ff41; padding: 12px 16px; overflow-x: auto;
  font-family: monospace; font-size: 15px; letter-spacing: 0; line-height: 1.45; white-space: pre;
}
code {
  font-family: monospace; letter-spacing: 0; overflow-wrap: anywhere;
}
:not(pre) > code {
  font-size: 18px; color: rgb(203, 203, 203);
}
pre {
  max-width: 100%; box-sizing: border-box;
}
pre code {
  color: rgb(230, 230, 230);
}
'''


def build(publish=True):
    with open(os.path.join(DEX, LEDGER), 'rb') as f:
        ledger = f.read()
    if not os.path.exists(os.path.join(DEX, 'config.json')):
        with contextlib.redirect_stdout(io.StringIO()):
            create_dex(DEX, ledger, NAME)
    with open(os.path.join(DEX, 'config.json'), 'w') as f:
        f.write(json.dumps(CONFIG, indent=4) + '\n')
    import importlib_resources
    base = importlib_resources.files('dexweb').joinpath('styles.css').read_text()
    with open(os.path.join(DEX, 'styles.css'), 'w') as f:
        f.write(base.rstrip() + '\n' + STYLES)
    with open(os.path.join(DEX, 'data.json'), 'w') as f:      # the written pages; render() adds the ledger's
        f.write(json.dumps(pages.pages(), indent=4, ensure_ascii=False) + '\n')
    with contextlib.redirect_stdout(io.StringIO()):
        render(DEX)
        if publish:
            with inside(DEX):
                if not dexweb.Dexweb().publish():
                    raise SystemExit('dexweb did not publish the docs')
    print('docs built: ' + str(len(pages.pages())) + ' written pages' + (', published to docs/docs/' if publish else ''))


if __name__ == '__main__':
    build()

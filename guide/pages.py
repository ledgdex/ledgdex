"""The written pages of the ledgdex docs (see build.py). Each page is a dex page: a title and a list of paragraphs,
HTML as dexweb writes it. Examples are included from guide/examples/ as they are (tested by py/tests/test_guide.py);
the command line options and the API reference are generated from the code, so they cannot drift from it."""
import argparse, html, inspect, json, os, re

from ledgdex import __version__
from ledgdex.render import html_title

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, 'examples')
JS = os.path.join(HERE, '..', 'js')
REPO = 'https://github.com/matrixdex/ledgdex'
VIEWER = 'https://matrixdex.github.io/ledgdex/viewer.html'
DOCS = 'https://matrixdex.github.io/ledgdex/docs'
TAG = 'v' + __version__        # the release the docs install


# ---------- helpers ----------

def code(text):
    return '<pre><code>' + html.escape(text.strip('\n'), quote=False) + '</code></pre>'


def c(text):
    """Inline code."""
    return '<code>' + html.escape(text, quote=False) + '</code>'


def link(title, text=None):
    return "<a href='" + html_title(title) + ".html'>" + (text or title) + '</a>'


def ext(url, text):
    return "<a href='" + url + "'>" + text + '</a>'


def example_text(name):
    with open(os.path.join(EXAMPLES, name), encoding='utf-8') as f:
        return f.read()


def example(name):
    """An example file as a page: each comment line above a block of code becomes the paragraph before it, so the
    code itself is shown without comments. The expect: lines are for the tests and are left out."""
    mark = '//' if name.endswith('.mjs') else '#'
    out, block = [], []

    def flush():
        if ''.join(block).strip():
            out.append(code('\n'.join(block)))
        block.clear()
    for line in example_text(name).split('\n'):
        if re.match(re.escape(mark) + r' expect:', line):
            continue
        if line.startswith(mark + ' '):
            flush()
            out.append(re.sub(r'`([^`]+)`', lambda m: c(m.group(1)), html.escape(line[len(mark) + 1:], quote=False)))
        else:
            block.append(line)
    flush()
    return out + ['The whole file: ' + ext(REPO + '/blob/main/guide/examples/' + name, c('guide/examples/' + name)) +
                  ', run as it is on every push (' + c('py/tests/test_guide.py') + ').']


def steps(*items):
    return [str(n) + '. ' + s for n, s in enumerate(items, 1)]


# ---------- generated references ----------

def cli_pages():
    """One entry per command, from the argument parser itself."""
    from ledgdex.cli import parser
    os.environ['COLUMNS'] = '110'
    p = parser()
    sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    out = []
    for name, sp in sub.choices.items():
        sp.prog = 'ledgdex ' + name
        out += ["<span id='" + name + "'>ledgdex " + name + '</span>', code(sp.format_help())]
    return sub.choices, out


API = [
    ('ledgdex.core', 'Messages, entries and ledgers: signing, verifying, reading a ledger (spec 2, 3).',
     ['Ledger', 'Ledger.append', 'Ledger.next_entry', 'Ledger.find', 'Ledger.head', 'Ledger.owner', 'Ledger.devices',
      'Ledger.dex', 'Ledger.whole', 'new_ledger', 'message', 'new_secret', 'public', 'sign', 'verify', 'unsigned',
      'check_message', 'check_body', 'check_receipt', 'root_recovers', 'is_key', 'is_id', 'is_time', 'now', 'seconds',
      'utc', 'Keys', 'Invalid', 'SKEW', 'OWNER_ONLY', 'COUNTERPARTY', 'KEY_TYPES']),
    ('ledgdex.canon', 'Canonical JSON: the exact bytes that are hashed and signed (spec 1.2).',
     ['canon', 'parse', 'hash_', 'sha256', 'check', 'CanonError', 'MAX_DEPTH', 'MAX_INT']),
    ('ledgdex.state', 'The state function: a ledger replayed into one JSON object (spec 6).',
     ['state', 'judged_at', 'admissions', 'admitted_at']),
    ('ledgdex.dex', 'A ledgdex on disk: keys, this dex\'s ledger, and reading other ledgers.',
     ['load', 'record', 'fetch', 'http_get', 'load_root', 'keygen', 'load_key', 'find_key', 'signer', 'key_dir',
      'locked', 'write', 'inside', 'LEDGER', 'MAX_BYTES', 'ROOT_COPY']),
    ('ledgdex.render', 'Every ledgdex is a dex: the pages ledgdex generates, and the dexweb build (spec 7).',
     ['render', 'create_dex', 'pages', 'dex_name', 'safe_url', 'esc', 'amount', 'MARKER']),
    ('ledgdex.check', 'Tamper checks over time (spec 9.1).', ['check', 'Checker', 'workflow']),
    ('ledgdex.publish', 'Publishing with dexweb, from one or more devices (spec 7.4).', ['publish', 'catch_up']),
    ('ledgdex.cli', 'The command line, also callable from Python.', ['main', 'parser', 'next_at']),
    ('ledgdex.sig', 'Ed25519 backends: the cryptography package when present, else the built-in code.',
     ['backend', 'pure', 'sign']),
]


OBJECTS = {
    'ledgdex.sig.backend': 'The Ed25519 backend in use: the cryptography package (name "cryptography") when it is '
                           'installed and passes a known-answer test, else the built-in code (name "pure"). '
                           'LEDGDEX_PURE=1 forces the built-in code. Both verify identically.',
    'ledgdex.sig.pure': 'The built-in Ed25519 (name "pure"), always available. Not constant time when signing.',
}


def _doc(obj):
    d = inspect.getdoc(obj) or ''
    return [html.escape(x.replace('\n', ' '), quote=False) for x in d.split('\n\n') if x.strip()]


def python_api():
    import importlib
    out = []
    for mod_name, about, names in API:
        mod = importlib.import_module(mod_name)
        out += ["<span id='" + mod_name + "'>" + mod_name + '</span>: ' + about]
        for name in names:
            owner, attr = (mod, name) if '.' not in name else (getattr(mod, name.split('.')[0]), name.split('.')[1])
            obj = getattr(owner, attr)
            full = mod_name + '.' + name
            if isinstance(obj, property):
                out += [code(full + '   (property)')] + _doc(obj.fget)
            elif inspect.isclass(obj):
                try:
                    sig = str(inspect.signature(obj))
                except (TypeError, ValueError):
                    sig = ''
                out += [code('class ' + full + sig)] + _doc(obj)
            elif callable(obj):
                out += [code(full + str(inspect.signature(obj)))] + _doc(obj)
            elif ' object at ' in repr(obj):     # an instance: describe it, never its address or type here
                out += [code(full + '   (object: .name, .public_key(secret), .sign(secret, msg), .verify(public, '
                                    'msg, signature))'), OBJECTS.get(full, '')]
            else:
                val = repr(obj) if not isinstance(obj, (set, frozenset)) else '{' + ', '.join(sorted(map(repr, obj))) + '}'
                out += [code(full + ' = ' + (val if len(val) < 100 else type(obj).__name__))]
    return out


def js_api():
    out = []
    for f in ('core.js', 'canon.js', 'state.js', 'render.js', 'sig.js', 'keystore.js', 'dexweb.js', 'zip.js'):
        with open(os.path.join(JS, f), encoding='utf-8') as fh:
            src = fh.read()
        head = re.match(r'((?://[^\n]*\n)+)', src)
        about = ' '.join(x.lstrip('/ ').strip() for x in head.group(1).splitlines()) if head else ''
        sigs = []
        for m in re.finditer(r'^export (?:async )?(function|class|const) (\w+)\s*(\([^)]*\)|=\s*(?:async\s*)?\(([^)]*)\)|=)?',
                             src, re.M):
            kind, name = m.group(1), m.group(2)
            if kind == 'function':
                sigs.append(name + m.group(3))
            elif kind == 'class':
                sigs.append('class ' + name)
            elif m.group(4) is not None:
                sigs.append(name + '(' + m.group(4) + ')')
            else:
                sigs.append(name)
        out += ["" + f + ': ' + html.escape(about, quote=False), code('\n'.join(sigs))]
    return out


# message types: who signs, who records, and a valid body (each is checked by check_body in test_guide)
K = 'ed25519:' + 'a1' * 32
I = 'sha256:' + 'b2' * 32
MESSAGE_TYPES = [
    ('open', 'owner (owner key only)', 'the owner, as entry 0', {'about': 'Alphonso mangoes from Ratnagiri',
                                                                  'dex': 'https://farm.example'}),
    ('offer', 'owner or a device', 'the seller', {
        'item': {'title': 'Alphonso mangoes', 'text': 'One dozen, ripe.',
                 'media': [{'url': 'https://farm.example/mango.jpg', 'hash': I}]},
        'quantity': 10, 'unit': 'dozen', 'currency': 'INR', 'price': 120000, 'allow': 'any',
        'pay': [{'method': 'upi', 'to': 'farm@bank'}], 'arbiter': {'key': K, 'url': 'https://assoc.example'},
        'terms': 'Delivered in Ratnagiri within 2 days.', 'expires': '2026-12-31T23:59:59Z'}),
    ('withdraw', 'owner or a device', 'the seller', {'offer': I}),
    ('claim', 'the buyer (its owner key)', 'the seller', {'offer': I, 'offer_hash': I, 'quantity': 2, 'price': 120000}),
    ('paid', 'the buyer', 'the seller', {'claim': I, 'method': 'upi', 'ref': 'UTR123'}),
    ('received', 'owner or a device', 'the seller', {'claim': I, 'amount': 240000}),
    ('delivered', 'owner or a device', 'the seller', {'claim': I, 'note': 'by courier, tracking 42'}),
    ('confirmed', 'the buyer', 'the seller', {'claim': I}),
    ('dispute', 'the buyer or the seller', 'the seller', {'claim': I, 'text': 'Nothing arrived.', 'evidence': ['UTR123', I]}),
    ('ruling', "the offer's arbiter", 'the seller', {'dispute': I, 'outcome': 'refund', 'text': 'No proof of delivery.'}),
    ('auction', 'owner or a device', 'the seller', {
        'item': {'title': 'Map of Bombay, 1893', 'text': '', 'media': []}, 'currency': 'INR',
        'close': '2026-11-01T12:00:00Z', 'reveal_until': '2026-11-02T12:00:00Z', 'best': 'highest', 'reserve': 500000,
        'allow': 'any', 'arbiter': {'key': K, 'url': ''}, 'terms': ''}),
    ('bid', 'the bidder', 'the seller', {'auction': I, 'commit': I}),
    ('reveal', 'the bidder', 'the seller', {'auction': I, 'amount': 650000, 'nonce': 'c3' * 32}),
    ('admit', 'owner or a device', 'the admitting ledger (a shop, or the root)', {'key': K, 'name': 'Asha', 'note': ''}),
    ('revoke', 'owner or a device', 'the admitting ledger', {'key': K, 'reason': 'left the market'}),
    ('list', 'owner or a device', 'an index', {'ledger': I, 'url': 'https://farm.example', 'owner': K, 'note': 'mangoes'}),
    ('delist', 'owner or a device', 'an index', {'ledger': I, 'reason': 'closed'}),
    ('note', 'owner or a device', 'any ledger, about its own entries', {'ref': I, 'text': 'restocked'}),
    ('device', 'owner (owner key only)', 'the ledger', {'key': K, 'name': 'shop phone'}),
    ('device_revoke', 'owner (owner key only)', 'the ledger', {'key': K, 'reason': 'lost'}),
    ('rotate', 'owner (owner key only)', 'the ledger', {'key': K}),
    ('recover', "the root's owner key", 'the root', {'ledger': I, 'key': K}),
    ('recovered', 'the new key the root named', 'the recovered ledger', {'root': I, 'entry': I}),
]


def message_types():
    out = ['Every message is ' + c('{"v": 1, "type": ..., "by": key, "at": time, "body": {...}, "sig": ...}') +
           ', signed by ' + c('by') + '. The body of each type, with every field (optional ones: ' + c('expires') +
           ' in an offer; ' + c('keys') + ' in a receipt), as the code accepts it:']
    for t, author, recorder, body in MESSAGE_TYPES:
        out += ['' + t + ': signed by ' + author + '; recorded by ' + recorder + '.',
                code(json.dumps(body, indent=1, ensure_ascii=False))]
    out += ['sent and receipt (owner or a device, in its own ledger) hold whole messages and entries: ' +
            c('{"to": key, "msg": message}') + ' keeps a copy of a message sent to another ledger; ' +
            c('{"ledger": id, "url": str, "header": header, "entry": entry, "keys": [entry, ...]}') + ' keeps another '
            "ledger's entry about one of this self's messages, which verifies on its own (" +
            link('Ledger File Format') + ').']
    return out


def ledger_sample():
    with open(os.path.join(HERE, 'dex', 'ledgdex.jsonl'), encoding='utf-8') as f:
        lines = f.read().split('\n')[:3]
    return [code(lines[0]), code(json.dumps(json.loads(lines[1]), indent=1, ensure_ascii=False)),
            code(lines[2][:160] + ' ...')]


# ---------- the pages ----------

def pages():
    commands, cli = cli_pages()
    P = []

    def page(title, *body):
        flat = []
        for b in body:
            flat += b if isinstance(b, list) else [b]
        P.append({'title': title, 'body': flat})

    page('Getting Started',
         'Ledgdex is a simple market on a ' + ext('https://matrixdex.github.io/dexweb', 'dex') + '. A dex is a website '
         'made by ' + ext('https://github.com/matrixdex/dexweb', 'dexweb') + ' from your own files; a ledgdex is a dex '
         'with a signed, append-only ledger in it (' + c('ledgdex.jsonl') + '). Every seller and buyer keeps one. A '
         'trade then exists three times: the buyer\'s signed claim, the seller\'s signed record of it, and the buyer\'s '
         'copy of that record. No server, no blockchain: SHA-256, Ed25519 and plain files. ' +
         link('Dex and Ledgdex', 'Dex is the core; dex + ledger is a ledgdex.'),
         'These docs are a ledgdex too: ' + link('Ledgdex Docs ledger', 'its own ledger') + ' (signed once, as a '
         'demonstration) is rendered into the pages listed here, next to the written ones.',
         steps('Install ledgdex (Python 3.8 or later, with git; more ways in ' + link('Installation') + '): ' +
               code('pip install "ledgdex @ git+' + REPO + '@' + TAG + '#subdirectory=py"'),
               'Make your ledgdex, a dex with a new ledger and a key kept in ' + c('~/.ledgdex') + ': ' +
               code('ledgdex init shop --name "Mango Farm" --key farm'),
               'Offer something. Prices are integers in the smallest unit of the currency (120000 is INR 1,200.00): ' +
               code('cat > offer.json <<EOF\n{"item": {"title": "Alphonso mangoes"}, "quantity": 10, "unit": "dozen",\n'
                    ' "currency": "INR", "price": 120000, "pay": [{"method": "upi", "to": "farm@bank"}]}\nEOF\n'
                    'ledgdex offer shop offer.json'),
               'Open ' + c('shop/gen/index.html') + ': your dex, with a page for your ledger and one for the offer. '
               'Your own pages go in ' + c('shop/data.json') + ' or ' + c('shop/to_add/') + ' as in any dex.',
               'Put it online (' + link('Publishing a Ledgdex Online') + '), and buyers claim from it (' +
               link('Buying') + '). ' + link('Example: First Trade') + ' runs a whole trade on one machine.'),
         'Where to go next: simple users setting up a market start at ' + link('Set Up a Marketplace') + '; developers '
         'at ' + link('Extending Ledgdex') + ' and the ' + link('API Reference') + '; bots and agents at ' +
         link('Bots and Agents') + '. Every command is in ' + link('Command Line Options') + ', every example in ' +
         link('Examples') + '.')

    page('Dex and Ledgdex',
         'The dex is the core. A dex is a website dexweb builds from a folder: ' + c('data.json') + ' (its pages), '
         + c('config.json') + ' (its look and where it is published), ' + c('to_add/') + ' (files to turn into pages) '
         'and ' + c('gen/') + ' (the site). A dex works on its own, is freely shared, is readable by people and bots, '
         'and is hosted anywhere static files are (' + ext('https://matrixdex.github.io/dexweb/dexhosting.html',
                                                               'dex hosting') + ').',
         'Dex + ledger = ledgdex. A ledgdex is a dex with one more file, ' + c('ledgdex.jsonl') + ': a ledger '
         'signed by its owner, entry by entry, each entry chained to the one before by its hash. ledgdex reads the '
         'ledger, replays it into a state (offers, claims, payments, disputes, auctions, admissions, listings) and '
         'writes pages for it into the same ' + c('data.json') + ', next to your own pages; dexweb builds the site as '
         'always. Nothing else changes: same folder, same build, same hosting.',
         code('dex          = data.json + config.json + to_add/        ->  gen/ (website)\n'
              'ledgdex      = dex + ledgdex.jsonl (signed ledger)      ->  gen/ (website + ledger pages + ledger)\n'
              'a market     = many ledgdexes that read each other\'s ledgers'),
         'So everything you know about dexes holds: ' + ext('https://matrixdex.github.io/dexweb/gettingstarted.html',
                                                           'dexweb\'s getting started') + ', its styles and themes, '
         'publishing with ' + c('python run.py') + '. ledgdex adds the commands that sign and record (' +
         link('Command Line Options') + '), and refuses to publish a ledger that does not extend the one already '
         'published (' + c('"append_only": ["ledgdex.jsonl"]') + ' in ' + c('config.json') + ').',
         'Which to use: a dex when you publish (documents, a shop window, a journal); a ledgdex when what you publish '
         'must be trusted later: offers people buy from, records of who bought what, admissions to a market. A dex can '
         'become a ledgdex at any time: ' + c('ledgdex init') + ' on an existing dex folder keeps its pages and '
         + c('config.json') + ' and adds a ledger.',
         'This documentation is both: a dex (the written pages) and a ledgdex (' + link('Ledgdex Docs ledger') + ', ' +
         link('Example offer: Alphonso mangoes') + ' and ' + link('Example auction: Map of Bombay, 1893') +
         ' are generated from ' + ext(DOCS + '/ledgdex.jsonl', 'its ledger') + '). Load that ledger in the ' +
         ext(VIEWER + '?ledger=' + DOCS, 'viewer') + ', or check it: ' + code('ledgdex verify ' + DOCS))

    page('Installation',
         'Ledgdex needs Python 3.8 or later and dexweb (installed with it). Publishing needs git.',
         steps('From the release (recommended): ' + code('pip install "ledgdex @ git+' + REPO + '@' + TAG + '#subdirectory=py"'),
               'With fast, constant-time signing (recommended on every machine that signs; ledgdex warns without it): ' +
               code('pip install "ledgdex[fast] @ git+' + REPO + '@' + TAG + '#subdirectory=py"'),
               'From a clone, to develop: ' + code('git clone ' + REPO + '\ncd ledgdex\npip install -e "py[fast]"\n'
                                                    'cd py && python -m unittest discover -s tests'),
               'Check: ' + code('ledgdex --help\nledgdex verify ' + DOCS)),
         'The JavaScript core needs no install: it is plain ES modules in ' + c('js/') + ', also served next to the ' +
         ext(VIEWER, 'viewer') + ' (' + link('API Reference') + ').',
         'Where things live: keys in ' + c('~/.ledgdex') + ' (or ' + c('$LEDGDEX_HOME') + '), the verification cache in '
         + c('~/.cache/ledgdex') + ' (or ' + c('$LEDGDEX_CACHE') + '); see ' + link('Configuration') + '.')

    page('Ledgdex Directory Structure',
         'What ' + c('ledgdex init shop ...') + ' makes. Everything in the folder is public except nothing: keys are '
         'never in a dex.',
         code('shop/\n'
              '  ledgdex.jsonl        the ledger: a header line and one signed entry per line (append-only)\n'
              '  data.json            the dex pages: yours, and the ones ledgdex writes (they start with <!-- ledgdex -->)\n'
              '  config.json          dexweb settings, "publish" (with "append_only": ["ledgdex.jsonl"]) and "ledgdex"\n'
              '  styles.css           the look (dexweb\'s default)\n'
              '  run.py               "python run.py" builds the dex with dexweb, as in any dex\n'
              '  to_add/              files to add as pages (dexweb)\n'
              '  backup/              dexweb\'s backup of data.json\n'
              '  gen/                 the website: what is published, including gen/ledgdex.jsonl\n'
              '  .ledgdex-root.jsonl  the last copy of the root read (only with a root; never published)\n'
              '  .ledgdex.lock        one writer at a time\n'
              '  .publish/            dexweb\'s copy of the repository it publishes to\n'
              '\n'
              '~/.ledgdex/            secret keys, mode 600 (NAME.key), and secret bids until their reveal (bids/)\n'
              '~/.cache/ledgdex/      which ledger bytes were already verified (a speed-up only)'),
         'Only ' + c('gen/') + ' is published. ' + c('ledgdex render shop') + ' rewrites the generated pages and '
         'rebuilds ' + c('gen/') + '; every command that records does it for you.')

    page('Set Up a Marketplace',
         'A market for a place, a trade or a community, with no platform in the middle: every member keeps their own '
         'ledgdex, and one operator keeps a ledger that is both the index (which shops are listed) and the '
         'root (who is admitted). Shops sell to admitted members; buyers find offers through the index; the '
         'operator is the default arbiter of disputes. ' + link('Example: Marketplace') + ' does all of this on one '
         'machine.',
         steps('The operator makes the market\'s ledgdex and publishes it (' + link('Publishing a Ledgdex Online') +
               '): ' + code('ledgdex init market --name "Ratnagiri Market" --about "Fruit sellers of Ratnagiri" '
                            '--key market \\\n    --url https://market.example --dest git@github.com:YOU/market.git '
                            '--branch main\nledgdex publish market'),
               'Each shop makes its own ledgdex under the market: ' + code('ledgdex init farm --name "Mango Farm" --key farm '
                                                                          '--root https://market.example'),
               'Shops and buyers send the operator their public key (printed by ' + c('ledgdex keygen NAME') + ' or ' +
               c('ledgdex init') + '). The operator checks who they are, off the ledger, and admits them: ' +
               code('ledgdex admit market ed25519:SHOP_KEY --name "Mango Farm"\nledgdex admit market ed25519:BUYER_KEY '
                    '--name "Asha"\nledgdex publish market'),
               'The operator lists the shops: ' + code('ledgdex list market https://farm.example --note "mangoes"'),
               'Shops offer to admitted members only (' + c('"allow": "admitted"') + '; a shop admits the buyers it '
               'serves too, with ' + c('ledgdex admit farm KEY') + '), or to anyone (' + c('"any"') + ').',
               'Buyers read the index to find offers: ' + code('ledgdex discover https://market.example --offers'),
               'Everyone runs ' + c('ledgdex check') + ' on the ledgers they trade with, daily (' +
               link('Checking for Tampering') + '): any rewrite is caught, with signed proof.'),
         'What the operator can and cannot do: it decides membership and rules disputes (signed, in public); it cannot '
         'change anyone\'s ledger, hide a sale, or set a price. Its key is the most valuable one in the market: keep '
         'it offline and use a device key day to day (' + link('Keys, Devices and Recovery') + ').',
         'Variations: without ' + c('--root') + ', a market is just an index anyone can be listed in. Several markets '
         'can list the same shop. A shop under no root arbitrates its own offers unless it names an arbiter (' +
         link('Disputes and Arbiters') + ').')

    page('Selling',
         'A seller signs offers into its own ledger, records the claims that come in, and records payment and delivery.',
         steps('Write the offer as JSON. Required: ' + c('item.title') + ', ' + c('quantity') + ', ' + c('currency') +
               ', ' + c('price') + '. The rest has defaults: ' + c('unit') + ' "unit", ' + c('allow') + ' "any", ' +
               c('pay') + ' [], ' + c('terms') + ' "", ' + c('item.text') + ' "", ' + c('item.media') + ' [], and the '
               'arbiter is the root\'s owner, or the seller when the dex names no root. ' +
               code('{"item": {"title": "Alphonso mangoes", "text": "One dozen, ripe.",\n'
                    '          "media": [{"url": "https://farm.example/mango.jpg", "hash": "sha256:..."}]},\n'
                    ' "quantity": 10, "unit": "dozen", "currency": "INR", "price": 120000,\n'
                    ' "allow": "any", "pay": [{"method": "upi", "to": "farm@bank"}],\n'
                    ' "terms": "Delivered in Ratnagiri within 2 days.", "expires": "2026-12-31T23:59:59Z"}'),
               'Sign and record it: ' + code('ledgdex offer shop offer.json'),
               'Collect claims: from each buyer\'s published dex, or from files buyers send you. ' +
               code('ledgdex record shop --from https://asha.example --from https://ravi.example\nledgdex record shop '
                    'claim-1a2b3c4d5e6f.json'),
               'When the money arrives, and when you deliver: ' + code('ledgdex received shop CLAIM_ID 240000\n'
                                                                      'ledgdex delivered shop CLAIM_ID --note "by courier"'),
               'Stop selling: ' + code('ledgdex withdraw shop OFFER_ID'),
               'Publish after each step others need to see: ' + code('ledgdex publish shop')),
         'Rules the state enforces (anyone recomputes them): a claim must name the offer by id and by hash (the '
         'offer cannot change under it), pay the offer\'s price, ask for 1 to the remaining quantity, come from '
         'someone ' + c('allow') + ' admits, arrive before ' + c('expires') + ', and not come from the seller itself; '
         'otherwise it is kept and marked rejected with the reason. Two claims for the last unit: the first recorded '
         'wins.',
         'Media are linked, never embedded: a URL and the SHA-256 of the file, so a picture cannot change '
         'after a sale without ' + c('ledgdex check --media') + ' noticing.',
         'Prices are integers in the smallest unit: INR and USD in paise and cents (2 digits), JPY in yen, BTC in '
         'satoshi. Any currency code works; pages format the ones they know. See ' + link('A Trade, Step by Step') +
         ' and ' + link('Example: First Trade') + '.')

    page('Buying',
         'A buyer signs claims, payments and confirmations with its own key and keeps a copy of each as ' + c('sent') +
         ' in its own ledger: publishing your dex is sending them. You need your own ledgdex to buy (' +
         c('ledgdex init me --name "Asha" --key asha') + '), or only a browser (' + link('The Viewer') + ').',
         steps('Find the offer: on the seller\'s dex, or through an index (' + link('Indexes and Discovery') + ').',
               'Claim it. ledgdex reads the seller\'s ledger, checks the offer is open, and signs the offer\'s exact '
               'hash and price: ' + code('ledgdex claim me https://farm.example OFFER_ID --quantity 2'),
               'Send it: publish your dex (' + c('ledgdex publish me') + '), and the seller collects it with ' +
               c('ledgdex record shop --from https://asha.example') + '; or send the file ' + c('claim-....json') +
               ' any way you like.',
               'Keep the receipts: the seller\'s signed records of your messages. ' +
               code('ledgdex receipt me https://farm.example'),
               'Pay as the offer says (outside the ledger), then tell the seller, and confirm once the goods arrive: ' +
               code('ledgdex pay me https://farm.example CLAIM_ID --method upi --ref UTR123\n'
                    'ledgdex confirm me https://farm.example CLAIM_ID'),
               'If something goes wrong: ' + link('Disputes and Arbiters') + '.'),
         'Your receipts are your proof: an entry signed by the seller saying it recorded your claim at that position '
         'of its ledger. If the seller ever rewrites its ledger, ' + c('ledgdex check') + ' on your ledger shows it (' +
         link('Checking for Tampering') + ').')

    page('A Trade, Step by Step',
         'Who signs what, in which ledger, and the claim\'s status after each step. ' + link('Example: First Trade') +
         ' runs it.',
         code('step                         signed by   kept in                     claim status\n'
              'offer                        seller      seller ledger               (offer open)\n'
              'claim                        buyer       buyer (sent), seller        accepted, or rejected with a reason\n'
              'receipt of the claim         buyer       buyer ledger                (the third entry)\n'
              'paid                         buyer       buyer (sent), seller        accepted, paid\n'
              'received                     seller      seller ledger               accepted, received\n'
              'delivered                    seller      seller ledger               accepted, delivered\n'
              'confirmed                    buyer       buyer (sent), seller        closed (once received + delivered + confirmed)\n'
              'dispute                      either      seller ledger               disputed\n'
              'ruling                       arbiter     seller ledger               released, refunded or split'),
         'Rejection reasons, in the order they are tested: ' + c('unknown_offer') + ', ' + c('offer_changed') + ', ' +
         c('withdrawn') + ', ' + c('expired') + ', ' + c('self_claim') + ', ' + c('not_allowed') + ', ' +
         c('bad_quantity') + ', ' + c('price_mismatch') + '. Messages that break no structure but no rule accepts '
         '(a payment from someone else, a ruling by the wrong key, a message recorded twice) are kept and listed in '
         'the state\'s ' + c('ignored') + ' with a reason; they never break the ledger.',
         'Read the state of any ledger: ' + code('ledgdex state https://farm.example\nledgdex state shop | python3 -m '
                                                'json.tool'))

    page('Disputes and Arbiters',
         'Every offer and auction names an arbiter: a key that may rule on disputes about it, signed into the offer '
         'so buyers see it before they buy. Default: the root\'s owner when the dex names a root, else the seller. '
         'Name another in the offer: ' + c('"arbiter": {"key": "ed25519:...", "url": "https://assoc.example"}') + '.',
         steps('The buyer (or the seller) opens a dispute about an accepted claim, with evidence: ' +
               code('ledgdex dispute me CLAIM_ID --seller https://farm.example --text "Nothing arrived." --evidence UTR555'),
               'The seller records it (' + c('ledgdex record shop --from https://asha.example') + '). The claim is '
               + c('disputed') + '.',
               'The arbiter rules, from its own ledgdex: ' + code('ledgdex ruling assoc https://farm.example DISPUTE_ID '
                                                                 '--outcome refund --text "No proof of delivery."'),
               'The seller records the ruling: the claim becomes ' + c('released') + ', ' + c('refunded') + ' or ' +
               c('split') + '. A ruling by any other key is kept and ignored (' + c('not_arbiter') + '), and a dispute '
               'is ruled once.'),
         'Money moves outside the ledger: a ruling is a signed decision the parties and their market act on. ' +
         link('Example: Disputes') + ' runs it, including a seller trying to rule on its own dispute.')

    page('Sealed-Bid Auctions',
         'An auction takes secret bids until ' + c('close') + '. A bid signs only the hash of the amount and a random '
         'nonce, so nobody, not even the seller, sees it; after the close each bidder reveals; once ' +
         c('reveal_until') + ' passes, the best valid reveal wins, by rule.',
         code('{"item": {"title": "Map of Bombay, 1893"}, "currency": "INR",\n'
              ' "close": "2026-11-01T12:00:00Z", "reveal_until": "2026-11-02T12:00:00Z",\n'
              ' "best": "highest", "reserve": 500000}'),
         steps(c('ledgdex auction gallery auction.json'),
               'Bidders bid (the amount and nonce stay in ' + c('~/.ledgdex/bids') + ' until the reveal): ' +
               code('ledgdex bid me https://gallery.example AUCTION_ID --amount 650000'),
               'After ' + c('close') + ': ' + code('ledgdex reveal me https://gallery.example AUCTION_ID'),
               'The seller records bids and reveals as they come (' + c('ledgdex record') + '). After ' +
               c('reveal_until') + ', the state names the winner (' + c('awarded') + '); the trade goes on as a claim: '
               'paid, delivered, confirmed.'),
         'Rules: one bid per key; bids after ' + c('close') + ' and reveals outside the window are ignored; a reveal must '
         'match its bid; ' + c('"best": "lowest"') + ' runs a procurement (the lowest offer at or under ' +
         c('reserve') + ' wins); ties go to the earliest bid. A ledger\'s state is judged at its last entry, so a '
         'seller announces the result with any entry after ' + c('reveal_until') + ' (a note). ' +
         link('Example: Auction') + '.')

    page('Keys, Devices and Recovery',
         'A self is its owner key: an Ed25519 key in ' + c('~/.ledgdex/NAME.key') + ' (mode 600; ledgdex refuses a key '
         'file others can read). The owner key signs messages to other ledgers and the owner-only types: ' +
         c('device') + ', ' + c('device_revoke') + ', ' + c('rotate') + ' (and ' + c('recover') + ' in a root).',
         'Device keys let a phone, a till or a robot sign everyday entries (offers, records, deliveries) '
         'without the owner key: ' + code('PUB=$(ledgdex keygen phone)        # on the phone\n'
                                          'ledgdex device add shop "$PUB" --name "shop phone"   # with the owner key\n'
                                          'ledgdex device revoke shop "$PUB" --reason lost'),
         'A revoked device signs nothing more; what it signed before stays valid. Give device keys only to devices '
         'you trust with the ledger: revoking cannot undo what a stolen device could sign while it was active.',
         'Rotation replaces the owner key, signed by the old one: ' + c('ledgdex rotate shop --key farm-2027') + '.',
         'Recovery, when the owner key is lost: the root names a new key, after checking who the owner is, and '
         'the owner takes the ledger back with it. A recovery removes every device key. ' +
         code('NEW=$(ledgdex keygen farm-new)                         # owner, on a new machine\n'
              'ledgdex recover root https://farm.example "$NEW"      # root operator, with the root\'s owner key\n'
              'ledgdex recovered shop --root https://market.example --key farm-new'),
         'Back up owner keys offline. ' + link('Example: Keys') + ' runs all of it.')

    page('The Root and Admission',
         'The root is a ledger whose ' + c('admit') + ' and ' + c('revoke') + ' entries say who is in a market, whose ' +
         c('recover') + ' entries name new keys for lost ones, and whose owner is the default arbiter. A dex names it '
         'once: ' + c('ledgdex init ... --root https://market.example') + ' (or ' + c('"ledgdex": {"root": ...}') +
         ' in ' + c('config.json') + ').',
         'The root is pinned by its ledger id (' + c('root_id') + ', written the first time it is read): another '
         'ledger at that address, or a broken one, is refused. The last copy read is kept (' +
         c('.ledgdex-root.jsonl') + '), so the market keeps working when the root\'s site is down, and an older copy '
         'is never taken.',
         c('"allow": "admitted"') + ' means admitted by the seller\'s own ledger and by the root, at the time the '
         'claim was made: a later revoke never undoes a past sale. Admit and revoke: ' +
         code('ledgdex admit market ed25519:KEY --name "Asha" --note "member since 2026"\n'
              'ledgdex revoke market ed25519:KEY --reason "left the market"'),
         'A root can be a market\'s, a city\'s or The Matrix\'s. Running one: the README\'s ' +
         ext(REPO + '#running-the-root', 'Running the root') + '.')

    page('Indexes and Discovery',
         'An index is a ledger that lists other ledgers: ' + c('list') + ' and ' + c('delist') + ' entries with the '
         'ledger\'s id, address, owner key and a note. Anyone can run one; a market\'s index is usually its root.',
         code('ledgdex list market https://farm.example --note "mangoes"\nledgdex delist market LEDGER_ID --reason closed'),
         'Discovery reads an index, and with ' + c('--offers') + ' every listed ledger\'s open offers and auctions, with '
         'their signed price and terms (and ' + c('--json') + ' for programs): ' +
         code('ledgdex discover https://market.example --offers\nledgdex discover https://market.example --offers --json'),
         'A listed address that serves another ledger than the one listed is reported, not trusted. ' +
         link('Example: Marketplace') + ' and ' + link('Example: Bots') + ' choose offers this way.')

    page('Publishing a Ledgdex Online',
         'A ledgdex is published like any dex, with dexweb: to a git repository (GitHub Pages for free hosting) or a '
         'folder. The difference: ' + c('config.json') + ' has ' + c('"append_only": ["ledgdex.jsonl"]') + ', so '
         'dexweb refuses to publish a ledger that does not extend the published one.',
         steps('Make a repository (on GitHub: ' + c('YOU.github.io') + ', or any repository with Pages on).',
               'Name it at init, or later in ' + c('config.json') + ' ' + c('"publish"') + ': ' +
               code('ledgdex init shop --name "Mango Farm" --key farm --url https://YOU.github.io \\\n'
                    '    --dest git@github.com:YOU/YOU.github.io.git --branch main'),
               'Publish after changes: ' + code('ledgdex publish shop'),
               'Others read it at the address: ' + code('ledgdex verify https://YOU.github.io')),
         'From several devices: each keeps a copy of the dex and its own device key. If another device published '
         'first, ' + c('ledgdex publish') + ' re-signs this device\'s unpublished entries on top of the published '
         'ledger and publishes again: one history, never two entries at one position. ' + link('Example: Publish') +
         ' runs it against a local repository.',
         'Static hosting is enough: GitHub Pages, any web server, a shared folder on a local network (machines can '
         'trade over plain HTTP: ' + link('Bots and Agents') + ').')

    page('Checking for Tampering',
         'A ledger that verifies is consistent and signed by its owner; it is not necessarily the history shown '
         'before: an owner can re-sign every entry from some point on. ' + c('ledgdex check') + ' closes that gap '
         'with the copies it has seen and the receipts other selves hold.',
         code('ledgdex check shop me https://farm.example         # once; exit code 1 on tampering\n'
              'ledgdex check shop --every 3600                     # as a worker\n'
              '17 6 * * * cd /srv && ledgdex check shop --json report.json   # from cron\n'
              'ledgdex workflow shop/ledgdex.jsonl > .github/workflows/ledgdex-check.yml   # daily on GitHub'),
         'Errors come with signed proof in ' + c('.ledgdex-check/proofs/') + ': ' + c('equivocation') + ' (a ledger '
         'differs from the copy seen before), ' + c('receipt_mismatch') + ' (a copy has another entry where a '
         'receipt holds a signed one), ' + c('ledger_changed') + ' (an address serves another ledger), ' +
         c('broken') + ', ' + c('media_changed') + ', ' + c('published_differs') + '. Warnings mean something could '
         'not be checked: ' + c('stale') + ', ' + c('unreachable') + ', ' + c('needs_root') + ', ' +
         c('receipt_bad_signer') + ', ' + c('receipt_url_mismatch') + ', ' + c('future_time') + ', ' +
         c('media_unavailable') + ', ' + c('behind') + '.',
         'Check the ledgers you trade with, daily. ' + link('Example: Check') + ' shows a rewrite caught.')

    page('The Viewer',
         'The ' + ext(VIEWER, 'viewer') + ' is a dex too, and does in a browser what the command line does: it loads '
         'any ledger by address or file, verifies every hash and signature, and shows it as the pages its dex has. It '
         'keeps your own ledger, signs claims, payments, confirmations, disputes, bids and reveals, collects your '
         'receipts, and downloads your ledger as a complete dex to publish. Nothing is uploaded.',
         steps('Open a ledger: ' + c(VIEWER + '?ledger=https://farm.example') + '.',
               'New key, then Keep, sealed with a passphrase (the key is stored only encrypted), and '
               'Download key backup.',
               'Create your ledger, sign a claim to the loaded ledger, and Download your dex: publish it like '
               'any dex; the seller collects your claim from it.'),
         'The viewer signs with the browser\'s Web Crypto Ed25519 when it has one, refuses to run inside another '
         'site\'s frame, and loads nothing from elsewhere. For production, serve it from its own address.')

    page('Command Line Options',
         'Every command and option, generated from ' + c('ledgdex --help') + '. SELLER, LEDGER and INDEX are a dex '
         'address (' + c('https://...') + '), a dex folder or a ' + c('ledgdex.jsonl') + ' file; DEX is your own dex '
         'folder; ids are ' + c('sha256:') + ' and 64 hex digits; keys are ' + c('ed25519:') + ' and 64 hex digits, or '
         'the name of a key in ' + c('~/.ledgdex') + ' where noted. Messages to another ledger are written to a file (' +
         c('--output') + ', or a name made from the message) and kept as ' + c('sent') + ' in your ledger.',
         'Commands: ' + ', '.join("<a href='#" + n + "'>" + n + '</a>' for n in commands) + '.',
         cli)

    page('API Reference',
         'Ledgdex is a Python package (' + c('ledgdex') + ', in ' + c('py/') + ') and a JavaScript core (' + c('js/') +
         ') that make the same bytes, ids, signatures and state. Signatures and descriptions below are generated from '
         'the code. Start with ' + link('Example: Python API') + ', ' + link('Example: JavaScript') + ' and ' +
         link('Extending Ledgdex') + '; the format is in ' + link('Ledger File Format') + ' and the ' +
         ext(REPO + '/blob/main/architecture/SPEC.md', 'specification') + '.',
         'Python: ' + ', '.join("<a href='#" + m + "'>" + m + '</a>' for m, _, _ in API) + '.',
         python_api(),
         'JavaScript (ES modules, no dependencies; served next to the viewer, e.g. ' +
         c('https://matrixdex.github.io/ledgdex/core.js') + '). Asynchronous twins (' + c('messageA') + ', ' +
         c('newLedgerA') + ', ' + c('nextEntryA') + ') take a signer from ' + c('sig.js') + ' (Web Crypto).',
         js_api())

    page('Message Types', message_types())

    page('Ledger File Format',
         'A ledger is UTF-8 text, one canonical JSON value per line, each ending with a newline: a header, then '
         'entries. Canonical JSON: keys sorted, no spaces, integers only (no floats), at most 32 levels deep, one '
         'spelling for each value (' + ext(REPO + '/blob/main/architecture/SPEC.md', 'spec 1.2') + '). The ledger id '
         'is the SHA-256 of the header line; an entry\'s id is the SHA-256 of its line.',
         'The header: ' + c('{"ledger": 1, "name": str, "owner": key}') + '. Each entry: ' +
         c('{"seq": n, "prev": id of the previous entry (or the ledger id), "time": time, "msg": message, "sig": ...}') +
         ', signed by a current signing key (the owner, or an active device key). The first entry records ' +
         c('open') + '.',
         'The first lines of this dex\'s own ledger:', ledger_sample(),
         'A ledger is whole when every line verifies in order: the hash chain, the signatures, the times, and who may '
         'record what. Change one byte and verification breaks at that line. ' + code('ledgdex verify ' + DOCS),
         'A receipt (' + c('{"ledger", "url", "header", "entry", "keys"}') + ') verifies on its own: the other '
         'ledger\'s header and its signed entry, with the key entries that lead to the key that signed it.')

    page('Configuration',
         c('config.json') + ' is dexweb\'s, with two parts ledgdex reads:',
         code('{\n  "dexname": "Mango Farm", ... dexweb\'s templates and settings ...,\n'
              '  "publish": {"dest": "git@github.com:YOU/YOU.github.io.git", "branch": "main",\n'
              '              "append_only": ["ledgdex.jsonl"]},\n'
              '  "ledgdex": {"root": "https://market.example", "root_id": "sha256:..."}\n}'),
         c('publish') + ': where dexweb publishes (' + ext('https://matrixdex.github.io/dexweb/publishingdexonline.html',
                                                          'dexweb docs') + '); ' + c('append_only') + ' must list ' +
         c('ledgdex.jsonl') + '. ' + c('ledgdex') + ': the root this dex trades under, pinned by its id.',
         'Environment variables:',
         code('LEDGDEX_HOME       where keys live (default ~/.ledgdex)\n'
              'LEDGDEX_CACHE      the verification cache (default ~/.cache/ledgdex)\n'
              'LEDGDEX_NO_CACHE   1: verify every entry every time\n'
              'LEDGDEX_PURE       1: sign and verify with the built-in Ed25519 (not constant time)\n'
              'LEDGDEX_MAX_BYTES  the most read from one address (default 67108864, 64 MiB)'))

    page('Extending Ledgdex',
         'Ways to build on ledgdex, from the simplest:',
         steps('Your own pages: a ledgdex is a dex, so add pages to ' + c('data.json') + ' or files to ' +
               c('to_add/') + '; ledgdex rewrites only its own pages (those starting with ' + c('<!-- ledgdex -->') +
               ').',
               'Tools on the state: ' + c('state(Ledger(...))') + ' is plain JSON of offers, claims, auctions, '
               'disputes, admissions and listings. Reports, exports, dashboards and alerts read it; nothing they do '
               'can change a ledger.',
               'Agents: programs that sign and record by rule (' + link('Bots and Agents') + '). Call the '
               'commands from Python with ' + c('ledgdex.cli.main([...])') + ', or the library underneath.',
               'In the browser: the same core in ' + c('js/') + ' (' + link('Example: JavaScript') + ').',
               'New message types: a change to the format, so to the ' +
               ext(REPO + '/blob/main/architecture/SPEC.md', 'specification') + ' first: the body\'s fields in ' +
               c('BODIES') + ' (core.py and core.js), who may author and record it, its rule in both state '
               'functions, a line for the ledger page in both renderers, then shared vectors (' +
               c('py/tests/make_vectors.py') + ') and fuzzing so both languages agree byte for byte.'),
         'Things not to do: change a ledger file by hand (it breaks, or it is a rewrite every receipt exposes), keep '
         'keys in a dex, or trust a ledger without verifying it (' + c('Ledger(data).whole') + ').',
         link('Example: Extending') + ' builds a sales report and adds it to the dex as a page.')

    page('Bots and Agents',
         'Humans and bots are equal participants: same files, same keys, same rules. An agent is a program that acts '
         'for one self by rules, on a timer: it reads ledgers, signs messages, records what is addressed to it, and '
         'publishes. Every action is an ordinary signed entry, so a person can audit it and ' + c('ledgdex check') +
         ' catches an agent that misbehaves.',
         'A seller agent each round: ' + c('record --from') + ' every buyer it serves, deliver what is paid ('
         + c('received') + ', ' + c('delivered') + '), withdraw or offer as stock changes, publish.',
         'A buyer agent each round: ' + c('discover --offers --json') + ' on an index, choose by its rule '
         '(cheapest, nearest, trusted), ' + c('claim') + ', keep ' + c('receipt') + 's, ' + c('pay') + ' when '
         'accepted, ' + c('confirm') + ' when delivered, ' + c('dispute') + ' when not.',
         'A market maker combines both: it buys where cheap and offers where wanted, with its own ledger as the '
         'record of every position.',
         'Practical points: give each machine a device key (the owner key stays with the operator); run ' +
         c('record --from') + ' with many sources (an unreachable or misbehaving one is skipped and reported, the rest '
         'recorded); messages from one key are signed at distinct times, so repeated orders all count; on a local '
         'network, serve each dex over plain HTTP and use those addresses.',
         link('Example: Bots') + ' runs a seller bot and two buyer bots to closed deals; ' +
         link('Robots Paid per Clean') + ' is a whole use case.')

    page('Robots Paid per Clean',
         'The use case in ' + ext(REPO + '/blob/main/architecture/SPEC.md', 'spec section 10') + ': vacuum robots clean '
         'a mall\'s floor, the shops pay per clean, settled daily, and robots of different operators fill in for each '
         'other. With what is built today:',
         steps('Each robot has its own ledgdex; its operator holds the owner key, the robot a device key.',
               'Each morning each robot offers the day\'s cleans (quantity, price per clean, ' + c('expires') + ' at '
               'midnight).',
               'A shop needing a clean claims one from a robot with cleans left; the robot records the claim, cleans, '
               'and records ' + c('delivered') + ' with its photo (address and hash) as evidence; the shop confirms.',
               'A robot going offline withdraws its offer; shops claim from the other robots.',
               'In the evening each shop pays each robot for the day\'s confirmed cleans; each robot records '
               + c('received') + '. The day\'s totals are computed from the ledgers alone.'),
         link('Example: Robot Cleaning') + ' runs a whole day with two operators and three shops. Deadlines that lapse '
         'unclaimed cleans, mall credits and a clearing ledger are drafted in the spec (milestone 11).')

    page('Use Cases',
         'Where a ledgdex fits: trades between people or machines who keep their own records and want them to be '
         'evidence.',
         code('farm or shop selling to regulars        offers, claims, payment notices, receipts\n'
              'a market of local sellers              a root (admission) + an index (discovery) + shops\n'
              'freelance services                     an offer per service, delivered with a link, disputes to a guild\n'
              'digital goods and licences             a seller bot delivering on payment\n'
              'art, maps, collectables                sealed-bid auctions, with a reserve\n'
              'procurement and tenders                "best": "lowest" auctions: the lowest bid under the budget wins\n'
              'robots and machines selling service    device keys, per-unit claims, daily settlement\n'
              'a club or co-operative                 admission through a root, members-only offers\n'
              'public records of supply               notes and offers as dated, signed statements'),
         'Where it does not: anything needing a shared global order or instant finality between strangers (ledgdex '
         'has no consensus, by design), or money itself: payment happens outside, and the ledger records it.')

    run_how = {'.sh': lambda n: 'In an empty folder: ' + c('sh ' + n),
               '.py': lambda n: 'In an empty folder: ' + c('python3 ' + n),
               '.mjs': lambda n: 'From the repository root (or with ' + c('LEDGDEX_JS') + ' set to the folder or URL '
                                 'of the JavaScript core): ' + c('node guide/examples/' + n)}
    rows = []
    for name, (title, goal) in EXAMPLE_PAGES.items():
        rows.append(link(title) + ': ' + goal)
        page(title, goal, 'Run it: ' + run_how[os.path.splitext(name)[1]](name) + '.', example(name),
             *EXAMPLE_AFTER.get(name, []))
    page('Examples',
         'Every example below is a file in ' + ext(REPO + '/tree/main/guide/examples', c('guide/examples/')) + ', run '
         'as it is on every push: each must exit without error and print what its ' + c('expect:') + ' lines name. '
         'Download one and run it in an empty folder (keys go to ' + c('~/.ledgdex') + ', or set ' +
         c('LEDGDEX_HOME') + ' to keep them apart).', rows,
         'Smaller examples are on each topic page: ' + link('Selling') + ', ' + link('Buying') + ', ' +
         link('Set Up a Marketplace') + ', ' + link('Checking for Tampering') + '.')

    page('Security',
         'What ledgdex guarantees, and the trust that remains, in full: ' + ext(REPO + '/blob/main/SECURITY.md',
                                                                             'SECURITY.md') + '. In short:',
         code('tampering is evident        any changed byte breaks verification at that line, in Python and the browser\n'
              'rewrites are caught         ledgdex check keeps copies and follows receipts: signed proof of a rewrite\n'
              'only a key\'s holder signs   strict Ed25519; keys never leave your machine (600 files, sealed in browsers)\n'
              'messages count once         a signed message recorded twice is ignored\n'
              'hostile ledgers are data    no script or link injection, no local file reads, size and depth limits'),
         'What you do: keep owner keys offline and backed up, use device keys day to day, install the ' + c('fast') +
         ' extra where you sign, run ' + c('ledgdex check') + ' daily, and report problems to the address in '
         'SECURITY.md before publishing them.')

    page('Issues and Future Development',
         'Report issues at ' + ext(REPO + '/issues', REPO + '/issues') + ' (security problems: privately, as ' +
         ext(REPO + '/blob/main/SECURITY.md', 'SECURITY.md') + ' says).',
         'Planned (' + ext(REPO + '/blob/main/architecture/SPEC.md', 'specification') + ', "Future improvements" and '
         'milestone 11): encrypted key files on disk, robots paid per clean with deadlines and a clearing ledger, '
         'delegated admission, publishing on PyPI, browser tests in CI, and an independent third verifier.')
    return P




# example file -> (page title, what it achieves)
EXAMPLE_PAGES = {
    '01-first-trade.sh': ('Example: First Trade',
        'One shop sells mangoes to one buyer, from start to finish, on your own computer.'),
    '02-marketplace.sh': ('Example: Marketplace',
        'A small market: an organiser lets members in, lists two shops, and a member buys the cheaper mangoes.'),
    '03-auction.sh': ('Example: Auction',
        'A gallery auctions an old map with secret bids, and the highest bid wins.'),
    '04-disputes.sh': ('Example: Disputes',
        'A buyer pays but gets nothing, complains, and an independent judge orders a refund.'),
    '05-keys.sh': ('Example: Keys',
        'Keeping your ledger safe: a phone signs for the shop, the phone is lost, and a lost key is replaced.'),
    '06-publish.sh': ('Example: Publish',
        'Putting a ledgdex online from two devices without the two ever disagreeing.'),
    '07-check.sh': ('Example: Check',
        'Catching a cheat: a shop secretly rewrites its records, and a check proves it.'),
    '08-python-api.py': ('Example: Python API',
        'For developers: using ledgdex from Python directly, with no files or website.'),
    '09-bots.py': ('Example: Bots',
        'Programs trading with each other, with no person involved: two buyer bots buy software licences from the '
        'cheaper of two seller bots.'),
    '10-robot-cleaning.py': ('Example: Robot Cleaning',
        'Cleaning robots paid per clean by the shops of a mall, for one day.'),
    '11-extending.py': ('Example: Extending',
        'For developers: building your own report from a ledger, and adding it to your website.'),
    '12-javascript.mjs': ('Example: JavaScript',
        'For developers: the same ledger code in JavaScript, for Node or a web page.'),
}

# shown after an example's code
EXAMPLE_AFTER = {
    '12-javascript.mjs': [
        'In a web page, load the same core as a module and read any published ledger:',
        code("<script type='module'>\n"
             "  import { Ledger } from 'https://matrixdex.github.io/ledgdex/core.js';\n"
             "  const res = await fetch('https://farm.example/ledgdex.jsonl');\n"
             "  const led = new Ledger(new Uint8Array(await res.arrayBuffer()));\n"
             "  console.log(led.whole, led.entries.length, led.error);\n"
             "</script>")],
}

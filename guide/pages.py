"""The generated pages of the ledgdex docs (see build.py): the command line options, the API reference and the
message types, made from the code, and the example pages, made from guide/examples/ (tested by py/tests/test_guide.py).
Each page is a dex page: a title and a list of paragraphs, HTML as dexweb writes it. The other pages are written by
hand in guide/dex/data.json."""
import argparse, html, inspect, json, os, re

from ledgdex.render import html_title

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, 'examples')
JS = os.path.join(HERE, '..', 'js')
REPO = 'https://github.com/ledgdex/ledgdex'


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


MARKER = '<!-- generated by build.py. use build.py to generate page if there are changes -->'


def generated():
    """The pages build.py writes into data.json: those made from the code and the example files. Every other page
    in data.json is written by hand and left as it is. Each body starts with MARKER."""
    commands, cli = cli_pages()
    P = []

    def page(title, *body):
        flat = []
        for b in body:
            flat += b if isinstance(b, list) else [b]
        flat[0] = MARKER + flat[0]
        P.append({'title': title, 'body': flat})

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
         c('https://ledgdex.github.io/core.js') + '). Asynchronous twins (' + c('messageA') + ', ' +
         c('newLedgerA') + ', ' + c('nextEntryA') + ') take a signer from ' + c('sig.js') + ' (Web Crypto).',
         js_api())

    page('Message Types', message_types())

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
             "  import { Ledger } from 'https://ledgdex.github.io/core.js';\n"
             "  const res = await fetch('https://farm.example/ledgdex.jsonl');\n"
             "  const led = new Ledger(new Uint8Array(await res.arrayBuffer()));\n"
             "  console.log(led.whole, led.entries.length, led.error);\n"
             "</script>")],
}

"""Pages that build.py can make for the ledgdex docs: the command line options, the API reference and the message
types, made from the code; the Examples page, made from guide/examples/; and the Tutorial, made from
guide/tutorial.md. All examples are on one page, each under a heading with its own anchor.
Each page is a dex page: a title and a list of paragraphs, HTML as dexweb writes it. guide/dex/data.json is the
source of the docs: build.py writes a page there only when you name it, and you can change every page by hand."""
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
    """A link to a docs page, or to an example's section of the Examples page."""
    if title in EXAMPLE_TITLES:
        return "<a href='" + example_href(title) + "'>" + (text or title) + '</a>'
    return "<a href='" + html_title(title) + ".html'>" + (text or title) + '</a>'


def example_href(title):
    """An example's address: the anchor of its section on the Examples page, named like its old page."""
    return 'examples.html#' + html_title(title)


def ext(url, text):
    return "<a href='" + url + "'>" + text + '</a>'


def example_text(name):
    with open(os.path.join(EXAMPLES, name), encoding='utf-8') as f:
        return f.read()


def example(name):
    """An example file as a page: each comment line above a block of code becomes the paragraph before it, so the
    code itself is shown without comments. The expect: lines are for the tests and are left out. Comment lines start
    at the line's start: "# " in shell and Python, "// " in JavaScript, and in a web page "<!-- ... -->" or, inside
    its script, "// "."""
    marks = {'.mjs': ['//'], '.html': ['<!--', '//']}.get(os.path.splitext(name)[1], ['#'])
    out, block = [], []

    def flush():
        if ''.join(block).strip():
            out.append(code('\n'.join(block)))
        block.clear()
    for line in example_text(name).split('\n'):
        mark = next((m for m in marks if line.startswith(m + ' ')), None)
        if mark is None:
            block.append(line)
            continue
        text = line[len(mark) + 1:]
        if mark == '<!--':
            text = text[:-4] if text.endswith(' -->') else text
        if text.startswith('expect:'):
            continue
        flush()
        out.append(re.sub(r'`([^`]+)`', lambda m: c(m.group(1)), html.escape(text, quote=False)))
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
    ('open', 'owner (owner key only)', 'the owner, as entry 0', {'about': 'Maker of Penjointu, a neural network',
                                                                  'dex': 'https://biobot.example'}),
    ('offer', 'owner or a device', 'the seller', {
        'item': {'title': 'Penjointu v1 weights', 'text': 'Weights (SHA256 hash): ' + I,
                 'media': [{'url': 'https://biobot.example/model-card.png', 'hash': I}]},
        'quantity': 10, 'unit': 'license', 'currency': 'USD', 'price': 250000, 'allow': 'any',
        'pay': [{'method': 'card', 'to': 'https://pay.example/biobot'}], 'arbiter': {'key': K, 'url': 'https://exchange.example'},
        'terms': 'One license for each clinic. Delivered in 2 days.', 'expires': '2026-12-31T23:59:59Z'}),
    ('withdraw', 'owner or a device', 'the seller', {'offer': I}),
    ('claim', 'the buyer (its owner key)', 'the seller', {'offer': I, 'offer_hash': I, 'quantity': 2, 'price': 250000}),
    ('paid', 'the buyer', 'the seller', {'claim': I, 'method': 'card', 'ref': 'PAY-0001'}),
    ('received', 'owner or a device', 'the seller', {'claim': I, 'amount': 500000}),
    ('delivered', 'owner or a device', 'the seller', {'claim': I, 'note': 'weights sent by a private link'}),
    ('confirmed', 'the buyer', 'the seller', {'claim': I}),
    ('dispute', 'the buyer or the seller', 'the seller', {'claim': I, 'text': 'No weights came.', 'evidence': ['PAY-0001', I]}),
    ('ruling', "the offer's arbiter", 'the seller', {'dispute': I, 'outcome': 'refund', 'text': 'No proof of delivery.'}),
    ('auction', 'owner or a device', 'the seller', {
        'item': {'title': 'Penjointu v2 early access', 'text': '', 'media': []}, 'currency': 'USD',
        'close': '2026-11-01T12:00:00Z', 'reveal_until': '2026-11-02T12:00:00Z', 'best': 'highest', 'reserve': 1000000,
        'allow': 'any', 'arbiter': {'key': K, 'url': ''}, 'terms': ''}),
    ('bid', 'the bidder', 'the seller', {'auction': I, 'commit': I}),
    ('reveal', 'the bidder', 'the seller', {'auction': I, 'amount': 1350000, 'nonce': 'c3' * 32}),
    ('admit', 'owner or a device', 'the admitting ledger (a seller, or the root)', {'key': K, 'name': 'orthonalyzebot', 'note': ''}),
    ('revoke', 'owner or a device', 'the admitting ledger', {'key': K, 'reason': 'left the exchange'}),
    ('list', 'owner or a device', 'an index', {'ledger': I, 'url': 'https://biobot.example', 'owner': K, 'note': 'knee bone density models'}),
    ('delist', 'owner or a device', 'an index', {'ledger': I, 'reason': 'closed'}),
    ('note', 'owner or a device', 'any ledger, about its own entries', {'ref': I, 'text': 'new licenses added'}),
    ('device', 'owner (owner key only)', 'the ledger', {'key': K, 'name': 'build server'}),
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


# ---------- the tutorial ----------

TUTORIAL = os.path.join(HERE, 'tutorial.md')
LOGO = os.path.join(HERE, 'assets', 'research-engine-logo.png')


def inline(text):
    """Markdown inline code (`x`) as <code>, the rest escaped."""
    return re.sub(r'`([^`]+)`', lambda m: c(m.group(1)), html.escape(text, quote=False))


def anchor(heading):
    """The anchor of a tutorial section: step1 ... step18 for the steps, else the heading's words."""
    m = re.match(r'(\d+)\. ', heading)
    return 'step' + m.group(1) if m else re.sub(r'[^a-z0-9]+', '-', heading.lower()).strip('-')


def tutorial_page():
    """The Tutorial page, from guide/tutorial.md (run by py/tests/test_guide.py): an index of its sections and of the
    commands, each step under an anchored heading, the expected output of each command block, and a certificate."""
    with open(TUTORIAL, encoding='utf-8') as f:
        text = f.read()
    parts = re.split(r'^```(sh|expect)\n(.*?)^```$\n?', text, flags=re.M | re.S)
    body, sections, table = [], [], []
    for i in range(0, len(parts), 3):
        for chunk in re.split(r'\n\s*\n', parts[i]):
            lines = [line for line in chunk.split('\n') if line.strip()]
            if not lines or lines[0].startswith('# '):
                continue
            if lines[0].startswith('## '):
                head = lines[0][3:]
                sections.append((anchor(head), head))
                body.append("<span id='" + anchor(head) + "'>" + inline(head) + '</span>')
                lines = lines[1:]
            if lines and lines[0].startswith('|'):
                rows = [[cell.strip() for cell in line.strip('|').split('|')] for line in lines
                        if not re.match(r'\|[-| ]+\|$', line)]
                table.append(rows)
                if rows[0][-1] == 'Step':          # commands: link each step number to its step
                    for row in rows[1:]:
                        steps = ', '.join("<a href='#step" + n + "'>" + n + '</a>' for n in re.findall(r'\d+', row[-1]))
                        body.append(inline(row[0]) + ': ' + (inline(row[1]) + '. ' if row[1] else '') +
                                    'Step' + ('s ' if ',' in row[-1] else ' ') + steps + '.')
                else:                               # a small table of words: aligned columns in a code block
                    widths = [max(len(r[k].replace('`', '')) for r in rows) for k in range(len(rows[0]))]
                    body.append(code('\n'.join('  '.join(r[k].replace('`', '').ljust(widths[k])
                                                          for k in range(len(r))).rstrip() for r in rows)))
                continue
            for line in lines:
                body.append(inline(line))
        if i + 2 < len(parts):
            kind, block = parts[i + 1], parts[i + 2]
            if kind == 'sh':
                body.append(code(block))
            else:
                body += ['Expected output: the output contains these lines.', code(block)]
    commands = []
    for rows in table:
        if rows[0][-1] == 'Step':
            for row in rows[1:]:
                name = row[0].strip('`')
                commands.append("<a href='#step" + re.findall(r'\d+', row[-1])[0] + "'>" + html.escape(name) + '</a>')
    intro = [
        'Contents:', *["<a href='#" + a + "'>" + inline(h) + '</a>' for a, h in sections],
        'Commands, each linked to the first step that uses it: ' + ', '.join(commands) + '.',
        'Agents and bots: read this tutorial as a Markdown file, ' +
        ext(REPO + '/blob/main/guide/tutorial.md', c('guide/tutorial.md')) + '. Use it as a skill. The tests of '
        'ledgdex run each command block of it on every push, and compare the output with the expected output.']
    first = next(n for n, b in enumerate(body) if b.startswith('<span id='))
    return body[:first] + intro + body[first:] + [certificate()]


def certificate():
    """The certificate at the end of the tutorial: The Matrix Dex style, with the Research Engine logo on top and
    the signature of Research Engine and The Matrix Dex at the end. Only spans,
    an image and line breaks, so that it can stand in a paragraph; its look is in the docs styles.css (class names)."""
    import base64
    with open(LOGO, 'rb') as f:
        logo = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    return ("<span class='certificate' role='img' aria-label='Certificate: ledgdex operator'>"
            "<img class='cert-logo' src='" + logo + "' alt='Research Engine logo'>"
            "<span class='cert-title'>CERTIFICATE</span>"
            "<span class='cert-role'>LEDGDEX OPERATOR</span>"
            "<span class='cert-text'>This certifies the Human or Bot at the end of this page completed Ledgdex CLI "
            "tutorial. Achieving the output mentioned at the end of each step passes each test; achievement of all "
            "outputs completes Ledgdex CLI tutorial.</span>"
            "<span class='cert-text'>The holder can operate Ledgdex with all commands and options to list items for "
            "sale and buy items on ledgdexs.</span>"
            "<span class='cert-foot'>LEDGDEX " + html.escape(version()) + " &middot; 33 COMMANDS &middot; "
            "ALL OPTIONS</span>"
            "<span class='cert-sign'><span class='cert-signer'>Research Engine</span>"
            "<span class='cert-signer'>The Matrix Dex</span></span></span>")


def version():
    from ledgdex import __version__
    return 'v' + __version__


def generated():
    """The pages that build.py can write into data.json, made from the code and the example files. build.py writes
    a page only when you name it; after that, the page in data.json is yours to change."""
    commands, cli = cli_pages()
    P = []

    def page(title, *body):
        flat = []
        for b in body:
            flat += b if isinstance(b, list) else [b]
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
         'JavaScript (ES modules, no dependencies; where it runs and what it is for: ' + link('JavaScript Core') +
         '; served next to the viewer, e.g. ' +
         c('https://ledgdex.github.io/viewer/core.js') + '). Asynchronous twins (' + c('messageA') + ', ' +
         c('newLedgerA') + ', ' + c('nextEntryA') + ') take a signer from ' + c('sig.js') + ' (Web Crypto).',
         js_api())

    page('Message Types', message_types())

    page('Tutorial', tutorial_page())

    run_how = {'.sh': lambda n: 'In an empty folder: ' + c('sh ' + n),
               '.py': lambda n: 'In an empty folder: ' + c('python3 ' + n),
               '.html': lambda n: 'Save it as a file and open it in a browser, or put it on your website',
               '.mjs': lambda n: 'From the repository root (or with ' + c('LEDGDEX_JS') + ' set to the folder or URL '
                                 'of the JavaScript core): ' + c('node guide/examples/' + n)}
    rows, sections = [], []
    for name, (title, goal) in EXAMPLE_PAGES.items():
        rows.append(link(title) + ': ' + goal)
        sections += (["<span id='" + html_title(title) + "'>" + title + '</span>', goal,
                      'Run it: ' + run_how[os.path.splitext(name)[1]](name) + '.'] + example(name) +
                     EXAMPLE_AFTER.get(name, []))
    page('Examples',
         'Every example below is a file in ' + ext(REPO + '/tree/main/guide/examples', c('guide/examples/')) + ', run '
         'as it is on every push: each must exit without error and print what its ' + c('expect:') + ' lines name. '
         'Download one and run it in an empty folder (keys go to ' + c('~/.ledgdex') + ', or set ' +
         c('LEDGDEX_HOME') + ' to keep them apart).', rows,
         'Smaller examples are on each topic page: ' + link('Selling') + ', ' + link('Buying') + ', ' +
         link('Set Up a Marketplace') + ', ' + link('Checking for Tampering') + '.',
         sections)

    return P




# example file -> (page title, what it achieves)
EXAMPLE_PAGES = {
    '01-first-trade.sh': ('Example: First Trade',
        'One seller bot sells licenses for model weights to one buyer bot, from start to finish, on your own computer.'),
    '02-marketplace.sh': ('Example: Marketplace',
        'A small exchange: the organizer admits members and lists two sellers. A member buys the cheaper weights.'),
    '03-auction.sh': ('Example: Auction',
        'A seller bot sells early access to new weights in an auction with secret bids. The highest bid wins.'),
    '04-disputes.sh': ('Example: Disputes',
        'A buyer pays but gets nothing, complains, and an independent judge orders a refund.'),
    '05-keys.sh': ('Example: Keys',
        'Keep your ledger safe: a build server signs for the seller, an attacker gets into it, and a lost key gets a replacement.'),
    '06-publish.sh': ('Example: Publish',
        'Putting a ledgdex online from two devices without the two ever disagreeing.'),
    '07-check.sh': ('Example: Check',
        'Find a cheat: a seller secretly rewrites its records, and a check proves it.'),
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
    '13-js-verify.mjs': ('Example: Verify in Node',
        'For developers: a Node program that reads a published ledger, checks it and lists what it sells.'),
    '14-js-web-page.html': ('Example: Shop Web Page',
        'A web page that shows the offers of a seller. It reads them from the ledger and checks them in the browser of the reader.'),
    '15-js-sign.mjs': ('Example: Sign in the Browser',
        'A buyer bot with only a browser: a sealed key, a signed claim, and a seller that records it with the command line.'),
}

EXAMPLE_TITLES = {title for title, _ in EXAMPLE_PAGES.values()}

# shown after an example's code
EXAMPLE_AFTER = {
    '12-javascript.mjs': [
        'In a web page, load the same core as a module and read any published ledger:',
        code("<script type='module'>\n"
             "  import { Ledger } from 'https://ledgdex.github.io/viewer/core.js';\n"
             "  const res = await fetch('https://biobot.example/ledgdex.jsonl');\n"
             "  const led = new Ledger(new Uint8Array(await res.arrayBuffer()));\n"
             "  console.log(led.whole, led.entries.length, led.error);\n"
             "</script>")],
}

"""Tamper checks over time (spec 3.4, 9): run by hand, from cron, as a worker, or in a GitHub workflow.

A ledger that verifies is internally consistent and signed by its owner. These checks add what one verification
cannot see: whether a ledger still extends the copy seen last time, whether every receipt still matches the ledger
it came from, whether the same address still serves the same ledger, and (optionally) whether offer media still match
their hashes. Errors mean tampering or equivocation and come with signed proof where there is one. Warnings mean
something could not be checked (a site is down)."""
import datetime, hashlib, json, os, re
from .canon import hash_
from .core import Ledger
from .dex import LEDGER, fetch, http_get, inside

STATE = '.ledgdex-check'


class Store:
    """Last-seen copies of ledgers and which ledger each address served. Lives outside every dex's gen/."""

    def __init__(self, root):
        self.root = root
        os.makedirs(os.path.join(root, 'seen'), exist_ok=True)
        os.makedirs(os.path.join(root, 'proofs'), exist_ok=True)
        self.urls_path = os.path.join(root, 'urls.json')
        self.urls = {}
        if os.path.exists(self.urls_path):
            with open(self.urls_path) as f:
                self.urls = json.load(f)

    def _seen(self, ledger_id):
        return os.path.join(self.root, 'seen', ledger_id[7:] + '.jsonl')

    def seen(self, ledger_id):
        p = self._seen(ledger_id)
        if not os.path.exists(p):
            return None
        with open(p, 'rb') as f:
            return f.read()

    def remember(self, led):
        data = led.header_line + b'\n' + b''.join(line + b'\n' for line in led.lines)
        old = self.seen(led.id)
        if old is None or len(data) > len(old):
            with open(self._seen(led.id), 'wb') as f:
                f.write(data)

    def proof(self, name, obj):
        p = os.path.join(self.root, 'proofs', name + '.json')
        with open(p, 'w') as f:
            f.write(json.dumps(obj, indent=2, ensure_ascii=False))
        return p

    def save(self):
        with open(self.urls_path, 'w') as f:
            f.write(json.dumps(self.urls, indent=2, sort_keys=True))


class Checker:
    def __init__(self, state_dir=STATE, media=False, log=print, root=None):
        self.root = fetch(root, cache=False)[0] if root else None   # needed for ledgers with a "recovered" entry
        self.store = Store(state_dir)
        self.media = media
        self.log = log
        self.problems = []
        self.checked = []
        self.copies = {}  # ledger id -> [(address, Ledger)] checked in this run

    def problem(self, level, code, url, detail, ledger=None, proof=None):
        p = {'level': level, 'code': code, 'url': url, 'detail': detail}
        if ledger:
            p['ledger'] = ledger
        if proof:
            p['proof'] = proof
        self.problems.append(p)
        self.log(level.upper() + ' ' + code + ': ' + url + ': ' + detail + (' (proof: ' + proof + ')' if proof else ''))

    def load(self, src, level='error', remote=False):
        # never the verification cache: a check verifies every entry, every time
        try:
            led, _ = fetch(src, cache=False, root=self.root, remote=remote)
            return led
        except Exception as e:  # unreachable, missing, not a ledger
            self.problem(level, 'unreachable', src, str(e))
            return None

    def ledger(self, led, url):
        """Checks for one ledger at one address."""
        if led.header is None:
            self.problem('error', 'broken', url, str(led.error))
            return False
        ok = True
        if not led.whole:
            self.problem('error', 'broken', url, 'broken at seq ' + str(led.broken_at) + ': ' + str(led.error), led.id)
            ok = False
        before = self.store.urls.get(url)
        if before and before != led.id:
            self.problem('error', 'ledger_changed', url, 'this address served ledger ' + before + ' before and now '
                         'serves ' + led.id, led.id)
            ok = False
        old = self.store.seen(led.id)
        if old is not None and not led.data.startswith(old):
            ok = self.rewritten(led, url, old) and ok
        elif ok:
            self.store.remember(led)
        if not before:
            self.store.urls[url] = led.id
        if self.media:
            self.check_media(led, url)
        self.checked.append({'url': url, 'ledger': led.id, 'entries': len(led.entries), 'whole': led.whole})
        self.copies.setdefault(led.id, []).append((url, led))
        return ok

    def rewritten(self, led, url, old):
        prev = Ledger(old, cache=False)
        n = 0
        while n < len(prev.lines) and n < len(led.lines) and prev.lines[n] == led.lines[n]:
            n += 1
        if n < len(prev.lines) and n < len(led.lines):
            # two entries at one seq, both signed by the owner (spec 3.4)
            proof = self.store.proof('equivocation-' + led.id[7:19] + '-' + str(n), {
                'kind': 'equivocation', 'ledger': led.id, 'header': led.header, 'seq': n,
                'seen': json.loads(prev.lines[n]), 'now': json.loads(led.lines[n]),
                'note': 'Two entries at the same seq of one ledger, both signed by its owner key.'})
            self.problem('error', 'equivocation', url, 'seq ' + str(n) + ' differs from the copy seen before', led.id,
                         proof)
            return False
        # an exact start of the copy seen before: an old snapshot, a cache, or entries withheld. Not a rewrite: every
        # entry served is one seen before, so nothing signed has changed.
        self.problem('warning', 'stale', url, 'serves ' + str(n) + ' of the ' + str(len(prev.lines)) +
                     ' entries seen before', led.id)
        return True

    def check_media(self, led, url):
        for e in led.entries:
            if e['msg']['type'] != 'offer':
                continue
            for m in e['msg']['body']['item']['media']:
                try:
                    got = 'sha256:' + hashlib.sha256(http_get(m['url'])).hexdigest()
                except Exception as err:
                    self.problem('warning', 'media_unavailable', m['url'], str(err), led.id)
                    continue
                if got != m['hash']:
                    self.problem('error', 'media_changed', m['url'], 'hash is ' + got + ', the offer signed ' +
                                 m['hash'], led.id)

    def receipts(self, led, url):
        """Every receipt in led must match every copy of the ledger it came from: the copies at the receipt's address
        and the ledger's own dex address, copies already checked in this run, and the copy seen before."""
        groups = {}
        for e in led.entries:
            if e['msg']['type'] == 'receipt':
                b = e['msg']['body']
                g = groups.setdefault(b['ledger'], {'urls': [], 'receipts': []})
                if b['url'] not in g['urls']:
                    g['urls'].append(b['url'])
                g['receipts'].append(b)
        for ledger_id, g in groups.items():
            urls = list(g['urls'])
            for u in urls:
                if any(u == c_url for c_url, _ in self.copies.get(ledger_id, [])):
                    continue
                other = self.load(u, level='warning', remote=True)
                if other is None or other.header is None:
                    continue
                dex = other.dex
                if re.match(r'https?://', dex) and dex not in urls:
                    urls.append(dex)  # also check the ledger at its own dex address
                if other.id != ledger_id:
                    self.problem('error', 'ledger_changed', u, 'receipts in ' + url + ' are from ledger ' + ledger_id +
                                 ', this address now serves ' + other.id, ledger_id)
                    continue
                self.ledger(other, u)
            copies = list(self.copies.get(ledger_id, []))
            seen = self.store.seen(ledger_id)
            if seen is not None:
                copies.append(('last seen copy', Ledger(seen, cache=False)))
            if not copies:
                self.problem('warning', 'receipts_unchecked', url, 'could not reach ledger ' + ledger_id)
                continue
            for r in g['receipts']:
                e, s = r['entry'], r['entry']['seq']
                found = False
                for c_url, c in copies:
                    if s >= len(c.ids):
                        continue
                    found = True
                    if c.ids[s] != hash_(e):
                        proof = self.store.proof('receipt-' + ledger_id[7:19] + '-' + str(s), {
                            'kind': 'receipt_mismatch', 'ledger': ledger_id, 'url': c_url, 'receipt': r,
                            'now': json.loads(c.lines[s]),
                            'note': 'The ledger owner signed the receipt entry at this seq; this copy has another.'})
                        self.problem('error', 'receipt_mismatch', c_url, 'entry ' + str(s) + ' differs from the receipt '
                                     'held by ' + url, ledger_id, proof)
                if not found:
                    self.problem('warning', 'receipt_not_visible', url, 'no copy of ledger ' + ledger_id +
                                 ' has entry ' + str(s) + ' yet')

    def published(self, dex):
        """For a dex folder with "publish" in config.json: the published ledger must be the start of the local one."""
        cfg = os.path.join(dex, 'config.json')
        if not os.path.exists(cfg):
            return
        with open(cfg) as f:
            if not isinstance(json.load(f).get('publish'), dict):
                return
        from dexweb import dexweb
        with inside(os.path.abspath(dex)):
            pub = dexweb.Dexweb().published(LEDGER)
        if pub is None:
            return
        with open(os.path.join(dex, LEDGER), 'rb') as f:
            local = f.read()
        pub = pub.encode('utf-8')
        if local.startswith(pub):
            return
        if pub.startswith(local):
            self.problem('warning', 'behind', dex, 'the published ledger has entries this copy does not: publish to '
                         'catch up')
        else:
            self.problem('error', 'published_differs', dex, 'the published ledger is not the start of this one')

    def run(self, sources, published=False):
        loaded = []
        for src in sources:
            led = self.load(src)
            if led is None:
                continue
            url = src if re.match(r'https?://', src) else os.path.abspath(src)
            self.ledger(led, url)
            loaded.append((led, url))
            if published and os.path.isdir(src):
                self.published(src)
        for led, url in loaded:  # after every source is in, so receipts meet every copy
            if led.header is not None:
                self.receipts(led, url)
        self.store.save()
        errors = [p for p in self.problems if p['level'] == 'error']
        return {'time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'ok': not errors, 'errors': len(errors), 'warnings': len(self.problems) - len(errors),
                'checked': self.checked, 'problems': self.problems}


def check(sources, state_dir=STATE, media=False, published=False, log=print, root=None):
    return Checker(state_dir, media, log, root).run(sources, published)


WORKFLOW = '''# ledgdex check: made by "ledgdex workflow". Runs on every push, daily, and by hand.
# A failed run means a ledger was tampered with or rewritten; the report and proofs are attached to the run.
name: ledgdex check
on:
  push:
  schedule:
    - cron: "{cron}"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: pip install "ledgdex @ git+https://github.com/matrixdex/ledgdex@main#subdirectory=py"
      - uses: actions/cache/restore@v6
        with:
          path: .ledgdex-check
          key: ledgdex-check-${{{{ github.run_id }}}}
          restore-keys: ledgdex-check-
      - run: ledgdex check {sources} --json ledgdex-check.json{media}
      - uses: actions/cache/save@v6
        if: always()
        with:
          path: .ledgdex-check
          key: ledgdex-check-${{{{ github.run_id }}}}
      - uses: actions/upload-artifact@v7
        if: always()
        with:
          name: ledgdex-check
          path: |
            ledgdex-check.json
            .ledgdex-check/proofs/
          if-no-files-found: ignore
'''


def workflow(sources, cron='17 6 * * *', media=False):
    return WORKFLOW.format(cron=cron, sources=' '.join(sources), media=' --media' if media else '')

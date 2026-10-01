"""Publishing a ledgdex with dexweb (spec 7.4): catch up, re-sequence unpublished entries, publish, retry."""
import json, os
from .canon import hash_
from .core import Ledger, Invalid, OWNER_ONLY
from .dex import LEDGER, find_key, inside, load, signer, write
from .render import render

TRIES = 3


def check_config(dex):
    path = os.path.join(dex, 'config.json')
    if not os.path.exists(path):
        raise Invalid(dex + ' is not a dex: config.json is missing')
    with open(path) as f:
        p = json.load(f).get('publish')
    if not isinstance(p, dict) or LEDGER not in p.get('append_only', []):
        raise Invalid('config.json "publish" must have "append_only": ["' + LEDGER + '"] (spec 7.4)')


def catch_up(dex, old, at=None):
    """Put this dex's unpublished entries on top of the published ledger `old` (bytes). Spec 3.5 rule 3."""
    local = load(dex)
    if local.data.startswith(old):
        return 0
    pub = Ledger(old, root=local.root)
    if not pub.whole:
        raise Invalid('the published ' + LEDGER + ' is broken: ' + str(pub.error))
    if pub.id != local.id:
        raise Invalid('the published ' + LEDGER + ' is a different ledger')
    shared = 0
    while shared < min(len(pub.lines), len(local.lines)) and pub.lines[shared] == local.lines[shared]:
        shared += 1
    published_msgs = {hash_(e['msg']) for e in pub.entries}
    moved = 0
    for e in local.entries[shared:]:
        if hash_(e['msg']) in published_msgs:
            continue
        m = e['msg']
        secret = find_key(m['by']) if m['type'] == 'recovered' else signer(pub, owner_only=m['type'] in OWNER_ONLY)
        pub.append(pub.next_entry(secret, m, at=max(at or e['time'], e['time'])))
        moved += 1
    write(dex, pub.data)
    return moved


def publish(dex, at=None):
    """Spec 7.4. True when every entry in the ledger is published."""
    from dexweb import dexweb
    check_config(dex)
    dex = os.path.abspath(dex)
    with inside(dex):
        old = dexweb.Dexweb().published(LEDGER)
    plain_retry = True
    for _ in range(TRIES + 1):
        if old is not None:
            moved = catch_up(dex, old.encode('utf-8'), at)
            if moved:
                print('re-sequenced ' + str(moved) + ' unpublished entries on top of the published ledger')
        render(dex)
        with inside(dex):
            if dexweb.Dexweb().publish():
                return True
            new = dexweb.Dexweb().published(LEDGER)
        if new == old:
            # the ledger did not move: the push failed for another reason, such as another dex publishing to the
            # same repository at the same moment. Try once more; a second failure is reported.
            if not plain_retry:
                return False
            plain_retry = False
        old = new  # another device published first: catch up and try again
    return False

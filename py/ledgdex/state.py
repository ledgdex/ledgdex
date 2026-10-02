"""The state function (spec 6): replay a ledger into one JSON object."""
from .canon import hash_
from .core import Keys

OUTCOME = {'release': 'released', 'refund': 'refunded', 'split': 'split'}


def admissions(root):
    """The root's admit and revoke entries in order, as {key: [(time, admitted)]} (a message recorded twice counts
    once, as in 6.2). A claim is judged by the root's admissions at its own time, never by later ones (spec 5.7)."""
    out, seen = {}, set()
    for e in root.entries:
        m = e['msg']
        if m['type'] in ('admit', 'revoke') and hash_(m) not in seen:
            out.setdefault(m['body']['key'], []).append((e['time'], m['type'] == 'admit'))
        seen.add(hash_(m))
    return out


def admitted_at(admits, key, t):
    """Whether the root had admitted key at time t."""
    now = False
    for time, admitted in admits.get(key, []):
        if time > t:
            break
        now = admitted
    return now


def state(led, root=None, now=None):
    """Replay a parsed Ledger. root: the root Ledger, for "allow": "admitted" (spec 5.7). now: the time auction
    statuses are judged at (default: the time of the last entry)."""
    keys = Keys(led.header['owner']) if led.header else None
    admitted = set()
    root_admits = admissions(root) if root is not None and root.header else None
    offers, claims, auctions, disputes, listings, recoveries, ignored = {}, {}, {}, {}, {}, {}, []
    sellers = {}    # deal id -> the offer or auction body (for its arbiter)
    offer_hash = {}  # offer id -> hash of its message
    hidden = {}     # auction id -> bids, reveals, body (not in the output)

    def ignore(n, reason):
        ignored.append({'seq': n, 'reason': reason})

    def mine(key):
        return key == keys.owner or key in keys.devices

    def may(allow, key, t):
        if allow == 'any':
            return True
        if allow == 'admitted':
            return key in admitted and (root_admits is None or admitted_at(root_admits, key, t))
        return key in allow

    def award(aid, t):
        """The deal for an auction once its reveals are over (spec 5.6), or None."""
        a, h = auctions[aid], hidden[aid]
        if t < h['body']['reveal_until']:
            return None
        if 'decided' not in h:
            h['decided'] = True
            b, best = h['body'], None
            for key, bid in sorted(h['bids'].items(), key=lambda kv: kv[1]['seq']):
                amt = h['reveals'].get(key)
                if amt is None:
                    continue
                if (b['best'] == 'highest' and amt < b['reserve']) or (b['best'] == 'lowest' and amt > b['reserve']):
                    continue
                if best is None or (amt > best[1] if b['best'] == 'highest' else amt < best[1]):
                    best = (key, amt)
            if best:
                a['winner'], a['amount'] = best
                a['buyer'] = best[0]
                a['status'] = 'accepted'
        return a if 'winner' in a else None

    def deal(n, ref, t, need=True):
        if ref in claims:
            d = claims[ref]
        elif ref in auctions:
            d = award(ref, t)
            if d is None:
                ignore(n, 'not_awarded')
                return None
        else:
            ignore(n, 'unknown_claim')
            return None
        if need and d['status'] not in ('accepted', 'closed'):
            ignore(n, 'claim_not_accepted')
            return None
        return d

    def maybe_close(d):
        if d['status'] == 'accepted' and 'received' in d and d.get('delivered') and d.get('confirmed'):
            d['status'] = 'closed'

    recorded = set()   # message ids: a message recorded twice counts once (no replayed claims)
    for n, (e, id_) in enumerate(zip(led.entries, led.ids)):
        m, b, t, at = e['msg'], e['msg']['body'], e['msg']['type'], e['time']
        mid = hash_(m)
        if mid in recorded:
            ignore(n, 'duplicate_message')
            continue
        recorded.add(mid)
        if t == 'offer':
            offers[id_] = {'title': b['item']['title'], 'remaining': b['quantity'], 'status': 'open'}
            offer_hash[id_] = mid   # hashed once, not again for every claim
            sellers[id_] = b
        elif t == 'withdraw':
            o = offers.get(b['offer'])
            if o is None or o['status'] != 'open':
                ignore(n, 'offer_not_open')
            else:
                o['status'] = 'withdrawn'
        elif t == 'admit':
            admitted.add(b['key'])
        elif t == 'revoke':
            admitted.discard(b['key'])
        elif t == 'claim':
            c = {'offer': b['offer'], 'buyer': m['by'], 'quantity': b['quantity'], 'price': b['price']}
            claims[id_] = c
            o, ob = offers.get(b['offer']), sellers.get(b['offer'])
            if o is None:
                reason = 'unknown_offer'
            elif b['offer_hash'] != offer_hash[b['offer']]:
                reason = 'offer_changed'
            elif o['status'] == 'withdrawn':
                reason = 'withdrawn'  # a sold offer falls through to bad_quantity
            elif 'expires' in ob and at >= ob['expires']:
                reason = 'expired'
            elif mine(m['by']):
                reason = 'self_claim'  # a self never buys from its own ledger
            elif not may(ob['allow'], m['by'], at):
                reason = 'not_allowed'
            elif b['quantity'] < 1 or b['quantity'] > o['remaining']:
                reason = 'bad_quantity'
            elif b['price'] != ob['price']:
                reason = 'price_mismatch'
            else:
                reason = None
            if reason:
                c['status'], c['reason'] = 'rejected', reason
            else:
                c['status'] = 'accepted'
                sellers[id_] = ob
                o['remaining'] -= b['quantity']
                if o['remaining'] == 0:
                    o['status'] = 'sold'
        elif t in ('paid', 'confirmed'):
            d = deal(n, b['claim'], at)
            if d is not None:
                if m['by'] != d['buyer']:
                    ignore(n, 'not_buyer')
                elif t == 'paid':
                    d['paid'] = {'method': b['method'], 'ref': b['ref']}
                elif not d.get('delivered'):
                    ignore(n, 'not_delivered')
                else:
                    d['confirmed'] = True
                    maybe_close(d)
        elif t in ('received', 'delivered'):
            d = deal(n, b['claim'], at)
            if d is not None:
                if t == 'received':
                    d['received'] = b['amount']
                else:
                    d['delivered'] = True
                maybe_close(d)
        elif t == 'dispute':
            d = deal(n, b['claim'], at)
            if d is not None:
                if m['by'] != d['buyer'] and not mine(m['by']):
                    ignore(n, 'not_party')
                else:
                    d['status'] = 'disputed'
                    disputes[id_] = {'claim': b['claim']}
        elif t == 'ruling':
            dp = disputes.get(b['dispute'])
            if dp is None:
                ignore(n, 'unknown_dispute')
            elif 'ruling' in dp:
                ignore(n, 'already_ruled')
            else:
                ref = dp['claim']
                src = sellers.get(ref) if ref in claims else hidden[ref]['body']
                if m['by'] != src['arbiter']['key']:
                    ignore(n, 'not_arbiter')
                else:
                    dp['ruling'] = id_
                    (claims.get(ref) or auctions[ref])['status'] = OUTCOME[b['outcome']]
        elif t == 'auction':
            auctions[id_] = {'status': 'open', 'bids': 0}
            hidden[id_] = {'body': b, 'bids': {}, 'reveals': {}}
        elif t == 'bid':
            h = hidden.get(b['auction'])
            if h is None:
                ignore(n, 'unknown_auction')
            elif at >= h['body']['close']:
                ignore(n, 'late_bid')
            elif mine(m['by']):
                ignore(n, 'self_bid')
            elif not may(h['body']['allow'], m['by'], at):
                ignore(n, 'not_allowed')
            elif m['by'] in h['bids']:
                ignore(n, 'duplicate_bid')
            else:
                h['bids'][m['by']] = {'commit': b['commit'], 'seq': n}
                auctions[b['auction']]['bids'] += 1
        elif t == 'reveal':
            h = hidden.get(b['auction'])
            bid = h['bids'].get(m['by']) if h else None
            if h is None:
                ignore(n, 'unknown_auction')
            elif at < h['body']['close']:
                ignore(n, 'early_reveal')
            elif at >= h['body']['reveal_until']:
                ignore(n, 'late_reveal')
            elif bid is None:
                ignore(n, 'no_bid')
            elif m['by'] in h['reveals']:
                ignore(n, 'duplicate_reveal')
            elif hash_({'amount': b['amount'], 'nonce': b['nonce']}) != bid['commit']:
                ignore(n, 'bad_reveal')
            else:
                h['reveals'][m['by']] = b['amount']
        elif t == 'list':
            listings[b['ledger']] = {'url': b['url'], 'owner': b['owner'], 'note': b['note']}
        elif t == 'delist':
            if listings.pop(b['ledger'], None) is None:
                ignore(n, 'not_listed')
        elif t == 'recover':
            recoveries[b['ledger']] = {'key': b['key'], 'entry': id_}
        elif t == 'sent':
            if not mine(b['msg']['by']):
                ignore(n, 'not_my_message')
        elif t == 'receipt':
            if not mine(b['entry']['msg']['by']):
                ignore(n, 'not_my_message')
        if t in ('rotate', 'device', 'device_revoke', 'recovered'):
            keys.apply(m)

    when = now or (led.entries[-1]['time'] if led.entries else None)
    for aid, a in auctions.items():
        b = hidden[aid]['body']
        if when is None or when < b['close']:
            a['status'] = 'open'
        elif when < b['reveal_until']:
            a['status'] = 'revealing'
        else:
            if award(aid, when) is None:
                a['status'] = 'no_winner'
            elif a['status'] == 'accepted':
                a['status'] = 'awarded'
        a.pop('buyer', None)

    head = led.head()
    return {
        'ledger': led.id,
        'owner': keys.owner if keys else None,
        'devices': sorted(keys.devices) if keys else [],
        'head': head if head else {'seq': -1, 'id': led.id},
        'broken_at': led.broken_at,
        'admitted': sorted(admitted),
        'offers': offers,
        'claims': claims,
        'auctions': auctions,
        'disputes': disputes,
        'listings': listings,
        'recoveries': recoveries,
        'ignored': ignored,
    }

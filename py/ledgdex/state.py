"""The state function (spec 6), for the v1 market types."""
from .canon import hash_


def state(led):
    """Replay a parsed Ledger and return the state object (spec 6.3)."""
    owner = led.owner
    admitted = set()
    offers, claims, ignored = {}, {}, []
    offer_msgs = {}

    def ignore(n, reason):
        ignored.append({'seq': n, 'reason': reason})

    def claim_of(n, b, need='accepted'):
        c = claims.get(b['claim'])
        if c is None:
            ignore(n, 'unknown_claim')
        elif need and c['status'] not in ('accepted', 'closed'):
            ignore(n, 'claim_not_accepted')
        else:
            return c
        return None

    for n, (e, id_) in enumerate(zip(led.entries, led.ids)):
        m, b, t = e['msg'], e['msg']['body'], e['msg']['type']
        if t == 'offer':
            offers[id_] = {'title': b['item']['title'], 'remaining': b['quantity'], 'status': 'open'}
            offer_msgs[id_] = m
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
            o, om = offers.get(b['offer']), offer_msgs.get(b['offer'])
            ob = om['body'] if om else None
            if o is None:
                reason = 'unknown_offer'
            elif b['offer_hash'] != hash_(om):
                reason = 'offer_changed'
            elif o['status'] == 'withdrawn':
                reason = 'withdrawn'  # a sold offer falls through to bad_quantity
            elif 'expires' in ob and e['time'] >= ob['expires']:
                reason = 'expired'
            elif m['by'] == owner:
                reason = 'self_claim'  # a self never buys from its own ledger
            elif not allowed(ob['allow'], m['by'], admitted):
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
                o['remaining'] -= b['quantity']
                if o['remaining'] == 0:
                    o['status'] = 'sold'
        elif t == 'paid':
            c = claim_of(n, b)
            if c is not None:
                if m['by'] != c['buyer']:
                    ignore(n, 'not_buyer')
                else:
                    c['paid'] = {'method': b['method'], 'ref': b['ref']}
        elif t == 'received':
            c = claim_of(n, b)
            if c is not None:
                c['received'] = b['amount']
        elif t == 'delivered':
            c = claim_of(n, b)
            if c is not None:
                c['delivered'] = True
        elif t == 'confirmed':
            c = claim_of(n, b)
            if c is not None:
                if m['by'] != c['buyer']:
                    ignore(n, 'not_buyer')
                elif not c.get('delivered'):
                    ignore(n, 'not_delivered')
                else:
                    c['confirmed'] = True
        elif t == 'sent':
            if b['msg']['by'] != owner:
                ignore(n, 'not_my_message')
        elif t == 'receipt':
            if b['entry']['msg']['by'] != owner:
                ignore(n, 'not_my_message')
        if t in ('received', 'delivered', 'confirmed') and b['claim'] in claims:
            c = claims[b['claim']]
            if c['status'] == 'accepted' and 'received' in c and c.get('delivered') and c.get('confirmed'):
                c['status'] = 'closed'

    head = led.head()
    return {
        'ledger': led.id,
        'owner': owner,
        'devices': [],
        'head': head if head else {'seq': -1, 'id': led.id},
        'broken_at': led.broken_at,
        'admitted': sorted(admitted),
        'offers': offers,
        'claims': claims,
        'auctions': {},
        'disputes': {},
        'ignored': ignored,
    }


def allowed(allow, key, admitted):
    if allow == 'any':
        return True
    if allow == 'admitted':
        return key in admitted
    return key in allow

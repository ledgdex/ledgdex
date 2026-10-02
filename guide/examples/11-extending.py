"""Extending ledgdex: your own tools on the state, and your own pages in the dex. A ledgdex is a dex first: its
data.json holds your pages and the pages ledgdex generates from the ledger (those start with <!-- ledgdex -->).
ledgdex only ever rewrites its own pages, so anything you add stays."""
# expect: sales.csv
# expect: Mango Farm sales
# expect: your page kept: True
import contextlib, csv, io, json, os
from ledgdex.cli import main
from ledgdex.dex import load
from ledgdex.render import MARKER, render
from ledgdex.state import state


def ledgdex(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


# A shop with a few sales (as in the first trade example).
ledgdex('init', 'shop', '--name', 'Mango Farm', '--key', 'farm')
with open('offer.json', 'w') as f:
    json.dump({'item': {'title': 'Alphonso mangoes'}, 'quantity': 50, 'unit': 'dozen', 'currency': 'INR',
               'price': 120000}, f)
offer = ledgdex('offer', 'shop', 'offer.json').split()[-1]
for buyer, qty in (('asha', 2), ('ravi', 5), ('meena', 1)):
    ledgdex('init', buyer, '--name', buyer.title(), '--key', buyer)
    ledgdex('claim', buyer, 'shop', offer, '--quantity', qty, '--output', buyer + '.json')
    ledgdex('record', 'shop', '--from', buyer)

# 1. A tool on the state: a CSV of sales, from the verified ledger alone.
led = load('shop')
st = state(led)
with open('sales.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['claim', 'buyer', 'quantity', 'amount', 'status'])
    for cid, c in st['claims'].items():
        w.writerow([cid, c['buyer'], c['quantity'], c['quantity'] * c['price'], c['status']])
total = sum(c['quantity'] * c['price'] for c in st['claims'].values() if c['status'] != 'rejected')
print('sales.csv written:', len(st['claims']), 'claims, INR', total / 100)

# 2. A page of your own in the dex: add it to data.json like any dex page, then render.
with open('shop/data.json') as f:
    pages = json.load(f)
pages.append({'title': 'Sales report', 'body': [
    led.header['name'] + ' sales: ' + str(len(st['claims'])) + ' orders, INR ' + '{:,.2f}'.format(total / 100) + '.',
    'Every figure here is computed from the signed ledger: <a href="ledgdex.jsonl">ledgdex.jsonl</a>.']})
with open('shop/data.json', 'w') as f:
    json.dump(pages, f, indent=4, ensure_ascii=False)
render('shop')
print(open('shop/gen/salesreport.html').read().split('<p>')[1].split('</p>')[0])

# 3. ledgdex keeps it: more ledger entries rewrite only the generated pages.
ledgdex('note', 'shop', offer, 'restocked')
with open('shop/data.json') as f:
    kept = [p for p in json.load(f) if p['title'] == 'Sales report' and not p['body'][0].startswith(MARKER)]
print('your page kept:', len(kept) == 1, '| ledgdex pages:', sum(p['body'][0].startswith(MARKER) for p in pages))

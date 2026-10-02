# expect: sales.csv
# expect: Mango Farm sales
# expect: your page kept: True
import contextlib, csv, io, json, os
from ledgdex.cli import main
from ledgdex.dex import load
from ledgdex.render import MARKER, render
from ledgdex.state import state

# `ledgdex(...)` runs one ledgdex command in this program and returns what it printed.
def ledgdex(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


# A shop with three sales, made as in the first trade example.
ledgdex('init', 'shop', '--name', 'Mango Farm', '--key', 'farm')
with open('offer.json', 'w') as f:
    json.dump({'item': {'title': 'Alphonso mangoes'}, 'quantity': 50, 'unit': 'dozen', 'currency': 'INR',
               'price': 120000}, f)
offer = ledgdex('offer', 'shop', 'offer.json').split()[-1]
for buyer, qty in (('asha', 2), ('ravi', 5), ('meena', 1)):
    ledgdex('init', buyer, '--name', buyer.title(), '--key', buyer)
    ledgdex('claim', buyer, 'shop', offer, '--quantity', qty, '--output', buyer + '.json')
    ledgdex('record', 'shop', '--from', buyer)

# Your own tool: a spreadsheet (CSV) of sales, worked out from the verified ledger alone.
led = load('shop')
st = state(led)
with open('sales.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['claim', 'buyer', 'quantity', 'amount', 'status'])
    for cid, c in st['claims'].items():
        w.writerow([cid, c['buyer'], c['quantity'], c['quantity'] * c['price'], c['status']])
total = sum(c['quantity'] * c['price'] for c in st['claims'].values() if c['status'] != 'rejected')
print('sales.csv written:', len(st['claims']), 'claims, INR', total / 100)

# Your own page: a ledgdex is a dex, so add a page to `data.json` like any dex page, then render the site.
with open('shop/data.json') as f:
    pages = json.load(f)
pages.append({'title': 'Sales report', 'body': [
    led.header['name'] + ' sales: ' + str(len(st['claims'])) + ' orders, INR ' + '{:,.2f}'.format(total / 100) + '.',
    'Every figure here is computed from the signed ledger: <a href="ledgdex.jsonl">ledgdex.jsonl</a>.']})
with open('shop/data.json', 'w') as f:
    json.dump(pages, f, indent=4, ensure_ascii=False)
render('shop')
print(open('shop/gen/salesreport.html').read().split('<p>')[1].split('</p>')[0])

# A new ledger entry rewrites only the pages ledgdex made itself (they start with `<!-- ledgdex -->`). Your page stays.
ledgdex('note', 'shop', offer, 'restocked')
with open('shop/data.json') as f:
    kept = [p for p in json.load(f) if p['title'] == 'Sales report' and not p['body'][0].startswith(MARKER)]
print('your page kept:', len(kept) == 1, '| ledgdex pages:', sum(p['body'][0].startswith(MARKER) for p in pages))

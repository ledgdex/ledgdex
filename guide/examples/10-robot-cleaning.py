# expect: robot offline: hoover
# expect: day total
# expect: paid per clean: True
import contextlib, hashlib, io, json, os
from ledgdex.cli import main
HOME = os.environ.get('LEDGDEX_HOME') or os.path.join(os.path.expanduser('~'), '.ledgdex')

# `ledgdex(...)` runs one ledgdex command. `keys` picks the folder of keys to sign with: a robot's own, or by default its company's.
def ledgdex(*args, keys=None):
    os.environ['LEDGDEX_HOME'] = keys or HOME
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


def state(src):
    return json.loads(ledgdex('state', src))


# Two companies, one robot each. The company holds the main key; the robot gets its own device key and signs with it. Each robot offers today's 10 cleans at USD 4.00 each. Three shops join.
robots = {'roomba': 'CleanCo', 'hoover': 'Brightfloor'}
for robot, operator in robots.items():
    ledgdex('init', robot, '--name', robot.title() + ' (' + operator + ')', '--key', operator.lower())
    robot_keys = os.path.join(os.getcwd(), robot + '-keys')
    device = ledgdex('keygen', robot, keys=robot_keys).strip()
    ledgdex('device', 'add', robot, device, '--name', robot)
    with open(robot + '-offer.json', 'w') as f:
        json.dump({'item': {'title': 'Floor clean, 2026-10-01'}, 'quantity': 10, 'unit': 'clean',
                   'currency': 'USD', 'price': 400, 'expires': '2099-01-01T00:00:00Z'}, f)
    ledgdex('offer', robot, robot + '-offer.json', keys=robot_keys)
shops = ['bakery', 'pharmacy', 'bookshop']
for shop in shops:
    ledgdex('init', shop, '--name', shop.title(), '--key', shop)


# One clean: the shop orders it from the robot's open offer; the robot records the order, cleans, and records a photo as proof (its address and hash; here a made-up hash); the shop confirms.
def open_offer(robot):
    return next((i for i, o in state(robot)['offers'].items() if o['status'] == 'open' and o['remaining']), None)


def clean(shop, robot):
    keys = os.path.join(os.getcwd(), robot + '-keys')
    ledgdex('claim', shop, robot, open_offer(robot), '--output', shop + '-claim.json')
    claim = ledgdex('record', robot, '--from', shop, keys=keys).split('claim recorded: ')[1].split()[0]
    photo = hashlib.sha256((robot + claim).encode()).hexdigest()
    ledgdex('delivered', robot, claim, '--note', 'photo https://photos.example/' + photo + '.jpg sha256:' + photo,
            keys=keys)
    ledgdex('confirm', shop, robot, claim, '--output', shop + '-confirmed.json')
    ledgdex('record', robot, '--from', shop, keys=keys)
    return claim


# In the morning each shop gets a clean from each robot. At midday the hoover's battery fails, so it withdraws its offer; in the afternoon every shop uses the roomba.
done = [(shop, robot, clean(shop, robot)) for shop in shops for robot in robots]
ledgdex('withdraw', 'hoover', open_offer('hoover'), keys=os.path.join(os.getcwd(), 'hoover-keys'))
print('robot offline: hoover; open offers:', {r: open_offer(r) is not None for r in robots})
done += [(shop, 'roomba', clean(shop, 'roomba')) for shop in shops]

# In the evening each shop pays for each of the day's cleans, and each robot records the money it received.
for shop, robot, claim in done:
    ledgdex('pay', shop, robot, claim, '--method', 'card', '--ref', 'DAY-2026-10-01', '--output', shop + '-paid.json')
for robot in robots:
    keys = os.path.join(os.getcwd(), robot + '-keys')
    ledgdex('record', robot, *[x for s in shops for x in ('--from', s)], keys=keys)
    for cid, c in state(robot)['claims'].items():
        if 'paid' in c and 'received' not in c:
            ledgdex('received', robot, cid, c['price'], keys=keys)

# The day's report, worked out from the ledgers alone, so anyone can check it.
for robot in robots:
    claims = state(robot)['claims'].values()
    print(robot, 'day total: USD', sum(c['price'] for c in claims if c['status'] == 'closed') / 100,
          'for', sum(c['status'] == 'closed' for c in claims), 'cleans')
print('paid per clean:', all(c['status'] == 'closed' for r in robots for c in state(r)['claims'].values()))

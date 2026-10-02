"""Robots paid per clean (spec section 10, with the features built today). Two operators' robots each offer the
day's cleans; shops on the floor claim a clean when they need one; the robot records the clean with its photo as
evidence; shops confirm and pay for the day's cleans. One robot goes offline mid-day: it withdraws its offer and the
shops claim from the other robot. Each robot signs with its own device key; its operator keeps the owner key."""
# expect: robot offline: hoover
# expect: day total
# expect: paid per clean: True
import contextlib, hashlib, io, json, os
from ledgdex.cli import main
HOME = os.environ.get('LEDGDEX_HOME') or os.path.join(os.path.expanduser('~'), '.ledgdex')


def ledgdex(*args, keys=None):
    """One ledgdex command. keys: the key store to sign from (a robot's own, or an operator's)."""
    os.environ['LEDGDEX_HOME'] = keys or HOME
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        main([str(a) for a in args])
    return out.getvalue()


def state(src):
    return json.loads(ledgdex('state', src))


# Two operators, one robot each. The robot gets a device key; the operator's owner key never leaves the operator.
robots = {'roomba': 'CleanCo', 'hoover': 'Brightfloor'}
for robot, operator in robots.items():
    ledgdex('init', robot, '--name', robot.title() + ' (' + operator + ')', '--key', operator.lower())
    robot_keys = os.path.join(os.getcwd(), robot + '-keys')
    device = ledgdex('keygen', robot, keys=robot_keys).strip()
    ledgdex('device', 'add', robot, device, '--name', robot)
    with open(robot + '-offer.json', 'w') as f:      # today's cleans: 10 at USD 4.00 each, until midnight
        json.dump({'item': {'title': 'Floor clean, 2026-10-01'}, 'quantity': 10, 'unit': 'clean',
                   'currency': 'USD', 'price': 400, 'expires': '2099-01-01T00:00:00Z'}, f)
    ledgdex('offer', robot, robot + '-offer.json', keys=robot_keys)
shops = ['bakery', 'pharmacy', 'bookshop']
for shop in shops:
    ledgdex('init', shop, '--name', shop.title(), '--key', shop)


def open_offer(robot):
    return next((i for i, o in state(robot)['offers'].items() if o['status'] == 'open' and o['remaining']), None)


def clean(shop, robot):
    """The shop claims one clean; the robot records it, cleans, and records the photo as evidence."""
    keys = os.path.join(os.getcwd(), robot + '-keys')
    ledgdex('claim', shop, robot, open_offer(robot), '--output', shop + '-claim.json')
    claim = ledgdex('record', robot, '--from', shop, keys=keys).split('claim recorded: ')[1].split()[0]
    photo = hashlib.sha256((robot + claim).encode()).hexdigest()          # stands in for the photo's real hash
    ledgdex('delivered', robot, claim, '--note', 'photo https://photos.example/' + photo + '.jpg sha256:' + photo,
            keys=keys)
    ledgdex('confirm', shop, robot, claim, '--output', shop + '-confirmed.json')
    ledgdex('record', robot, '--from', shop, keys=keys)
    return claim


# Morning: the shops spread their cleans over both robots. Midday the hoover's battery fails: it withdraws its offer.
done = [(shop, robot, clean(shop, robot)) for shop in shops for robot in robots]
ledgdex('withdraw', 'hoover', open_offer('hoover'), keys=os.path.join(os.getcwd(), 'hoover-keys'))
print('robot offline: hoover; open offers:', {r: open_offer(r) is not None for r in robots})
done += [(shop, 'roomba', clean(shop, 'roomba')) for shop in shops]  # afternoon: everyone uses the roomba

# Evening: each shop pays each robot for the day's confirmed cleans, and each robot records the money.
for shop, robot, claim in done:
    ledgdex('pay', shop, robot, claim, '--method', 'card', '--ref', 'DAY-2026-10-01', '--output', shop + '-paid.json')
for robot in robots:
    keys = os.path.join(os.getcwd(), robot + '-keys')
    ledgdex('record', robot, *[x for s in shops for x in ('--from', s)], keys=keys)
    for cid, c in state(robot)['claims'].items():
        if 'paid' in c and 'received' not in c:
            ledgdex('received', robot, cid, c['price'], keys=keys)

# The day's report, from the ledgers alone: anyone can recompute it.
for robot in robots:
    claims = state(robot)['claims'].values()
    print(robot, 'day total: USD', sum(c['price'] for c in claims if c['status'] == 'closed') / 100,
          'for', sum(c['status'] == 'closed' for c in claims), 'cleans')
print('paid per clean:', all(c['status'] == 'closed' for r in robots for c in state(r)['claims'].values()))

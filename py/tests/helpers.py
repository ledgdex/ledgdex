import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledgdex.core import message, new_ledger, public  # noqa: E402
from ledgdex.canon import hash_  # noqa: E402

SELLER = bytes(range(32))
BUYER = bytes(range(1, 33))
OTHER = bytes(range(2, 34))
T0 = '2026-10-01T09:00:00Z'


def t(minutes):
    return '2026-10-01T%02d:%02d:00Z' % (9 + minutes // 60, minutes % 60)


def offer_body(**kw):
    b = {'item': {'title': 'Mangoes', 'text': 'ripe', 'media': []}, 'quantity': 2, 'unit': 'dozen',
         'currency': 'INR', 'price': 120000, 'allow': 'any', 'pay': [{'method': 'upi', 'to': 'farm@bank'}],
         'arbiter': {'key': public(SELLER), 'url': ''}, 'terms': ''}
    b.update(kw)
    return b


class Book:
    """A seller ledger built step by step with a fixed clock."""

    def __init__(self, secret=SELLER, name='Farm'):
        self.secret = secret
        self.led = new_ledger(secret, name, 'about', 'https://farm.example', at=T0)
        self.minute = 0

    def tick(self):
        self.minute += 1
        return t(self.minute)

    def own(self, type_, body):
        at = self.tick()
        return self.led.append(self.led.next_entry(self.secret, message(self.secret, type_, body, at=at), at=at))

    def rec(self, msg):
        return self.led.append(self.led.next_entry(self.secret, msg, at=self.tick()))

    def from_(self, secret, type_, body):
        return self.rec(message(secret, type_, body, at=t(self.minute)))

    def offer(self, **kw):
        oid = self.own('offer', offer_body(**kw))
        return oid, hash_(self.led.entries[self.led.find(oid)]['msg'])

    def claim(self, oid, ohash, secret=BUYER, quantity=1, price=120000):
        return self.from_(secret, 'claim', {'offer': oid, 'offer_hash': ohash, 'quantity': quantity, 'price': price})

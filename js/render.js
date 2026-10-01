// Every ledgdex is a dex (spec 7.2): the generated dex pages for a ledger. Mirrors py/ledgdex/render.py pages(),
// byte for byte (checked against vectors/pages.json).
import { hash } from './canon.js';
import { state } from './state.js';

export const MARKER = '<!-- ledgdex -->';
export const LEDGER = 'ledgdex.jsonl';
const DIGITS = { INR: 2, USD: 2, EUR: 2, GBP: 2, AUD: 2, CAD: 2, SGD: 2, AED: 2, CHF: 2, CNY: 2, JPY: 0, KRW: 0, BTC: 8 };
// Python's str.split() whitespace, and str.isalnum()
const SPACE = /[\t\n\x0b\x0c\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u;
const ALNUM = /[\p{L}\p{N}]/u;

/** Python's html.escape(s, quote=True), then newlines as <br>. */
export const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[c]))
  .replace(/\n/g, '<br>');
const group = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

/** INR 20,000.00 (2000000). Currencies without known minor units are written as the integer. */
export function amount(currency, n) {
  const k = DIGITS[currency];
  if (k === undefined) return esc(currency) + ' ' + (n < 0 ? '-' : '') + group(Math.abs(n));
  const a = Math.abs(n), unit = 10 ** k;
  return esc(currency) + ' ' + (n < 0 ? '-' : '') + group(Math.floor(a / unit)) +
    (k ? '.' + String(a % unit).padStart(k, '0') : '') + ' (' + n + ')';
}
export const short = (s) => s.split(':')[0] + ':' + s.split(':')[1].slice(0, 12);
export const code = (s) => '<code>' + esc(s) + '</code>';
/** dexweb names each page file after its title: letters and digits only, lowercase. */
export const htmlTitle = (t) => [...t].filter((c) => ALNUM.test(c)).join('').toLowerCase();
const link = (title) => "<a href='" + htmlTitle(title) + ".html'>" + title + '</a>';
const ref = (label, key) => (b) => label + code(short(b[key]));

const SUMMARY = {
  open: () => 'opened the ledger',
  offer: (b) => esc(b.item.title) + ', ' + b.quantity + ' ' + esc(b.unit) + ' at ' + amount(b.currency, b.price) + ' each',
  withdraw: ref('offer ', 'offer'),
  claim: (b) => b.quantity + ' of offer ' + code(short(b.offer)),
  paid: (b) => 'claim ' + code(short(b.claim)) + ' by ' + esc(b.method),
  received: (b) => 'claim ' + code(short(b.claim)) + ' amount ' + b.amount,
  delivered: ref('claim ', 'claim'),
  confirmed: ref('claim ', 'claim'),
  admit: ref('', 'key'),
  revoke: ref('', 'key'),
  note: (b) => 'about ' + code(short(b.ref)) + ': ' + esc(b.text),
  sent: (b) => esc(b.msg.type) + ' to ' + code(short(b.to)),
  rotate: ref('', 'key'),
  device: (b) => code(short(b.key)) + (b.name ? ' (' + esc(b.name) + ')' : ''),
  device_revoke: ref('', 'key'),
  recovered: ref('owner key recovered through the root, entry ', 'entry'),
  recover: (b) => 'new key ' + code(short(b.key)) + ' for ledger ' + code(short(b.ledger)),
  dispute: (b) => 'about ' + code(short(b.claim)) + (b.text ? ': ' + esc(b.text) : ''),
  ruling: (b) => b.outcome + ' on dispute ' + code(short(b.dispute)),
  auction: (b) => esc(b.item.title) + ', bids until ' + b.close,
  bid: ref('auction ', 'auction'),
  reveal: (b) => 'auction ' + code(short(b.auction)) + ' amount ' + b.amount,
  list: (b) => 'ledger ' + code(short(b.ledger)) + ' ' + esc(b.url),
  delist: ref('ledger ', 'ledger'),
  receipt: (b) => 'entry ' + b.entry.seq + ' (' + esc(b.entry.msg.type) + ') of ' + esc(b.header.name) + "'s ledger",
};

const itemLines = (item) => (item.text ? [esc(item.text)] : []).concat(item.media.map((md) =>
  "Media: <a href='" + esc(md.url) + "'>" + esc(md.url) + '</a> ' + code(md.hash)));
const flags = (c) => {
  const f = ['paid', 'received', 'delivered', 'confirmed'].filter((k) => k in c);
  return f.length ? ', ' + f.join(', ') : '';
};

/** The generated pages (spec 7.2) for a whole ledger, as dex page objects. */
export function pages(led, authorTitles = []) {
  const st = state(led), name = led.header.name;
  const taken = new Set(authorTitles.map(htmlTitle).concat(['index'])), own = new Set(taken);
  function titleFor(t, id) {
    t = esc(t.split(SPACE).filter((x) => x).join(' '));  // dexweb writes titles into the page as they are
    if (!htmlTitle(t)) t = 'Offer ' + (id || '').slice(7, 15);
    if (own.has(htmlTitle(t))) t += ' (ledgdex)';
    if (taken.has(htmlTitle(t)) && id) t += ' ' + id.slice(7, 15);
    taken.add(htmlTitle(t));
    return t;
  }
  const of = (type) => led.entries.map((e, n) => [led.ids[n], e.msg]).filter(([, m]) => m.type === type);
  const ledgerTitle = titleFor(name + ' ledger');
  const offers = of('offer'), auctions = of('auction');
  const offerTitles = {}, auctionTitles = {};
  offers.forEach(([id, m]) => { offerTitles[id] = titleFor(m.body.item.title, id); });
  auctions.forEach(([id, m]) => { auctionTitles[id] = titleFor(m.body.item.title, id); });
  const listingsTitle = Object.keys(st.listings).length ? titleFor(name + ' listings') : null;
  const sentClaims = led.entries.filter((e) => e.msg.type === 'sent' && e.msg.body.msg.type === 'claim');
  const purchasesTitle = sentClaims.length ? titleFor(name + ' purchases') : null;
  const admits = led.entries.filter((e) => e.msg.type === 'admit' || e.msg.type === 'revoke');
  const admissionsTitle = admits.length ? titleFor(name + ' admissions') : null;
  const about = led.entries.length ? led.entries[0].msg.body.about : '';
  const dex = led.dex || 'THIS_DEX';
  const verdict = led.whole ? 'whole' : 'broken at seq ' + led.broken_at;
  const out = [];

  // 1. the ledger
  const head = led.head();
  let body = [MARKER + esc(name) + "'s ledger: " + led.entries.length + ' entries, ' + verdict,
    'Owner key: ' + code(led.owner),
    'Device keys: ' + (st.devices.length ? st.devices.map(code).join(', ') : 'none'),
    'Ledger id: ' + code(led.id),
    'Head: ' + (head ? 'seq ' + head.seq + ', ' + code(head.id) : 'none'),
    'Verification: ' + verdict,
    "Download the ledger: <a href='" + LEDGER + "'>" + LEDGER + '</a>'];
  if (about) body.splice(1, 0, esc(about));
  const links = offers.map(([id]) => link(offerTitles[id])).concat(auctions.map(([id]) => link(auctionTitles[id])),
    [purchasesTitle, admissionsTitle, listingsTitle].filter((t) => t).map(link));
  if (links.length) body.push('Pages: ' + links.join(', '));
  body.push('Entries:');
  led.entries.forEach((e, n) => body.push(n + '. ' + e.time + ' ' + esc(e.msg.type) + ' by ' + code(short(e.msg.by)) +
    ': ' + SUMMARY[e.msg.type](e.msg.body) + ' ' + code(short(led.ids[n]))));
  out.push({ title: ledgerTitle, body });

  // 2. one page per offer
  for (const [id, m] of offers) {
    const b = m.body, o = st.offers[id], cur = b.currency;
    body = [MARKER + amount(cur, b.price) + ' per ' + esc(b.unit) + ', ' + o.remaining + ' of ' + b.quantity + ' left, ' +
      o.status, ...itemLines(b.item), 'Status: ' + o.status,
    'Remaining: ' + o.remaining + ' of ' + b.quantity + ' ' + esc(b.unit), 'Price: ' + amount(cur, b.price) + ' per ' + esc(b.unit)];
    if ('expires' in b) body.push('Expires: ' + b.expires);
    for (const p of b.pay) body.push('Pay by ' + esc(p.method) + ': ' + esc(p.to));
    body.push('Arbiter: ' + code(b.arbiter.key) + (b.arbiter.url ? ' ' + esc(b.arbiter.url) : ''));
    if (b.terms) body.push('Terms: ' + esc(b.terms));
    body.push('Who may buy: ' + (b.allow === 'any' ? 'anyone' : b.allow === 'admitted' ? 'keys admitted by this ledger'
      : b.allow.map(code).join(', ')));
    body.push('Offer id: ' + code(id), 'Offer hash: ' + code(hash(m)),
      'To buy, with your own ledgdex: ' + code('ledgdex claim YOUR_DEX ' + dex + ' ' + id + ' --quantity 1'),
      'Then send the claim file to the seller, or publish your dex: the seller collects claims with ' +
      code('ledgdex record DEX --from YOUR_DEX_URL') + '.');
    const mine = Object.entries(st.claims).filter(([, c]) => c.offer === id);
    if (mine.length) {
      body.push('Claims:');
      for (const [cid, c] of mine) {
        body.push(code(short(cid)) + ' by ' + code(short(c.buyer)) + ': ' + c.quantity + ' at ' + amount(cur, c.price) + ', ' +
          c.status + ('reason' in c ? ' (' + c.reason + ')' : '') + flags(c));
      }
    }
    out.push({ title: offerTitles[id], body });
  }

  // 2b. one page per auction
  for (const [id, m] of auctions) {
    const b = m.body, a = st.auctions[id];
    body = [MARKER + a.status + ', ' + a.bids + ' sealed bids', ...itemLines(b.item), 'Status: ' + a.status,
      'Bids close: ' + b.close, 'Reveals until: ' + b.reveal_until,
      'Best bid: ' + b.best + ', reserve ' + amount(b.currency, b.reserve), 'Arbiter: ' + code(b.arbiter.key)];
    if (b.terms) body.push('Terms: ' + esc(b.terms));
    if ('winner' in a) body.push('Winner: ' + code(a.winner) + ' at ' + amount(b.currency, a.amount));
    body.push('Auction id: ' + code(id), 'To bid, with your own ledgdex: ' + code('ledgdex bid YOUR_DEX ' + dex + ' ' + id +
      ' --amount N') + '. After the close, reveal it with ' + code('ledgdex reveal YOUR_DEX ' + dex + ' ' + id) + '.');
    out.push({ title: auctionTitles[id], body });
  }

  // 3. purchases: claims this self sent, and the receipts it holds for them
  if (purchasesTitle) {
    const receipts = {};
    for (const e of led.entries) {
      if (e.msg.type === 'receipt') receipts[hash(e.msg.body.entry.msg)] = [e.msg.body, hash(e.msg.body.entry)];
    }
    body = [MARKER + sentClaims.length + ' claims sent'];
    for (const e of sentClaims) {
      const s = e.msg.body, c = s.msg, got = receipts[hash(c)];
      body.push(e.time + ': ' + c.body.quantity + ' of offer ' + code(short(c.body.offer)) + ' from ' + code(short(s.to)) +
        ' at ' + c.body.price + ' each. ' + (got ? 'Receipt: entry ' + got[0].entry.seq + ' of ' + esc(got[0].header.name) +
          "'s ledger, claim id " + code(got[1]) : 'No receipt yet.'));
    }
    out.push({ title: purchasesTitle, body });
  }

  // 3b. listings (an index)
  if (listingsTitle) {
    body = [MARKER + Object.keys(st.listings).length + ' ledgers listed'];
    for (const [lid, l] of Object.entries(st.listings)) {
      body.push("<a href='" + esc(l.url) + "'>" + esc(l.url) + '</a> ledger ' + code(lid) + ', owner ' + code(l.owner) +
        (l.note ? ': ' + esc(l.note) : ''));
    }
    out.push({ title: listingsTitle, body });
  }

  // 4. admissions
  if (admissionsTitle) {
    body = [MARKER + st.admitted.length + ' keys admitted'];
    for (const e of admits) {
      const b = e.msg.body;
      body.push(e.time + ' ' + e.msg.type + ' ' + code(b.key) + ': ' + esc(b.name !== undefined ? b.name : b.reason || '') +
        (b.note ? ' ' + esc(b.note) : ''));
    }
    out.push({ title: admissionsTitle, body });
  }
  return out;
}

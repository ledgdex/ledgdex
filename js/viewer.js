// The viewer (viewer.html): read and verify any ledger, keep your own, sign messages. Nothing leaves the browser.
import { Ledger, message, publicKey, Invalid, newSecret, newLedger, KEY_TYPES } from './core.js';
import { state } from './state.js';
import { canonString, hash } from './canon.js';
import { hex, unhex } from './sha.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const short = (s) => esc(s.split(':')[0] + ':' + s.split(':')[1].slice(0, 12));
const code = (s) => '<code>' + esc(s) + '</code>';
const store = {  // browser storage can be missing (private windows): then things last for this page only
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* this page only */ } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* nothing stored */ } },
};
const enc = new TextEncoder(), dec = new TextDecoder();
let led = null, st = null, own = null, secret = null, lastMsg = null, loadedFrom = '';

function fail(e) { $('err').textContent = e.message || String(e); }
const ledgerURL = (u) => (u = u.trim()).endsWith('.jsonl') ? u : u.replace(/\/+$/, '') + '/ledgdex.jsonl';
async function fetchBytes(u) {
  const r = await fetch(ledgerURL(u), { cache: 'no-store' });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + ledgerURL(u));
  return new Uint8Array(await r.arrayBuffer());
}
const rootLedger = async () => $('rooturl').value.trim() ? new Ledger(await fetchBytes($('rooturl').value)) : null;
function money(cur, n) {
  const d = { INR: 2, USD: 2, EUR: 2, GBP: 2, JPY: 0, BTC: 8 }[cur];
  if (d === undefined) return esc(cur) + ' ' + n.toLocaleString('en');
  const a = Math.abs(n), minor = a % 10 ** d;
  return esc(cur) + ' ' + (n < 0 ? '-' : '') + Math.floor(a / 10 ** d).toLocaleString('en') +
    (d ? '.' + String(minor).padStart(d, '0') : '');
}
const table = (heads, rows) => '<div class="scroll"><table><tr>' + heads.map((h) => '<th>' + h + '</th>').join('') +
  '</tr>' + rows.map((r) => '<tr>' + r.map((c) => '<td>' + c + '</td>').join('') + '</tr>').join('') + '</table></div>';

// ---------- the ledger you look at ----------

function show(data, root) {
  const t0 = performance.now();
  led = new Ledger(data, root);
  st = led.header ? state(led, root) : null;
  const ms = Math.round(performance.now() - t0), r = $('result');
  buildForm();
  if (!led.header) { r.innerHTML = '<p class="status bad">Not a ledger: ' + esc(led.error) + '</p>'; return; }
  const open = led.entries[0] ? led.entries[0].msg.body : { about: '', dex: '' };
  let h = '<p>' + (led.whole ? '<span class="status ok">Whole</span>: every hash and signature checks out'
    : '<span class="status bad">Broken at seq ' + led.broken_at + '</span>: ' + esc(led.error)) +
    ' <span class="dim">(' + led.entries.length + ' entries checked in ' + ms + ' ms)</span></p>' +
    '<p><b>' + esc(led.header.name) + '</b>' + (open.about ? ': ' + esc(open.about) : '') +
    (open.dex ? ' · <a href="' + esc(open.dex) + '">dex</a>' : '') + '</p>' +
    '<p class="dim">Ledger id ' + code(led.id) + '<br>Owner key ' + code(st.owner) +
    (st.devices.length ? '<br>Device keys ' + st.devices.map(code).join(' ') : '') + '</p>';
  const offers = led.entries.map((e, n) => [led.ids[n], e.msg.body]).filter(([id]) => id in st.offers);
  if (offers.length) {
    h += '<h2>Offers</h2>' + table(['Item', 'Price', 'Left', 'Status', 'Offer id'], offers.map(([id, b]) =>
      [esc(b.item.title), money(b.currency, b.price) + ' / ' + esc(b.unit), st.offers[id].remaining + ' of ' + b.quantity,
        st.offers[id].status, '<code>' + short(id) + '</code>']));
  }
  const claims = Object.entries(st.claims);
  if (claims.length) {
    h += '<h2>Claims</h2>' + table(['Claim id', 'Buyer', 'Qty', 'Status'], claims.map(([id, c]) => {
      const flags = ['paid', 'received', 'delivered', 'confirmed'].filter((k) => k in c).join(', ');
      return ['<code>' + short(id) + '</code>', '<code>' + short(c.buyer) + '</code>', c.quantity,
        c.status + (c.reason ? ' (' + c.reason + ')' : '') + (flags ? '<br><span class="dim">' + flags + '</span>' : '')];
    }));
  }
  const auctions = Object.entries(st.auctions);
  if (auctions.length) {
    h += '<h2>Auctions</h2>' + table(['Item', 'Status', 'Bids', 'Close', 'Winner'], auctions.map(([id, a]) => {
      const b = led.entries[led.find(id)].msg.body;
      return [esc(b.item.title) + '<br><code>' + short(id) + '</code>', a.status, a.bids,
        esc(b.close) + '<br><span class="dim">reveal by ' + esc(b.reveal_until) + '</span>',
        a.winner ? '<code>' + short(a.winner) + '</code> ' + money(b.currency, a.amount) : ''];
    }));
  }
  const listings = Object.entries(st.listings);
  if (listings.length) {
    h += '<h2>Listed ledgers</h2><ul>' + listings.map(([id, l]) => '<li><a href="#" data-load="' + esc(l.url) + '">' +
      esc(l.url) + '</a> <code>' + short(id) + '</code>' + (l.note ? ' ' + esc(l.note) : '') + '</li>').join('') + '</ul>';
  }
  if (st.ignored.length) {
    h += '<h2>Ignored entries</h2><p class="dim">' + st.ignored.map((i) => 'seq ' + i.seq + ': ' + i.reason).join(' · ') + '</p>';
  }
  h += '<h2>Entries</h2>' + table(['Seq', 'Time', 'Type', 'By', 'Entry id'], led.entries.map((e, n) =>
    [n, esc(e.time), esc(e.msg.type), '<code>' + short(e.msg.by) + '</code>', '<code>' + short(led.ids[n]) + '</code>']));
  r.innerHTML = h;
  r.querySelectorAll('[data-load]').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); $('url').value = a.dataset.load; load();
  }));
  showOwn();
}

async function load() {
  $('err').textContent = '';
  try {
    loadedFrom = $('url').value.trim();
    show(await fetchBytes(loadedFrom), await rootLedger());
  } catch (e) {
    $('result').innerHTML = '<p class="status bad">' + esc(e.message) +
      '</p><p class="dim">The site must allow cross-origin reads (GitHub Pages does), or download the file and open it here.</p>';
  }
}

// ---------- your key ----------

function setKey(s) {
  secret = s;
  $('pub').textContent = s ? publicKey(s) : 'none';
  if (s) store.set('ledgdex-secret', hex(s)); else store.del('ledgdex-secret');
  showOwn();
}

// ---------- your ledger ----------

function setOwn(l) {
  own = l;
  if (l) store.set('ledgdex-own', dec.decode(l.data)); else store.del('ledgdex-own');
  showOwn();
}
const mineKey = () => own && secret && own.keys.signing().includes(publicKey(secret));
function showOwn() {
  const o = $('own');
  ['ownsave', 'receipts'].forEach((id) => $(id).classList.toggle('hidden', !own));
  if (!own) { o.innerHTML = '<p class="dim">No ledger of yours open.</p>'; return; }
  const sent = own.entries.filter((e) => e.msg.type === 'sent').length;
  const receipts = own.entries.filter((e) => e.msg.type === 'receipt').length;
  o.innerHTML = '<p><b>' + esc(own.header.name) + '</b>: ' + own.entries.length + ' entries, ' +
    (own.whole ? 'whole' : '<span class="bad">broken at seq ' + own.broken_at + '</span>') + '; ' + sent + ' sent, ' +
    receipts + ' receipts</p><p class="dim">Ledger id ' + code(own.id) + '<br>Owner key ' + code(own.owner) + '</p>' +
    (secret && !mineKey() ? '<p class="status bad">Your key is not a signing key of this ledger.</p>' : '');
}
function append(m) {
  own.append(own.nextEntry(secret, m));
  setOwn(own);
}

function collectReceipts() {
  $('err').textContent = '';
  try {
    if (!own || !mineKey()) throw new Invalid('open your ledger and use its key first');
    if (!led || !led.whole) throw new Invalid('load the seller\'s ledger below first');
    const held = new Set(own.entries.filter((e) => e.msg.type === 'receipt').map((e) => hash(e.msg.body.entry)));
    const mine = new Set(own.entries.filter((e) => e.msg.type === 'sent').map((e) => hash(e.msg.body.msg)));
    const chain = led.entries.filter((e) => KEY_TYPES.has(e.msg.type));
    const url = (led.entries[0] && led.entries[0].msg.body.dex) || loadedFrom;
    let n = 0;
    led.entries.forEach((e, i) => {
      if (!mine.has(hash(e.msg)) || held.has(led.ids[i])) return;
      const body = { ledger: led.id, url, header: led.header, entry: e };
      const keys = chain.filter((k) => k.seq < e.seq);
      if (keys.length) body.keys = keys;
      append(message(secret, 'receipt', body));
      n++;
    });
    $('err').textContent = '';
    $('own').insertAdjacentHTML('beforeend', '<p class="status ok">' + n + ' new receipts kept.</p>');
  } catch (e) { fail(e); }
}

// ---------- signing ----------

const pick = (id, options, label) => '<label for="' + id + '">' + label + '</label><select id="' + id + '">' +
  (options.length ? options.map(([v, t]) => '<option value="' + esc(v) + '">' + esc(t) + '</option>').join('')
    : '<option value="">(none in this ledger)</option>') + '</select>';
const field = (id, label, value = '', type = 'text') =>
  '<label for="' + id + '">' + label + '</label><input id="' + id + '" type="' + type + '" value="' + esc(value) + '">';

function buildForm() {
  const t = $('type').value, f = $('form');
  const offers = st ? Object.entries(st.offers).filter(([, o]) => o.status === 'open').map(([id, o]) => [id, o.title + ' (' + o.remaining + ' left)']) : [];
  const claims = st ? Object.entries(st.claims).filter(([, c]) => c.status !== 'rejected').map(([id, c]) => [id, short(id) + ' ' + c.status])
    .concat(Object.entries(st.auctions).filter(([, a]) => a.winner).map(([id, a]) => [id, 'auction ' + short(id) + ' ' + a.status])) : [];
  const auctions = st ? Object.entries(st.auctions).map(([id, a]) => [id, led.entries[led.find(id)].msg.body.item.title + ' (' + a.status + ')']) : [];
  f.innerHTML = {
    claim: () => pick('f-offer', offers, 'Offer') + field('f-qty', 'Quantity', '1', 'number'),
    paid: () => pick('f-claim', claims, 'Claim') + field('f-method', 'Method', 'upi') + field('f-ref', 'Reference'),
    confirmed: () => pick('f-claim', claims, 'Claim'),
    dispute: () => pick('f-claim', claims, 'Claim') + field('f-text', 'What went wrong'),
    bid: () => pick('f-auction', auctions, 'Auction') + field('f-amount', 'Amount (smallest unit, kept secret until you reveal)', '', 'number'),
    reveal: () => pick('f-auction', auctions, 'Auction') + '<p class="dim">Uses the amount and nonce this browser saved when you bid.</p>',
  }[t]();
}

function body() {
  const t = $('type').value, v = (id) => $(id) ? $(id).value : '';
  if (!led || !led.whole) throw new Invalid('load a whole ledger first');
  if (t === 'claim') {
    const id = v('f-offer');
    if (!id) throw new Invalid('choose an offer');
    const m = led.entries[led.find(id)].msg;
    return { offer: id, offer_hash: hash(m), quantity: parseInt(v('f-qty'), 10), price: m.body.price };
  }
  if (t === 'paid') return { claim: v('f-claim'), method: v('f-method'), ref: v('f-ref') };
  if (t === 'confirmed') return { claim: v('f-claim') };
  if (t === 'dispute') return { claim: v('f-claim'), text: v('f-text'), evidence: [] };
  const auction = v('f-auction'), slot = 'ledgdex-bid-' + publicKey(secret) + '-' + auction;
  if (t === 'bid') {
    const amount = parseInt(v('f-amount'), 10);
    if (!(amount >= 0)) throw new Invalid('enter the amount');
    if (store.get(slot)) throw new Invalid('this key already bid in this auction (one bid per key)');
    const nonce = hex(crypto.getRandomValues(new Uint8Array(32)));
    store.set(slot, JSON.stringify({ amount, nonce }));
    return { auction, commit: hash({ amount, nonce }) };
  }
  const saved = JSON.parse(store.get(slot) || 'null');
  if (!saved) throw new Invalid('this browser has no bid of this key for that auction');
  return { auction, amount: saved.amount, nonce: saved.nonce };
}

function signIt() {
  $('err').textContent = '';
  try {
    if (!secret) throw new Invalid('make or paste a key first');
    if (own && own.owner !== publicKey(secret)) throw new Invalid('sign with your ledger\'s owner key: it is who you are in other ledgers');
    if (own && led && led.id === own.id) throw new Invalid('this is your own ledger');
    lastMsg = message(secret, $('type').value, body());
    if (own) append(message(secret, 'sent', { to: led.owner, msg: lastMsg }));
    $('signed').textContent = 'Signed' + (own ? ' and kept as "sent" in your ledger. Download your ledger and publish it: the seller collects' +
      ' it from your dex. Or send this file' : '. Send this file to the ledger owner') + '.';
    $('msg').textContent = canonString(lastMsg);
    $('out').classList.remove('hidden');
  } catch (e) {
    fail(e);
    $('out').classList.add('hidden');
  }
}

function download(text, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  a.download = name;
  a.click();
}

// ---------- wiring ----------

$('gen').onclick = () => setKey(newSecret());
$('import').onclick = () => {
  const v = $('secret').value.trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(v)) return fail(new Error('A secret key is 64 hex characters.'));
  $('secret').value = ''; $('err').textContent = ''; setKey(unhex(v));
};
$('forget').onclick = () => setKey(null);
$('newledger').onclick = () => {
  try {
    if (!secret) throw new Invalid('make or paste a key first');
    if (!$('newname').value.trim()) throw new Invalid('give your ledger a name');
    setOwn(newLedger(secret, $('newname').value.trim(), $('newabout').value, $('newdex').value.trim()));
  } catch (e) { fail(e); }
};
$('ownload').onclick = async () => {
  try { setOwn(new Ledger(await fetchBytes($('ownurl').value), await rootLedger())); } catch (e) { fail(e); }
};
$('ownfile').onchange = async () => {
  const f = $('ownfile').files[0];
  if (f) setOwn(new Ledger(new Uint8Array(await f.arrayBuffer()), await rootLedger().catch(() => null)));
};
$('ownsave').onclick = () => download(dec.decode(own.data), 'ledgdex.jsonl');
$('receipts').onclick = collectReceipts;
$('type').onchange = buildForm;
$('signit').onclick = signIt;
$('download').onclick = () => download(canonString(lastMsg) + '\n', lastMsg.type + '-' + hash(lastMsg).slice(7, 19) + '.json');
$('copy').onclick = () => navigator.clipboard.writeText(canonString(lastMsg));
$('load').onclick = load;
$('url').addEventListener('keydown', (e) => { if (e.key === 'Enter') load(); });
$('file').onchange = async () => {
  const f = $('file').files[0];
  if (f) { loadedFrom = ''; show(new Uint8Array(await f.arrayBuffer()), await rootLedger().catch(() => null)); }
};

const saved = store.get('ledgdex-secret');
if (saved && /^[0-9a-f]{64}$/.test(saved)) setKey(unhex(saved));
const ownText = store.get('ledgdex-own');
if (ownText) { const l = new Ledger(enc.encode(ownText)); if (l.header) setOwn(l); }
const q = new URLSearchParams(location.search);
if (q.get('ledger')) { $('url').value = q.get('ledger'); if (q.get('root')) $('rooturl').value = q.get('root'); load(); }
buildForm();
showOwn();

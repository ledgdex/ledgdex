// The viewer dex's page script (viewer/, built with dexweb): read and verify any ledger, keep your own, sign messages,
// and download your ledger as a complete dex. Nothing leaves the browser. Writes plain elements, no classes.
import { Ledger, message, publicKey, Invalid, newSecret, newLedger, KEY_TYPES } from './core.js';
import { state } from './state.js';
import { canonString, hash } from './canon.js';
import { hex, unhex } from './sha.js';
import { pages, htmlTitle, short, LEDGER } from './render.js';
import { makeDex } from './dexweb.js';
import { zip } from './zip.js';

const $ = (id) => document.getElementById(id);
const store = {  // browser storage can be missing (private windows): then things last for this page only
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* this page only */ } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* nothing stored */ } },
};
const enc = new TextEncoder(), dec = new TextDecoder();
let led = null, st = null, own = null, secret = null, lastMsg = null, loadedFrom = '', shown = [];

const say = (id, text) => { $(id).textContent = text; };
const fail = (e) => say('err', e.message || String(e));
const ledgerURL = (u) => (u = u.trim()).endsWith('.jsonl') ? u : u.replace(/\/+$/, '') + '/' + LEDGER;
async function fetchBytes(u) {
  const r = await fetch(ledgerURL(u), { cache: 'no-store' });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + ledgerURL(u));
  return new Uint8Array(await r.arrayBuffer());
}
const rootLedger = async () => $('rooturl').value.trim() ? new Ledger(await fetchBytes($('rooturl').value)) : null;
function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

// ---------- the ledger you look at: shown as the pages its own dex has ----------

function show(data, root) {
  const t0 = performance.now();
  led = new Ledger(data, root);
  st = led.header ? state(led, root) : null;
  for (const el of shown) el.remove();
  shown = [];
  buildForm();
  if (!led.header) return say('result', 'Not a ledger: ' + led.error);
  say('result', (led.whole ? 'Whole: every hash and signature checks out' : 'Broken at seq ' + led.broken_at + ': ' +
    led.error) + ' (' + led.entries.length + ' entries checked in ' + Math.round(performance.now() - t0) + ' ms).');
  let at = $('result').parentElement;
  const add = (tag, html, id) => {
    const el = document.createElement(tag);
    el.innerHTML = html;
    if (id) el.id = id;
    for (const a of el.querySelectorAll('a[href]')) {  // links between the dex's pages jump within this page
      const h = a.getAttribute('href');
      if (h === LEDGER && loadedFrom) a.href = ledgerURL(loadedFrom);
      else if (/^[^:/]+\.html$/.test(h)) a.href = '#' + h.slice(0, -5);
    }
    at.after(el);
    at = el;
    shown.push(el);
  };
  for (const page of pages(led)) {
    add('h2', page.title, htmlTitle(page.title));
    for (const line of page.body) add('p', line);
  }
  showOwn();
}

async function load() {
  say('err', '');
  try {
    loadedFrom = $('url').value.trim();
    show(await fetchBytes(loadedFrom), await rootLedger());
  } catch (e) {
    say('result', e.message + '. The site must allow cross-origin reads (GitHub Pages does), or download the file and open it here.');
  }
}

// ---------- your key and your ledger ----------

function setKey(s) {
  secret = s;
  say('pub', s ? publicKey(s) : 'none');
  if (s) store.set('ledgdex-secret', hex(s)); else store.del('ledgdex-secret');
  showOwn();
}
function setOwn(l) {
  own = l;
  if (l) store.set('ledgdex-own', dec.decode(l.data)); else store.del('ledgdex-own');
  showOwn();
}
const mineKey = () => own && secret && own.keys.signing().includes(publicKey(secret));
function showOwn() {
  if (!own) return say('own', 'none open');
  const count = (t) => own.entries.filter((e) => e.msg.type === t).length;
  say('own', own.header.name + ', ' + own.entries.length + ' entries, ' + (own.whole ? 'whole' : 'broken at seq ' +
    own.broken_at) + ', ' + count('sent') + ' sent, ' + count('receipt') + ' receipts. Ledger ' + short(own.id) +
    (secret && !mineKey() ? '. Your key is not a signing key of this ledger.' : ''));
}
const append = (m) => { own.append(own.nextEntry(secret, m)); setOwn(own); };
function needOwn() {
  if (!own || !mineKey()) throw new Invalid('open or create your ledger, and use its key');
}

function collectReceipts() {
  say('err', '');
  try {
    needOwn();
    if (!led || !led.whole) throw new Invalid('load the seller\'s ledger first');
    const held = new Set(own.entries.filter((e) => e.msg.type === 'receipt').map((e) => hash(e.msg.body.entry)));
    const mine = new Set(own.entries.filter((e) => e.msg.type === 'sent').map((e) => hash(e.msg.body.msg)));
    const chain = led.entries.filter((e) => KEY_TYPES.has(e.msg.type));
    let n = 0;
    led.entries.forEach((e, i) => {
      if (!mine.has(hash(e.msg)) || held.has(led.ids[i])) return;
      const body = { ledger: led.id, url: led.dex || loadedFrom, header: led.header, entry: e };
      const keys = chain.filter((k) => k.seq < e.seq);
      append(message(secret, 'receipt', keys.length ? { ...body, keys } : body));
      n++;
    });
    say('err', n + ' new receipts kept.');
  } catch (e) { fail(e); }
}

async function downloadDex() {
  say('err', '');
  try {
    needOwn();
    const template = await (await fetch('dexweb-template.json')).json();
    const { files, dirs } = makeDex(own.data, own.header.name, template);
    download(zip(files, dirs, htmlTitle(own.header.name) + '-dex/'), htmlTitle(own.header.name) + '-dex.zip');
  } catch (e) { fail(e); }
}

// ---------- signing ----------

const pick = (id, options, label) => label + ' <select id="' + id + '" aria-label="' + label + '">' +
  (options.length ? options.map(([v, t]) => '<option value="' + v + '">' + t.replace(/</g, '&lt;') + '</option>').join('')
    : '<option value="">(none in this ledger)</option>') + '</select> ';
const field = (id, label, value = '', type = 'text') =>
  '<input id="' + id + '" type="' + type + '" value="' + value + '" placeholder="' + label + '" aria-label="' + label + '"> ';

function buildForm() {
  const offers = st ? Object.entries(st.offers).filter(([, o]) => o.status === 'open').map(([id, o]) => [id, o.title + ' (' + o.remaining + ' left)']) : [];
  const claims = st ? Object.entries(st.claims).filter(([, c]) => c.status !== 'rejected').map(([id, c]) => [id, short(id) + ' ' + c.status])
    .concat(Object.entries(st.auctions).filter(([, a]) => a.winner).map(([id, a]) => [id, 'auction ' + short(id) + ' ' + a.status])) : [];
  const auctions = st ? Object.entries(st.auctions).map(([id, a]) => [id, led.entries[led.find(id)].msg.body.item.title + ' (' + a.status + ')']) : [];
  $('form').innerHTML = {
    claim: () => pick('f-offer', offers, 'Offer') + field('f-qty', 'quantity', '1', 'number'),
    paid: () => pick('f-claim', claims, 'Claim') + field('f-method', 'method', 'upi') + field('f-ref', 'reference'),
    confirmed: () => pick('f-claim', claims, 'Claim'),
    dispute: () => pick('f-claim', claims, 'Claim') + field('f-text', 'what went wrong'),
    bid: () => pick('f-auction', auctions, 'Auction') + field('f-amount', 'amount (kept secret until you reveal)', '', 'number'),
    reveal: () => pick('f-auction', auctions, 'Auction'),
  }[$('type').value]();
}

function body() {
  const t = $('type').value, v = (id) => $(id) ? $(id).value : '';
  if (!led || !led.whole) throw new Invalid('load a whole ledger first');
  if (t === 'claim') {
    if (!v('f-offer')) throw new Invalid('choose an offer');
    const m = led.entries[led.find(v('f-offer'))].msg;
    return { offer: v('f-offer'), offer_hash: hash(m), quantity: parseInt(v('f-qty'), 10), price: m.body.price };
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
  say('err', '');
  try {
    if (!secret) throw new Invalid('make or paste a key first');
    if (own && own.owner !== publicKey(secret)) throw new Invalid('sign with your ledger\'s owner key: it is who you are in other ledgers');
    if (own && led && led.id === own.id) throw new Invalid('this is your own ledger');
    lastMsg = message(secret, $('type').value, body());
    if (own) append(message(secret, 'sent', { to: led.owner, msg: lastMsg }));
    say('signed', own ? 'Signed, and kept as "sent" in your ledger: download your dex and publish it, and the seller ' +
      'collects it from there. Or send this file:' : 'Signed. Send this file to the ledger owner:');
    say('msg', canonString(lastMsg));
    $('download').hidden = $('copy').hidden = false;
  } catch (e) {
    fail(e);
    $('download').hidden = $('copy').hidden = true;
  }
}

// ---------- wiring ----------

function main() {
  $('gen').onclick = () => setKey(newSecret());
  $('import').onclick = () => {
    const v = $('secret').value.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(v)) return fail(new Error('A secret key is 64 hex characters.'));
    $('secret').value = '';
    say('err', '');
    setKey(unhex(v));
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
  $('ownsave').onclick = downloadDex;
  $('ownjsonl').onclick = () => own ? download(new Blob([own.data]), LEDGER) : fail(new Error('no ledger of yours is open'));
  $('receipts').onclick = collectReceipts;
  $('type').onchange = buildForm;
  $('signit').onclick = signIt;
  $('download').onclick = () => download(new Blob([canonString(lastMsg) + '\n']), lastMsg.type + '-' + hash(lastMsg).slice(7, 19) + '.json');
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
}

if ($('url')) main();  // dexweb puts this script on every page; only the viewer page has its controls

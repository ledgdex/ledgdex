// Keys, messages, entries and ledger verification (spec 1-5). Mirrors py/ledgdex/core.py.
import * as ed from './ed25519.js';
import { canon, hash, parse, sha256id, check, CanonError } from './canon.js';
import { hex, unhex } from './sha.js';

const KEY_RE = /^ed25519:[0-9a-f]{64}$/;
const SIG_RE = /^[0-9a-f]{128}$/;
const ID_RE = /^sha256:[0-9a-f]{64}$/;
const TIME_RE = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)Z$/;
export const SKEW = 300;

export class Invalid extends Error {}

// ---------- keys and time ----------

export function newSecret() {
  return crypto.getRandomValues(new Uint8Array(32));
}
export const publicKey = (secret) => 'ed25519:' + hex(ed.publicKey(secret));
export const sign = (secret, obj) => hex(ed.sign(secret, canon(obj)));
export function verify(key, obj, sig) {
  if (!isKey(key) || typeof sig !== 'string' || !SIG_RE.test(sig)) return false;
  return ed.verify(unhex(key.slice(8)), canon(obj), unhex(sig));
}
export const isKey = (v) => typeof v === 'string' && KEY_RE.test(v);
export const isId = (v) => typeof v === 'string' && ID_RE.test(v);
export function isTime(v) {
  const m = typeof v === 'string' && TIME_RE.exec(v);
  if (!m) return false;
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
  const t = new Date(0);
  t.setUTCFullYear(y, mo - 1, d);  // not Date.UTC, which reads years 0-99 as 1900-1999
  t.setUTCHours(h, mi, s);
  return y >= 1 && t.getUTCFullYear() === y && t.getUTCMonth() === mo - 1 && t.getUTCDate() === d &&
    t.getUTCHours() === h && t.getUTCMinutes() === mi && t.getUTCSeconds() === s;
}
export const seconds = (t) => Date.parse(t) / 1000;
export const utc = (s) => new Date(s * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');
export const now = () => utc(Math.floor(Date.now() / 1000));

// ---------- message bodies ----------

export const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const str = (v) => typeof v === 'string';
const int = (v) => typeof v === 'number' && Number.isInteger(v);
const exact = (v, keys) => v !== null && typeof v === 'object' && !Array.isArray(v) &&
  Object.keys(v).length === keys.length && keys.every((k) => has(v, k));
const media = (v) => Array.isArray(v) && v.every((m) => exact(m, ['url', 'hash']) && str(m.url) &&
  !m.url.startsWith('data:') && isId(m.hash));
const item = (v) => exact(v, ['title', 'text', 'media']) && str(v.title) && str(v.text) && media(v.media);
const allow = (v) => v === 'any' || v === 'admitted' || (Array.isArray(v) && v.every(isKey));
const pay = (v) => Array.isArray(v) && v.every((x) => exact(x, ['method', 'to']) && str(x.method) && str(x.to));
const arbiter = (v) => exact(v, ['key', 'url']) && isKey(v.key) && str(v.url);
const header = (v) => exact(v, ['ledger', 'name', 'owner']) && v.ledger === 1 && str(v.name) && isKey(v.owner);
const entry = (v) => exact(v, ['seq', 'prev', 'time', 'msg', 'sig']) && int(v.seq) && v.seq >= 0 && isId(v.prev) &&
  isTime(v.time) && str(v.sig);
const nonce = (v) => str(v) && /^[0-9a-f]{32,}$/.test(v);
const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

export const BODIES = {
  open: [{ about: str, dex: str }, {}],
  admit: [{ key: isKey, name: str, note: str }, {}],
  revoke: [{ key: isKey, reason: str }, {}],
  note: [{ ref: isId, text: str }, {}],
  sent: [{ to: isKey, msg: isObject }, {}],
  receipt: [{ ledger: isId, url: str, header, entry }, { keys: (v) => Array.isArray(v) && v.every(entry) }],
  rotate: [{ key: isKey }, {}],
  device: [{ key: isKey, name: str }, {}],
  device_revoke: [{ key: isKey, reason: str }, {}],
  dispute: [{ claim: isId, text: str, evidence: (v) => Array.isArray(v) && v.every(str) }, {}],
  ruling: [{ dispute: isId, outcome: (v) => ['release', 'refund', 'split'].includes(v), text: str }, {}],
  auction: [{ item, currency: str, close: isTime, reveal_until: isTime, best: (v) => v === 'highest' || v === 'lowest',
    reserve: (v) => int(v) && v >= 0, allow, arbiter, terms: str }, {}],
  bid: [{ auction: isId, commit: isId }, {}],
  reveal: [{ auction: isId, amount: (v) => int(v) && v >= 0, nonce }, {}],
  list: [{ ledger: isId, url: str, owner: isKey, note: str }, {}],
  delist: [{ ledger: isId, reason: str }, {}],
  recover: [{ ledger: isId, key: isKey }, {}],
  recovered: [{ root: isId, entry: isId }, {}],
  offer: [{ item, quantity: (v) => int(v) && v >= 1, unit: str, currency: str, price: (v) => int(v) && v >= 0,
    allow, pay, arbiter, terms: str }, { expires: isTime }],
  withdraw: [{ offer: isId }, {}],
  claim: [{ offer: isId, offer_hash: isId, quantity: int, price: int }, {}],
  paid: [{ claim: isId, method: str, ref: str }, {}],
  received: [{ claim: isId, amount: int }, {}],
  delivered: [{ claim: isId, note: str }, {}],
  confirmed: [{ claim: isId }, {}],
};
export const COUNTERPARTY = new Set(['claim', 'paid', 'confirmed', 'dispute', 'ruling', 'bid', 'reveal']);
export const OWNER_ONLY = new Set(['open', 'rotate', 'device', 'device_revoke', 'recover']);  // recover: in the root, hands a ledger over
export const KEY_TYPES = new Set(['rotate', 'device', 'device_revoke', 'recovered']);

export class Keys {
  constructor(owner) { this.owner = owner; this.devices = new Set(); }
  signing() { return [this.owner, ...[...this.devices].sort()]; }
  canAuthor(type, key) {
    if (OWNER_ONLY.has(type)) return key === this.owner;
    return key === this.owner || this.devices.has(key);
  }
  signedBy(e) {
    for (const k of this.signing()) if (verify(k, unsigned(e), e.sig)) return k;
    return null;
  }
  apply(m) {
    const b = m.body;
    if (m.type === 'rotate') this.owner = b.key;
    else if (m.type === 'device') this.devices.add(b.key);
    else if (m.type === 'device_revoke') this.devices.delete(b.key);
    else if (m.type === 'recovered') { this.owner = m.by; this.devices = new Set(); }
  }
}

export function checkBody(type, body, root = null) {
  if (typeof type !== 'string') throw new Invalid('the type must be a string');
  if (!has(BODIES, type)) throw new Invalid('unknown type: ' + type);
  const [req, opt] = BODIES[type];
  if (!isObject(body)) throw new Invalid(type + ': body is not an object');
  for (const k of Object.keys(body)) if (!has(req, k) && !has(opt, k)) throw new Invalid(type + ': unexpected field ' + k);
  for (const [k, ok] of [...Object.entries(req), ...Object.entries(opt)]) {
    if (has(body, k) && !ok(body[k])) throw new Invalid(type + ': bad ' + k);
    if (has(req, k) && !has(body, k)) throw new Invalid(type + ': missing ' + k);
  }
  if (type === 'sent') checkMessage(body.msg, root);
  if (type === 'receipt') checkReceipt(body, root);
}

export function checkMessage(m, root = null) {
  if (!exact(m, ['v', 'type', 'by', 'at', 'body', 'sig'])) {
    throw new Invalid('a message has exactly the keys v, type, by, at, body, sig');
  }
  try { check(m); } catch (e) { throw new Invalid(e.message); }
  if (m.v !== 1) throw new Invalid('message version must be 1');
  if (!isKey(m.by)) throw new Invalid('bad author key');
  if (!isTime(m.at)) throw new Invalid('bad time');
  checkBody(m.type, m.body, root);
  if (m.type === 'auction' && !(m.body.close < m.body.reveal_until)) {
    throw new Invalid('auction: close must be before reveal_until');
  }
  if (!verify(m.by, unsigned(m), m.sig)) throw new Invalid('message signature does not verify');
}

/** Spec 5.7: a "recovered" entry e of ledger ledgerId is signed by the new key, which a "recover" entry in the root
 * names. A recover entry is spent by its first "recovered", and is void once the ledger changes its keys after the
 * root made it (prior: the ledger's earlier key entries). Throws otherwise. */
export function rootRecovers(root, ledgerId, e, prior = []) {
  const m = e.msg, b = m.body;
  if (!verify(m.by, unsigned(e), e.sig)) throw new Invalid('recovered: the entry is not signed by the recovered key');
  if (!root) throw new Invalid('a "recovered" entry can only be verified with the root ledger');
  if (root.id !== b.root) throw new Invalid('recovered: names root ' + b.root + ', not the root given (' + root.id + ')');
  const i = root.find(b.entry);
  const r = i === null ? null : root.entries[i].msg;
  if (!r || r.type !== 'recover' || r.body.ledger !== ledgerId || r.body.key !== m.by) {
    throw new Invalid('recovered: the root has no recover entry for this ledger and key');
  }
  for (const p of prior) {
    if (p.msg.type === 'recovered' && p.msg.body.entry === b.entry) throw new Invalid('recovered: that recover entry was already used');
    if ((p.msg.type === 'rotate' || p.msg.type === 'recovered') && p.time > root.entries[i].time) {
      throw new Invalid('recovered: the ledger changed its keys after the root named this key');
    }
  }
}

// a "recovered" key entry is checked against the root, as in the ledger: else anyone could sign a false receipt
export function checkReceipt(body, root = null) {
  if (hash(body.header) !== body.ledger) throw new Invalid('receipt: header does not match ledger id');
  const e = body.entry, keys = new Keys(body.header.owner);
  let last = -1;
  for (const k of body.keys || []) {
    if (!(last < k.seq && k.seq < e.seq)) throw new Invalid('receipt: key entries must be in order and before the entry');
    checkMessage(k.msg, root);
    const m = k.msg;
    if (!KEY_TYPES.has(m.type)) {
      throw new Invalid('receipt: keys may hold only rotate, device, device_revoke and recovered entries');
    }
    if (m.type === 'recovered') rootRecovers(root, body.ledger, k, body.keys.filter((x) => x.seq < k.seq));
    const signer = m.type === 'recovered' ? null : keys.signedBy(k);
    const ok = m.type === 'recovered' || (signer !== null && keys.canAuthor(m.type, m.by) && (!OWNER_ONLY.has(m.type) || signer === keys.owner));
    if (!ok) throw new Invalid('receipt: key entry ' + k.seq + ' does not verify');
    keys.apply(m);
    last = k.seq;
  }
  if (keys.signedBy(e) === null) throw new Invalid('receipt: entry signature does not verify');
  checkMessage(e.msg, root);
}

export function unsigned(obj) {
  const o = {};
  for (const k of Object.keys(obj)) if (k !== 'sig') o[k] = obj[k];
  return o;
}

export function message(secret, type, body, at, root = null) {
  const m = { v: 1, type, by: publicKey(secret), at: at || now(), body };
  m.sig = sign(secret, m);
  checkMessage(m, root);
  return m;
}

// The same with a signer (sig.js), whose sign() is asynchronous: Web Crypto in the browser.
export const signA = async (signer, obj) => hex(await signer.sign(canon(obj)));
export async function messageA(signer, type, body, at, root = null) {
  const m = { v: 1, type, by: signer.public, at: at || now(), body };
  m.sig = await signA(signer, m);
  checkMessage(m, root);
  return m;
}

// ---------- ledgers (spec 3) ----------

const NL = 0x0a;
const enc = new TextEncoder();

export class Ledger {
  /** data: Uint8Array or string. root: the root Ledger, needed to verify "recovered" entries (spec 5.7). */
  constructor(data, root = null) {
    this.data = typeof data === 'string' ? enc.encode(data) : data;
    this.root = root;
    this.header = null; this.id = null; this.headerLine = null;
    this.entries = []; this.ids = []; this.lines = []; this.index = new Map();  // id -> position: no quadratic state
    this.broken_at = null; this.error = null;
    this.keys = null; this.keyHistory = new Set(); this.msgIds = new Set();
    this._load();
  }

  _load() {
    const lines = [];
    let start = 0;
    for (let i = 0; i < this.data.length; i++) {
      if (this.data[i] === NL) { lines.push(this.data.subarray(start, i)); start = i + 1; }
    }
    const partial = start < this.data.length;
    if (!lines.length) { this.error = partial ? 'the header must end with a newline' : 'empty ledger'; return; }
    let h;
    try { h = parse(lines[0]); } catch (e) { this.error = 'header: ' + e.message; return; }
    if (!header(h)) { this.error = 'header: must be {"ledger":1,"name":str,"owner":key}'; return; }
    this.header = h; this.headerLine = lines[0]; this.id = sha256id(lines[0]);
    this.keys = new Keys(h.owner); this.keyHistory = new Set([h.owner]);
    for (let n = 0; n < lines.length - 1; n++) {
      const line = lines[n + 1];
      let e;
      try {
        e = parse(line);
        this.checkEntry(n, e);
      } catch (err) {
        if (!(err instanceof CanonError || err instanceof Invalid)) throw err;
        this.broken_at = n; this.error = 'seq ' + n + ': ' + err.message;
        return;
      }
      this._add(e, line);
    }
    if (partial) {
      const n = this.entries.length;
      this.broken_at = n; this.error = 'seq ' + n + ': the line does not end with a newline';
    }
  }

  _add(e, line) {
    const id = sha256id(line);
    if (!this.index.has(id)) this.index.set(id, this.ids.length);
    this.entries.push(e); this.ids.push(id); this.lines.push(line);
    const mid = hash(e.msg), duplicate = this.msgIds.has(mid);  // a message recorded again changes nothing (6.2)
    this.msgIds.add(mid);
    if (KEY_TYPES.has(e.msg.type) && !duplicate) {
      this.keys.apply(e.msg);
      this.keyHistory.add(this.keys.owner);
      for (const d of this.keys.devices) this.keyHistory.add(d);
    }
  }

  get owner() { return this.keys ? this.keys.owner : null; }
  get devices() { return this.keys ? [...this.keys.devices].sort() : []; }
  /** The dex address in the "open" entry ('' if none). */
  get dex() { return this.entries.length ? this.entries[0].msg.body.dex : ''; }
  get whole() { return this.header !== null && this.broken_at === null && this.error === null; }
  head() { return this.entries.length ? { seq: this.entries.length - 1, id: this.ids[this.ids.length - 1] } : null; }
  find(id) { const i = this.index.get(id); return i === undefined ? null : i; }

  checkEntry(n, e) {
    if (!exact(e, ['seq', 'prev', 'time', 'msg', 'sig'])) {
      throw new Invalid('an entry has exactly the keys seq, prev, time, msg, sig');
    }
    if (e.seq !== n) throw new Invalid('seq must be ' + n);
    if (e.prev !== (this.ids.length ? this.ids[this.ids.length - 1] : this.id)) {
      throw new Invalid('prev does not match the previous entry');
    }
    if (!isTime(e.time)) throw new Invalid('bad time');
    if (this.entries.length && e.time < this.entries[this.entries.length - 1].time) {
      throw new Invalid('time goes backwards');
    }
    checkMessage(e.msg, this.root);
    const m = e.msg;
    if (m.type === 'recovered') this.checkRecovery(e);
    else {
      const signer = this.keys.signedBy(e);
      if (signer === null) throw new Invalid('entry signature does not verify with a current signing key');
      // messages carry no ledger id: a device must not copy in an owner-only message signed for another ledger
      if (OWNER_ONLY.has(m.type) && signer !== this.keys.owner) throw new Invalid(m.type + ' must be recorded by the owner key itself');
    }
    if (seconds(e.time) < seconds(m.at) - SKEW) {
      throw new Invalid('message recorded more than ' + SKEW + ' seconds before it was signed');
    }
    if ((n === 0) !== (m.type === 'open')) throw new Invalid('"open" is the first entry, and only the first');
    if (!COUNTERPARTY.has(m.type) && m.type !== 'recovered' && !this.keys.canAuthor(m.type, m.by)) {
      throw new Invalid(m.type + ' must be authored by the ledger owner' +
        (OWNER_ONLY.has(m.type) ? '' : ' or an active device key'));
    }
  }

  checkRecovery(e) { rootRecovers(this.root, this.id, e, this.entries.filter((x) => KEY_TYPES.has(x.msg.type))); }


  /** A new signed entry recording msg on top of this ledger (verified when appended). */
  nextEntry(secret, msg, at) {
    const e = this._draft(publicKey(secret), msg, at);
    e.sig = sign(secret, e);
    return e;
  }

  async nextEntryA(signer, msg, at) {
    const e = this._draft(signer.public, msg, at);
    e.sig = await signA(signer, e);
    return e;
  }

  _draft(signer, msg, at) {
    if (!this.whole) throw new Invalid('the ledger is broken: ' + this.error);
    if (!this.keys.signing().includes(signer) && !(msg.type === 'recovered' && msg.by === signer)) {
      throw new Invalid('this key is not a signing key of this ledger');
    }
    let t = at || now();
    const last = this.entries[this.entries.length - 1];
    if (last && t < last.time) t = last.time;
    if (seconds(t) < seconds(msg.at) - SKEW) {
      throw new Invalid('the message is signed more than ' + SKEW + ' seconds in the future');
    }
    return { seq: this.entries.length, prev: this.ids.length ? this.ids[this.ids.length - 1] : this.id, time: t, msg };
  }

  append(e) {
    const line = canon(e);
    this.checkEntry(this.entries.length, e);
    this._add(e, line);
    const data = new Uint8Array(this.data.length + line.length + 1);
    data.set(this.data); data.set(line, this.data.length); data[data.length - 1] = NL;
    this.data = data;
    return this.ids[this.ids.length - 1];
  }
}

export function newLedger(secret, name, about, dex, at) {
  const led = emptyLedger(publicKey(secret), name), t = at || now();
  led.append(led.nextEntry(secret, message(secret, 'open', { about, dex }, t), t));
  return led;
}

export async function newLedgerA(signer, name, about, dex, at) {
  const led = emptyLedger(signer.public, name), t = at || now();
  led.append(await led.nextEntryA(signer, await messageA(signer, 'open', { about, dex }, t), t));
  return led;
}

function emptyLedger(owner, name) {
  const head = canon({ ledger: 1, name, owner }), data = new Uint8Array(head.length + 1);
  data.set(head); data[head.length] = NL;
  return new Ledger(data);
}

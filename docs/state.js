// The state function (spec 6): replay a ledger into one JSON object. Mirrors py/ledgdex/state.py.
import { hash } from './canon.js';
import { Keys, has } from './core.js';

const OUTCOME = { release: 'released', refund: 'refunded', split: 'split' };

/** The root's admit and revoke entries in order, as Map key -> [[time, admitted]] (a message recorded twice counts
 * once, as in 6.2). A claim is judged by the root's admissions at its own time, never by later ones (spec 5.7). */
export function admissions(root) {
  const out = new Map(), seen = new Set();
  for (const e of root.entries) {
    const m = e.msg, id = hash(m);
    if ((m.type === 'admit' || m.type === 'revoke') && !seen.has(id)) {
      if (!out.has(m.body.key)) out.set(m.body.key, []);
      out.get(m.body.key).push([e.time, m.type === 'admit']);
    }
    seen.add(id);
  }
  return out;
}

/** Whether the root had admitted key at time t. */
export function admittedAt(admits, key, t) {
  let now = false;
  for (const [time, admitted] of admits.get(key) || []) {
    if (time > t) break;
    now = admitted;
  }
  return now;
}

/** root: the root Ledger, for "allow": "admitted" (spec 5.7). now: when auction statuses are judged (default: the
 * time of the last entry). */
export function state(led, root = null, now = null) {
  const keys = led.header ? new Keys(led.header.owner) : null;
  const admitted = new Set();
  const rootAdmits = root && root.header ? admissions(root) : null;
  const offers = {}, claims = {}, auctions = {}, disputes = {}, listings = {}, recoveries = {}, ignored = [];
  const sellers = {}, hidden = {}, offerHash = {};  // offerHash: offer id -> hash of its message, computed once

  const ignore = (n, reason) => ignored.push({ seq: n, reason });
  const mine = (key) => key === keys.owner || keys.devices.has(key);
  const may = (allow, key, t) => {
    if (allow === 'any') return true;
    if (allow === 'admitted') return admitted.has(key) && (rootAdmits === null || admittedAt(rootAdmits, key, t));
    return allow.includes(key);
  };

  function award(aid, t) {
    const a = auctions[aid], h = hidden[aid];
    if (t < h.body.reveal_until) return null;
    if (!h.decided) {
      h.decided = true;
      const b = h.body;
      let best = null;
      const bids = Object.entries(h.bids).sort((x, y) => x[1].seq - y[1].seq);
      for (const [key] of bids) {
        if (!has(h.reveals, key)) continue;
        const amt = h.reveals[key];
        if ((b.best === 'highest' && amt < b.reserve) || (b.best === 'lowest' && amt > b.reserve)) continue;
        if (best === null || (b.best === 'highest' ? amt > best[1] : amt < best[1])) best = [key, amt];
      }
      if (best) { a.winner = best[0]; a.amount = best[1]; a.buyer = best[0]; a.status = 'accepted'; }
    }
    return has(a, 'winner') ? a : null;
  }

  function deal(n, ref, t, need = true) {
    let d;
    if (has(claims, ref)) d = claims[ref];
    else if (has(auctions, ref)) {
      d = award(ref, t);
      if (d === null) { ignore(n, 'not_awarded'); return null; }
    } else { ignore(n, 'unknown_claim'); return null; }
    if (need && d.status !== 'accepted' && d.status !== 'closed') { ignore(n, 'claim_not_accepted'); return null; }
    return d;
  }

  const maybeClose = (d) => {
    if (d.status === 'accepted' && has(d, 'received') && d.delivered && d.confirmed) d.status = 'closed';
  };

  const recorded = new Set();  // message ids: a message recorded twice counts once (no replayed claims)
  led.entries.forEach((e, n) => {
    const id = led.ids[n], m = e.msg, b = m.body, t = m.type, at = e.time;
    const mid = hash(m);
    if (recorded.has(mid)) { ignore(n, 'duplicate_message'); return; }
    recorded.add(mid);
    if (t === 'offer') {
      offers[id] = { title: b.item.title, remaining: b.quantity, status: 'open' };
      offerHash[id] = mid;
      sellers[id] = b;
    } else if (t === 'withdraw') {
      const o = has(offers, b.offer) ? offers[b.offer] : null;
      if (o === null || o.status !== 'open') ignore(n, 'offer_not_open');
      else o.status = 'withdrawn';
    } else if (t === 'admit') admitted.add(b.key);
    else if (t === 'revoke') admitted.delete(b.key);
    else if (t === 'claim') {
      const c = { offer: b.offer, buyer: m.by, quantity: b.quantity, price: b.price };
      claims[id] = c;
      const o = has(offers, b.offer) ? offers[b.offer] : null, ob = o ? sellers[b.offer] : null;
      let reason = null;
      if (o === null) reason = 'unknown_offer';
      else if (b.offer_hash !== offerHash[b.offer]) reason = 'offer_changed';
      else if (o.status === 'withdrawn') reason = 'withdrawn';
      else if (has(ob, 'expires') && at >= ob.expires) reason = 'expired';
      else if (mine(m.by)) reason = 'self_claim';
      else if (!may(ob.allow, m.by, at)) reason = 'not_allowed';
      else if (b.quantity < 1 || b.quantity > o.remaining) reason = 'bad_quantity';
      else if (b.price !== ob.price) reason = 'price_mismatch';
      if (reason) { c.status = 'rejected'; c.reason = reason; } else {
        c.status = 'accepted';
        sellers[id] = ob;
        o.remaining -= b.quantity;
        if (o.remaining === 0) o.status = 'sold';
      }
    } else if (t === 'paid' || t === 'confirmed') {
      const d = deal(n, b.claim, at);
      if (d !== null) {
        if (m.by !== d.buyer) ignore(n, 'not_buyer');
        else if (t === 'paid') d.paid = { method: b.method, ref: b.ref };
        else if (!d.delivered) ignore(n, 'not_delivered');
        else { d.confirmed = true; maybeClose(d); }
      }
    } else if (t === 'received' || t === 'delivered') {
      const d = deal(n, b.claim, at);
      if (d !== null) {
        if (t === 'received') d.received = b.amount; else d.delivered = true;
        maybeClose(d);
      }
    } else if (t === 'dispute') {
      const d = deal(n, b.claim, at);
      if (d !== null) {
        if (m.by !== d.buyer && !mine(m.by)) ignore(n, 'not_party');
        else { d.status = 'disputed'; disputes[id] = { claim: b.claim }; }
      }
    } else if (t === 'ruling') {
      const dp = has(disputes, b.dispute) ? disputes[b.dispute] : null;
      if (dp === null) ignore(n, 'unknown_dispute');
      else if (has(dp, 'ruling')) ignore(n, 'already_ruled');
      else {
        const ref = dp.claim;
        const src = has(claims, ref) ? sellers[ref] : hidden[ref].body;
        if (m.by !== src.arbiter.key) ignore(n, 'not_arbiter');
        else {
          dp.ruling = id;
          (has(claims, ref) ? claims[ref] : auctions[ref]).status = OUTCOME[b.outcome];
        }
      }
    } else if (t === 'auction') {
      auctions[id] = { status: 'open', bids: 0 };
      hidden[id] = { body: b, bids: {}, reveals: {} };
    } else if (t === 'bid') {
      const h = has(hidden, b.auction) ? hidden[b.auction] : null;
      if (h === null) ignore(n, 'unknown_auction');
      else if (at >= h.body.close) ignore(n, 'late_bid');
      else if (mine(m.by)) ignore(n, 'self_bid');
      else if (!may(h.body.allow, m.by, at)) ignore(n, 'not_allowed');
      else if (has(h.bids, m.by)) ignore(n, 'duplicate_bid');
      else { h.bids[m.by] = { commit: b.commit, seq: n }; auctions[b.auction].bids += 1; }
    } else if (t === 'reveal') {
      const h = has(hidden, b.auction) ? hidden[b.auction] : null;
      const bid = h && has(h.bids, m.by) ? h.bids[m.by] : null;
      if (h === null) ignore(n, 'unknown_auction');
      else if (at < h.body.close) ignore(n, 'early_reveal');
      else if (at >= h.body.reveal_until) ignore(n, 'late_reveal');
      else if (bid === null) ignore(n, 'no_bid');
      else if (has(h.reveals, m.by)) ignore(n, 'duplicate_reveal');
      else if (hash({ amount: b.amount, nonce: b.nonce }) !== bid.commit) ignore(n, 'bad_reveal');
      else h.reveals[m.by] = b.amount;
    } else if (t === 'list') listings[b.ledger] = { url: b.url, owner: b.owner, note: b.note };
    else if (t === 'delist') {
      if (!has(listings, b.ledger)) ignore(n, 'not_listed'); else delete listings[b.ledger];
    } else if (t === 'recover') recoveries[b.ledger] = { key: b.key, entry: id };
    else if (t === 'sent') { if (!mine(b.msg.by)) ignore(n, 'not_my_message'); }
    else if (t === 'receipt') { if (!mine(b.entry.msg.by)) ignore(n, 'not_my_message'); }
    if (t === 'rotate' || t === 'device' || t === 'device_revoke' || t === 'recovered') keys.apply(m);
  });

  const when = now || (led.entries.length ? led.entries[led.entries.length - 1].time : null);
  for (const aid of Object.keys(auctions)) {
    const a = auctions[aid], b = hidden[aid].body;
    if (when === null || when < b.close) a.status = 'open';
    else if (when < b.reveal_until) a.status = 'revealing';
    else if (award(aid, when) === null) a.status = 'no_winner';
    else if (a.status === 'accepted') a.status = 'awarded';
    delete a.buyer;
  }

  const head = led.head();
  return {
    ledger: led.id,
    owner: keys ? keys.owner : null,
    devices: keys ? [...keys.devices].sort() : [],
    head: head || { seq: -1, id: led.id },
    broken_at: led.broken_at,
    admitted: [...admitted].sort(),
    offers, claims, auctions, disputes, listings, recoveries, ignored,
  };
}

// expect: Ledgdex Docs: whole, 4 entries
// expect: Example offer: Penjointu v1 weights | USD 2,500.00 (250000) per license | 10 left
// expect: one changed letter breaks it at entry 1
import { readFile } from 'fs/promises';
import { pathToFileURL } from 'url';

// Load the JavaScript core: from `LEDGDEX_JS` (a folder or a URL) if set, else from `js/` in the ledgdex repository.
const where = process.env.LEDGDEX_JS || new URL('../../js/', import.meta.url).href;
const base = /^[a-z]+:/.test(where) ? where : pathToFileURL(where.endsWith('/') ? where : where + '/').href;
const { Ledger } = await import(new URL('core.js', base));
const { state } = await import(new URL('state.js', base));
const { amount } = await import(new URL('render.js', base));

// Read a ledger from a dex address, a `ledgdex.jsonl` address or a file, given as the first argument. Without one, this reads the ledger of these docs.
const source = process.argv[2] || 'https://ledgdex.github.io/docs';
async function read(src) {
  if (!/^https?:\/\//.test(src)) return new Uint8Array(await readFile(src));
  const url = src.endsWith('.jsonl') ? src : src.replace(/\/+$/, '') + '/ledgdex.jsonl';
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + ': HTTP ' + res.status);
  return new Uint8Array(await res.arrayBuffer());
}
const bytes = await read(source);

// Verify each hash and each signature. `whole` is true only if each entry is correct. If not, `broken_at` and `error` say where and why.
const led = new Ledger(bytes);
console.log(led.header.name + ': ' + (led.whole ? 'whole' : 'BROKEN at entry ' + led.broken_at + ', ' + led.error) +
  ', ' + led.entries.length + ' entries');

// The state says which offers are open and how many units each offer has. The price and the unit are in the signed offer. Find the offer by its id.
const st = state(led);
for (const [id, o] of Object.entries(st.offers)) {
  if (o.status !== 'open') continue;
  const offer = led.entries[led.index.get(id)].msg.body;
  console.log(o.title, '|', amount(offer.currency, offer.price), 'per', offer.unit, '|', o.remaining, 'left');
}

// Change one letter of the offer's title and read the ledger again: it is no longer whole, and it says where.
const changed = bytes.slice();
changed[Buffer.from(changed).indexOf('Penjointu')] = 'B'.charCodeAt(0);
const bad = new Ledger(changed);
console.log('one changed letter breaks it at entry', bad.broken_at + ':', bad.error);

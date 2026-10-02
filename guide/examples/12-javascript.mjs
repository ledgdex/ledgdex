// The JavaScript core (js/ in the ledgdex repository; served next to the viewer, e.g. core.js at
// https://matrixdex.github.io/ledgdex/core.js). The same module runs in Node and in the browser: plain ES modules, no
// npm. It makes the same bytes, ids, signatures and state as the Python package, checked on every push.
// expect: whole true
// expect: accepted
// expect: same state as a fresh read: true
import { pathToFileURL } from 'url';
// where core.js is: LEDGDEX_JS (a folder or a URL), else js/ next to this guide in the ledgdex repository
const where = process.env.LEDGDEX_JS || new URL('../../js/', import.meta.url).href;
const base = /^[a-z]+:/.test(where) ? where : pathToFileURL(where.endsWith('/') ? where : where + '/').href;
const { Ledger, message, newLedger, newSecret, publicKey } = await import(new URL('core.js', base));
const { state } = await import(new URL('state.js', base));
const { hash, canonString, ID_KEY } = await import(new URL('canon.js', base));

const seller = newSecret(), buyer = newSecret();
const led = newLedger(seller, 'Mango Farm', 'Alphonso mangoes', 'https://farm.example');
const offer = message(seller, 'offer', {
  item: { title: 'Alphonso mangoes', text: '', media: [] }, quantity: 3, unit: 'dozen', currency: 'INR', price: 120000,
  allow: 'any', pay: [], arbiter: { key: publicKey(seller), url: '' }, terms: '' });
const offerId = led.append(led.nextEntry(seller, offer));
const claim = message(buyer, 'claim', { offer: offerId, offer_hash: hash(offer), quantity: 1, price: 120000 });
led.append(led.nextEntry(seller, claim));

// Read it back from the bytes alone, as the viewer does with a ledgdex.jsonl it fetched.
const read = new Ledger(led.data);
console.log('whole', read.whole, 'entries', read.entries.length);
const st = state(read);
console.log(Object.values(st.claims).map((c) => c.status).join(', '));
console.log('same state as a fresh read:', canonString(st, ID_KEY) === canonString(state(new Ledger(led.data)), ID_KEY));

// In a browser page:
//   <script type="module">
//     import { Ledger } from 'https://matrixdex.github.io/ledgdex/core.js';
//     const bytes = new Uint8Array(await (await fetch('https://farm.example/ledgdex.jsonl')).arrayBuffer());
//     const led = new Ledger(bytes);   // led.whole, led.entries, led.error
//   </script>

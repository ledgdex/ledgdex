// expect: whole true
// expect: accepted
// expect: same state as a fresh read: true
import { pathToFileURL } from 'url';

// Load the JavaScript core: from `LEDGDEX_JS` (a folder or a URL) if set, else from `js/` in the ledgdex repository.
const where = process.env.LEDGDEX_JS || new URL('../../js/', import.meta.url).href;
const base = /^[a-z]+:/.test(where) ? where : pathToFileURL(where.endsWith('/') ? where : where + '/').href;
const { Ledger, message, newLedger, newSecret, publicKey } = await import(new URL('core.js', base));
const { state } = await import(new URL('state.js', base));
const { hash, canonString, ID_KEY } = await import(new URL('canon.js', base));

// Make two keys and a ledger, then sign an offer and a buyer's order for it, as in the Python example.
const seller = newSecret(), buyer = newSecret();
const led = newLedger(seller, 'Mango Farm', 'Alphonso mangoes', 'https://farm.example');
const offer = message(seller, 'offer', {
  item: { title: 'Alphonso mangoes', text: '', media: [] }, quantity: 3, unit: 'dozen', currency: 'INR', price: 120000,
  allow: 'any', pay: [], arbiter: { key: publicKey(seller), url: '' }, terms: '' });
const offerId = led.append(led.nextEntry(seller, offer));
const claim = message(buyer, 'claim', { offer: offerId, offer_hash: hash(offer), quantity: 1, price: 120000 });
led.append(led.nextEntry(seller, claim));

// Read it back from the bytes alone, as the viewer does with a `ledgdex.jsonl` it downloaded: it is whole, the order is accepted, and a fresh read gives the same state.
const read = new Ledger(led.data);
console.log('whole', read.whole, 'entries', read.entries.length);
const st = state(read);
console.log(Object.values(st.claims).map((c) => c.status).join(', '));
console.log('same state as a fresh read:', canonString(st, ID_KEY) === canonString(state(new Ledger(led.data)), ID_KEY));

// expect: whole true
// expect: accepted
// expect: same state as a new read: true
import { pathToFileURL } from 'url';

// Load the JavaScript core: from `LEDGDEX_JS` (a folder or a URL) if set, else from `js/` in the ledgdex repository.
const where = process.env.LEDGDEX_JS || new URL('../../js/', import.meta.url).href;
const base = /^[a-z]+:/.test(where) ? where : pathToFileURL(where.endsWith('/') ? where : where + '/').href;
const { Ledger, message, newLedger, newSecret, publicKey } = await import(new URL('core.js', base));
const { state } = await import(new URL('state.js', base));
const { hash, canonString, ID_KEY } = await import(new URL('canon.js', base));

// Make two keys and a ledger. Then sign an offer, and a claim of a buyer for it, as in the Python example.
const seller = newSecret(), buyer = newSecret();
const led = newLedger(seller, 'biobot', 'Maker of Penjointu', 'https://biobot.example');
const offer = message(seller, 'offer', {
  item: { title: 'Penjointu v1 weights', text: '', media: [] }, quantity: 3, unit: 'license', currency: 'USD', price: 250000,
  allow: 'any', pay: [], arbiter: { key: publicKey(seller), url: '' }, terms: '' });
const offerId = led.append(led.nextEntry(seller, offer));
const claim = message(buyer, 'claim', { offer: offerId, offer_hash: hash(offer), quantity: 1, price: 250000 });
led.append(led.nextEntry(seller, claim));

// Read the ledger from its bytes, as the viewer does with a `ledgdex.jsonl` that it downloaded. The ledger is whole, the claim is accepted, and a new read gives the same state.
const read = new Ledger(led.data);
console.log('whole', read.whole, 'entries', read.entries.length);
const st = state(read);
console.log(Object.values(st.claims).map((c) => c.status).join(', '));
console.log('same state as a new read:', canonString(st, ID_KEY) === canonString(state(new Ledger(led.data)), ID_KEY));

// expect: key sealed with a passphrase: PBKDF2-SHA-256, 600000 rounds
// expect: signed with
// expect: claim recorded:
// expect: the shop accepted the order: accepted
import { execFileSync } from 'child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import { pathToFileURL } from 'url';

// Load the JavaScript core: from `LEDGDEX_JS` (a folder or a URL) if set, else from `js/` in the ledgdex repository. The same modules run in a browser.
const where = process.env.LEDGDEX_JS || new URL('../../js/', import.meta.url).href;
const base = /^[a-z]+:/.test(where) ? where : pathToFileURL(where.endsWith('/') ? where : where + '/').href;
const { Ledger, messageA, newLedgerA, newSecret, publicKey } = await import(new URL('core.js', base));
const { state } = await import(new URL('state.js', base));
const { hash } = await import(new URL('canon.js', base));
const { sealKey, openKey } = await import(new URL('keystore.js', base));
const { signer } = await import(new URL('sig.js', base));

// The shop uses the command line, as in the first trade example: it makes its ledgdex and offers 10 dozen mangoes.
const ledgdex = (...args) => execFileSync('ledgdex', args, { encoding: 'utf8' });
ledgdex('init', 'shop', '--name', 'Mango Farm', '--key', 'farm');
writeFileSync('offer.json', JSON.stringify({ item: { title: 'Alphonso mangoes' }, quantity: 10, unit: 'dozen',
  currency: 'INR', price: 120000 }));
const offerId = ledgdex('offer', 'shop', 'offer.json').trim().split(' ').pop();

// The buyer has only a browser. It makes a key and keeps it sealed with a passphrase, as the viewer does: the sealed box can be stored (in a browser, in `localStorage`), and only the passphrase opens it.
const secret = newSecret();
const box = await sealKey(secret, 'a long passphrase only Asha knows', publicKey(secret));
console.log('key sealed with a passphrase:', box.kdf + ',', box.rounds, 'rounds');
const opened = await openKey(box, 'a long passphrase only Asha knows');

// `signer` signs with Web Crypto's Ed25519 when the browser (or Node) has it, and with ledgdex's own code when it does not.
const sgn = await signer(opened);
console.log('signed with', sgn.name);

// The buyer reads the shop's ledger, finds the offer, and signs a claim for 2 dozen that names the offer by its id and its hash.
const shop = new Ledger(new Uint8Array(readFileSync('shop/ledgdex.jsonl')));
const offer = shop.entries[shop.index.get(offerId)].msg;
const claim = await messageA(sgn, 'claim', { offer: offerId, offer_hash: hash(offer), quantity: 2, price: offer.body.price });

// The buyer keeps the claim as "sent" in a ledger of its own, and publishes it: here, a folder with its `ledgdex.jsonl`. In the viewer, Download your dex does this.
const mine = await newLedgerA(sgn, 'Asha', 'A buyer with a browser', '');
mine.append(await mine.nextEntryA(sgn, await messageA(sgn, 'sent', { to: shop.header.owner, msg: claim })));
mkdirSync('me');
writeFileSync('me/ledgdex.jsonl', mine.data);

// The shop collects the claim from the buyer's dex with the command line, and the order is accepted.
console.log(ledgdex('record', 'shop', '--from', 'me').trim());
const after = state(new Ledger(new Uint8Array(readFileSync('shop/ledgdex.jsonl'))));
console.log('the shop accepted the order:', Object.values(after.claims).map((c) => c.status).join(', '));

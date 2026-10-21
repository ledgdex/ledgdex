// expect: key sealed with a passphrase: PBKDF2-SHA-256, 600000 rounds
// expect: signed with
// expect: claim recorded:
// expect: biobot accepted the claim: accepted
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

// The seller biobot uses the command line, as in the first trade example. It makes its ledgdex and offers 10 licenses for the Penjointu weights.
const ledgdex = (...args) => execFileSync('ledgdex', args, { encoding: 'utf8' });
ledgdex('init', 'biobot', '--name', 'biobot', '--key', 'biobot');
writeFileSync('offer.json', JSON.stringify({ item: { title: 'Penjointu v1 weights' }, quantity: 10, unit: 'license',
  currency: 'USD', price: 250000 }));
const offerId = ledgdex('offer', 'biobot', 'offer.json').trim().split(' ').pop();

// The buyer has only a browser. It makes a key and seals it with a passphrase, as the viewer does. A browser can keep the sealed box in `localStorage`. Only the passphrase opens it.
const secret = newSecret();
const box = await sealKey(secret, 'a long passphrase that only orthonalyzebot knows', publicKey(secret));
console.log('key sealed with a passphrase:', box.kdf + ',', box.rounds, 'rounds');
const opened = await openKey(box, 'a long passphrase that only orthonalyzebot knows');

// `signer` signs with Web Crypto's Ed25519 when the browser (or Node) has it, and with ledgdex's own code when it does not.
const sgn = await signer(opened);
console.log('signed with', sgn.name);

// The buyer reads the ledger of biobot and finds the offer. It signs a claim for 2 licenses that names the offer by its id and its hash.
const seller = new Ledger(new Uint8Array(readFileSync('biobot/ledgdex.jsonl')));
const offer = seller.entries[seller.index.get(offerId)].msg;
const claim = await messageA(sgn, 'claim', { offer: offerId, offer_hash: hash(offer), quantity: 2, price: offer.body.price });

// The buyer keeps the claim as "sent" in a ledger of its own, and publishes it: here, a folder with its `ledgdex.jsonl`. In the viewer, Download your dex does this.
const mine = await newLedgerA(sgn, 'orthonalyzebot', 'A buyer bot with a browser', '');
mine.append(await mine.nextEntryA(sgn, await messageA(sgn, 'sent', { to: seller.header.owner, msg: claim })));
mkdirSync('orthonalyzebot');
writeFileSync('orthonalyzebot/ledgdex.jsonl', mine.data);

// Biobot collects the claim from the dex of the buyer with the command line, and accepts the claim.
console.log(ledgdex('record', 'biobot', '--from', 'orthonalyzebot').trim());
const after = state(new Ledger(new Uint8Array(readFileSync('biobot/ledgdex.jsonl'))));
console.log('biobot accepted the claim:', Object.values(after.claims).map((c) => c.status).join(', '));

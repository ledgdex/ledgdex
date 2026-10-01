// node js/fuzz.mjs CORPUS OUT: the JavaScript half of py/tests/fuzz.py.
import { readFileSync, writeFileSync } from 'fs';
import { canonString, parse, ID_KEY } from './canon.js';
import { Ledger } from './core.js';
import { state } from './state.js';

const [, , corpus, out] = process.argv;
const b64 = (s) => new Uint8Array(Buffer.from(s, 'base64'));
const rows = [];
for (const line of readFileSync(corpus, 'utf8').split('\n')) {
  if (!line) continue;
  const c = JSON.parse(line);
  let r;
  if (c.kind === 'text') {
    try { r = { ok: true, canon: canonString(parse(b64(c.data))) }; } catch (e) { r = { ok: false }; }
  } else {
    const root = c.root ? new Ledger(b64(c.root)) : null;
    const led = new Ledger(b64(c.data), root);
    r = { header: led.header !== null, whole: led.whole, broken_at: led.broken_at, entries: led.entries.length,
      error: led.error };
    if (led.header !== null) r.state = canonString(state(led, root, c.now), ID_KEY);
  }
  rows.push(JSON.stringify({ id: c.id, ...r }));
}
writeFileSync(out, rows.join('\n') + '\n');
